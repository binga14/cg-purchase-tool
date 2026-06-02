from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.schemas.forecast import ForecastJobResponse
from app.schemas.upload import ErrorResponse
from app.services.file_storage_service import build_stored_filename, save_upload_file
from app.services.forecast_job_store import ForecastJob, forecast_job_store, utc_now_iso
from app.services.forecast_service import run_forecast_file

router = APIRouter(prefix="/forecasts", tags=["forecasts"])

ALLOWED_FORECAST_EXTENSIONS = {"csv", "xlsx"}
REQUIRED_XLSX_PARTS = {"[Content_Types].xml", "xl/workbook.xml"}


def error_response(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def file_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def serialize_job(job: ForecastJob) -> ForecastJobResponse:
    return ForecastJobResponse(
        id=job.id,
        uploadedFileName=job.uploaded_file_name,
        status=job.status,
        createdAt=job.created_at,
        startedAt=job.started_at,
        completedAt=job.completed_at,
        errorMessage=job.error_message,
        outputAvailable=job.output_available,
        downloadUrl=f"/api/forecasts/{job.id}/download" if job.output_available else None,
    )


async def validate_forecast_upload(upload_file: UploadFile) -> None:
    settings = get_settings()

    if not upload_file.filename:
        raise error_response(
            status.HTTP_400_BAD_REQUEST,
            "missing_filename",
            "Uploaded file must include a filename.",
        )

    extension = file_extension(upload_file.filename)
    if extension not in ALLOWED_FORECAST_EXTENSIONS:
        raise error_response(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "unsupported_file_type",
            "Forecasting accepts .csv and .xlsx uploads only.",
        )

    content = await upload_file.read(settings.max_upload_size_bytes + 1)
    await upload_file.seek(0)

    if not content:
        raise error_response(
            status.HTTP_400_BAD_REQUEST,
            "empty_file",
            "Uploaded file is empty.",
        )

    if len(content) > settings.max_upload_size_bytes:
        max_mb = settings.max_upload_size_bytes // (1024 * 1024)
        raise error_response(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "file_too_large",
            f"Uploaded file must be {max_mb} MB or smaller.",
        )

    if extension == "xlsx":
        try:
            with ZipFile(BytesIO(content)) as workbook:
                workbook_parts = set(workbook.namelist())
        except BadZipFile as exc:
            raise error_response(
                status.HTTP_400_BAD_REQUEST,
                "invalid_xlsx_file",
                "The uploaded .xlsx file is not a valid Excel workbook.",
            ) from exc

        if not REQUIRED_XLSX_PARTS.issubset(workbook_parts):
            raise error_response(
                status.HTTP_400_BAD_REQUEST,
                "invalid_xlsx_file",
                "The uploaded .xlsx file is missing required workbook data.",
            )


def run_forecast_job(job_id: str) -> None:
    job = forecast_job_store.mark_processing(job_id)
    if job is None:
        return

    try:
        run_forecast_file(job.input_path, job.output_path)
    except Exception as exc:
        forecast_job_store.mark_failed(job_id, str(exc))
        return

    forecast_job_store.mark_completed(job_id)


@router.post(
    "",
    response_model=ForecastJobResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_forecast_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> ForecastJobResponse:
    settings = get_settings()
    await validate_forecast_upload(file)

    stored_filename = build_stored_filename(file.filename or "forecast-upload.csv")
    try:
        input_path = save_upload_file(file, settings.upload_dir, stored_filename)
    except OSError as exc:
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "file_storage_failed",
            "Uploaded file could not be stored. Please try again.",
        ) from exc

    job_id = f"forecast-{uuid4().hex}"
    output_filename = f"{job_id}.csv"
    job = forecast_job_store.create(
        ForecastJob(
            id=job_id,
            uploaded_file_name=file.filename or stored_filename,
            input_path=input_path,
            output_path=settings.forecast_output_dir / output_filename,
            status="queued",
            created_at=utc_now_iso(),
        )
    )
    background_tasks.add_task(run_forecast_job, job.id)

    return serialize_job(job)


@router.get(
    "/{job_id}",
    response_model=ForecastJobResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_forecast_job(job_id: str) -> ForecastJobResponse:
    job = forecast_job_store.get(job_id)
    if job is None:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "forecast_job_not_found",
            "Forecast job was not found.",
        )
    return serialize_job(job)


@router.get(
    "/{job_id}/download",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def download_forecast(job_id: str) -> FileResponse:
    job = forecast_job_store.get(job_id)
    if job is None:
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "forecast_job_not_found",
            "Forecast job was not found.",
        )

    if job.status != "completed" or not job.output_path.exists():
        raise error_response(
            status.HTTP_409_CONFLICT,
            "forecast_not_ready",
            "Forecast output is not ready for download.",
        )

    return FileResponse(
        path=job.output_path,
        filename=f"{job.id}.csv",
        media_type="text/csv",
    )
