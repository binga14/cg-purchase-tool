from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.schemas.upload import ErrorResponse, UploadJobResponse
from app.services.file_storage_service import build_stored_filename, save_upload_file

router = APIRouter(prefix="/uploads", tags=["uploads"])

REQUIRED_XLSX_PARTS = {"[Content_Types].xml", "xl/workbook.xml"}


def error_response(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def file_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


async def validate_upload_file(upload_file: UploadFile) -> bytes:
    settings = get_settings()

    if not upload_file.filename:
        raise error_response(
            status.HTTP_400_BAD_REQUEST,
            "missing_filename",
            "Uploaded file must include a filename.",
        )

    extension = file_extension(upload_file.filename)
    if extension not in settings.allowed_extensions:
        allowed = ", ".join(f".{item}" for item in settings.allowed_extensions)
        raise error_response(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "unsupported_file_type",
            f"Only {allowed} files are supported.",
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

    return content


@router.post(
    "",
    response_model=UploadJobResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def upload_file(file: UploadFile = File(...)) -> UploadJobResponse:
    settings = get_settings()
    await validate_upload_file(file)

    stored_filename = build_stored_filename(file.filename or "upload")

    try:
        save_upload_file(file, settings.upload_dir, stored_filename)
    except OSError as exc:
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "file_storage_failed",
            "Uploaded file could not be stored. Please try again.",
        ) from exc

    now = datetime.now(timezone.utc).isoformat()

    return UploadJobResponse(
        id=f"upload-{uuid4().hex}",
        uploadedFileName=file.filename or stored_filename,
        uploadDate=now,
        status="uploaded",
        forecastStatus="queued",
        processingStatus="queued",
        startedAt=None,
        completedAt=None,
        errorMessage=None,
        outputAvailable=False,
    )
