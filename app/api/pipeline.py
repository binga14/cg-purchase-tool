from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.schemas.pipeline import (
    ErrorResponse,
    DatePeriodResponse,
    ForecastTriggerResponse,
    PhaseTriggerResponse,
    PipelinePhaseResponse,
    PipelineStatusResponse,
    TrainingDataResponse,
    UploadResponse,
)
from app.services.cg_pipeline_service import (
    FORECASTING,
    LOADING,
    SUCCESSFUL,
    TRAIN_DATA_PREP,
    WEEKLY_UPLOAD,
    PipelineError,
    get_forecast_period_info,
    pipeline_state,
    prepare_train_data,
    replace_training_data,
    run_forecast_pipeline_task,
    store_weekly_upload,
    validate_weekly_upload_content,
)

router = APIRouter(tags=["cg pipeline"])


def error_response(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def serialize_status() -> PipelineStatusResponse:
    snapshot = pipeline_state.snapshot()
    return PipelineStatusResponse(
        phases=[
            PipelinePhaseResponse(
                phase=phase.phase,
                status=phase.status,
                startedAt=phase.started_at,
                completedAt=phase.completed_at,
                errorMessage=phase.error_message,
            )
            for phase in snapshot.phases
        ],
        latestUploadFileName=snapshot.latest_upload_file_name,
        latestUploadUrl=snapshot.latest_upload_url,
        trainDataPath=str(snapshot.train_data_path) if snapshot.train_data_path else None,
        forecastResultPath=(
            str(snapshot.forecast_result_path) if snapshot.forecast_result_path else None
        ),
        latestSalesDate=snapshot.latest_sales_date,
    )


def run_train_data_prep_task() -> None:
    try:
        prepare_train_data()
    except Exception as exc:
        pipeline_state.mark_failed(TRAIN_DATA_PREP, str(exc))
        return

    pipeline_state.mark_successful(TRAIN_DATA_PREP)


def run_forecast_task() -> None:
    run_forecast_pipeline_task()


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def upload_weekly_data(file: UploadFile = File(...)) -> UploadResponse:
    content = await file.read()
    pipeline_state.mark_loading(WEEKLY_UPLOAD)

    try:
        validate_weekly_upload_content(file.filename, content)
        upload_path, stored_filename, static_url = store_weekly_upload(
            file.filename or "weekly-data.xlsx",
            content,
        )
    except PipelineError as exc:
        pipeline_state.mark_failed(WEEKLY_UPLOAD, str(exc))
        raise error_response(
            exc.status_code,
            exc.code,
            str(exc),
        ) from exc
    except OSError as exc:
        message = "Uploaded file could not be stored. Please try again."
        pipeline_state.mark_failed(WEEKLY_UPLOAD, message)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "file_storage_failed",
            message,
        ) from exc

    pipeline_state.set_latest_upload(file.filename or stored_filename, upload_path, static_url)
    pipeline_state.mark_successful(WEEKLY_UPLOAD)
    return UploadResponse(
        fileName=file.filename or stored_filename,
        storedFileName=stored_filename,
        staticUrl=static_url,
        status=SUCCESSFUL,
    )


@router.post(
    "/training-data",
    response_model=TrainingDataResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def replace_total_training_data(file: UploadFile = File(...)) -> TrainingDataResponse:
    content = await file.read()
    pipeline_state.mark_loading(TRAIN_DATA_PREP)

    try:
        train_data_path = replace_training_data(file.filename, content)
    except PipelineError as exc:
        pipeline_state.mark_failed(TRAIN_DATA_PREP, str(exc))
        raise error_response(exc.status_code, exc.code, str(exc)) from exc
    except OSError as exc:
        message = "Training data could not be stored. Please try again."
        pipeline_state.mark_failed(TRAIN_DATA_PREP, message)
        raise error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "training_data_storage_failed",
            message,
        ) from exc

    pipeline_state.mark_successful(TRAIN_DATA_PREP)
    return TrainingDataResponse(
        fileName=file.filename or train_data_path.name,
        trainDataPath=str(train_data_path),
        status=SUCCESSFUL,
        message="Training data replaced successfully.",
    )


@router.post(
    "/cg-data",
    response_model=PhaseTriggerResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def trigger_train_data_prep(background_tasks: BackgroundTasks) -> PhaseTriggerResponse:
    snapshot = pipeline_state.snapshot()
    weekly_phase = next(
        phase for phase in snapshot.phases if phase.phase == WEEKLY_UPLOAD
    )
    if weekly_phase.status != SUCCESSFUL or snapshot.latest_upload_path is None:
        raise error_response(
            status.HTTP_409_CONFLICT,
            "weekly_upload_required",
            "Upload weekly data before preparing train data.",
        )

    if pipeline_state.is_loading(TRAIN_DATA_PREP):
        raise error_response(
            status.HTTP_409_CONFLICT,
            "train_data_prep_in_progress",
            "Train data preparation is already running.",
        )

    pipeline_state.mark_loading(TRAIN_DATA_PREP)
    background_tasks.add_task(run_train_data_prep_task)
    return PhaseTriggerResponse(
        phase=TRAIN_DATA_PREP,
        status=LOADING,
        message="Train data preparation started.",
    )


@router.post(
    "/forecast",
    response_model=ForecastTriggerResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def trigger_forecast(background_tasks: BackgroundTasks) -> ForecastTriggerResponse:
    snapshot = pipeline_state.snapshot()
    train_phase = next(
        phase for phase in snapshot.phases if phase.phase == TRAIN_DATA_PREP
    )
    if (
        train_phase.status != SUCCESSFUL
        or snapshot.train_data_path is None
        or not snapshot.train_data_path.exists()
    ):
        raise error_response(
            status.HTTP_409_CONFLICT,
            "train_data_required",
            "Prepare train data before running the forecast.",
        )

    try:
        period_info = get_forecast_period_info(snapshot.train_data_path)
    except PipelineError as exc:
        raise error_response(exc.status_code, exc.code, str(exc)) from exc

    if not pipeline_state.try_mark_loading(FORECASTING):
        raise error_response(
            status.HTTP_409_CONFLICT,
            "forecast_in_progress",
            "Forecasting is already running.",
        )

    background_tasks.add_task(run_forecast_task)
    return ForecastTriggerResponse(
        phase=FORECASTING,
        status=LOADING,
        message="Forecasting started.",
        trainingDataPeriod=DatePeriodResponse(
            startDate=period_info.training_start_date,
            endDate=period_info.training_end_date,
        ),
        forecastingPeriod=DatePeriodResponse(
            startDate=period_info.forecasting_start_date,
            endDate=period_info.forecasting_end_date,
        ),
        forecastHorizonWeeks=period_info.forecast_horizon_weeks,
    )


def build_forecast_results_response() -> FileResponse:
    settings = get_settings()
    snapshot = pipeline_state.snapshot()
    forecast_phase = next(
        phase for phase in snapshot.phases if phase.phase == FORECASTING
    )
    if forecast_phase.status != SUCCESSFUL:
        raise error_response(
            status.HTTP_409_CONFLICT,
            "forecast_not_ready",
            "Forecast output is not ready for download.",
        )

    if not settings.forecast_result_file.exists():
        raise error_response(
            status.HTTP_404_NOT_FOUND,
            "forecast_result_not_found",
            "Forecast result file was not found.",
        )

    return FileResponse(
        path=settings.forecast_result_file,
        filename=settings.forecast_result_file.name,
        media_type="text/csv",
    )


@router.get(
    "/results",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def download_forecast_results() -> FileResponse:
    return build_forecast_results_response()


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status() -> PipelineStatusResponse:
    return serialize_status()
