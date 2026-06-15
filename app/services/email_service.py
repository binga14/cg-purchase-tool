import base64
from email.utils import formataddr
from pathlib import Path

import resend

from app.core.config import get_settings
from app.services.cg_pipeline_service import (
    FORECASTING,
    SUCCESSFUL,
    get_forecast_period_info,
    pipeline_state,
)


def build_forecast_email_body() -> str:
    settings = get_settings()
    snapshot = pipeline_state.snapshot()

    lines = [
        "Hello,",
        "",
        "The latest forecast run has completed successfully. The forecast CSV is attached.",
    ]

    if snapshot.train_data_path and snapshot.train_data_path.exists():
        try:
            period_info = get_forecast_period_info(snapshot.train_data_path)
            lines.extend(
                [
                    "",
                    "Training data period:",
                    f"- {period_info.training_start_date} to {period_info.training_end_date}",
                    "",
                    "Forecasting period:",
                    f"- {period_info.forecasting_start_date} to {period_info.forecasting_end_date}",
                    f"- Horizon: {period_info.forecast_horizon_weeks} weeks",
                ]
            )
        except Exception:
            if snapshot.latest_sales_date:
                lines.extend(["", f"Latest sales date: {snapshot.latest_sales_date}"])

    lines.extend(
        [
            "",
            "Regards,",
            "Forecast Purchase App",
        ]
    )
    return "\n".join(lines)


def validate_email_settings() -> bool:
    settings = get_settings()
    return all(
        [
            settings.resend_api_key,
            settings.email_from_email,
            settings.forecast_report_recipients,
        ]
    )


def build_forecast_email_params(result_path: Path) -> "resend.Emails.SendParams":
    settings = get_settings()
    attachment_content = base64.b64encode(result_path.read_bytes()).decode("ascii")

    return {
        "from": formataddr((settings.email_from_name, settings.email_from_email)),
        "to": list(settings.forecast_report_recipients),
        "subject": "Weekly forecast report",
        "text": build_forecast_email_body(),
        "attachments": [
            {
                "filename": result_path.name,
                "content": attachment_content,
                "content_type": "text/csv",
            }
        ],
    }


def send_forecast_email_if_ready() -> bool:
    settings = get_settings()
    if not settings.scheduled_email_enabled:
        return False
    if not validate_email_settings():
        print("Email settings are incomplete. Scheduled forecast email was skipped.")
        return False

    snapshot = pipeline_state.snapshot()
    forecast_phase = next(
        phase for phase in snapshot.phases if phase.phase == FORECASTING
    )
    if forecast_phase.status != SUCCESSFUL:
        return False
    if not settings.forecast_result_file.exists():
        return False

    resend.api_key = settings.resend_api_key
    resend.Emails.send(build_forecast_email_params(settings.forecast_result_file))

    return True
