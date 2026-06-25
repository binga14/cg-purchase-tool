import base64
from email.utils import formataddr
from pathlib import Path

import resend

from app.core.config import get_settings


class ForecastEmailError(RuntimeError):
    pass


PLACEHOLDER_EMAIL_DOMAINS = {
    "example.com",
    "yourdomain.com",
    "your-verified-domain.com",
}


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower()


def validate_email_settings() -> None:
    settings = get_settings()
    missing = []
    if not settings.resend_api_key:
        missing.append("RESEND_API_KEY")
    if not settings.email_from_email:
        missing.append("EMAIL_FROM_EMAIL")
    if not settings.forecast_report_recipients:
        missing.append("FORECAST_REPORT_RECIPIENT_EMAIL")

    if missing:
        raise ForecastEmailError(
            f"Missing required email settings: {', '.join(missing)}"
        )

    placeholder_emails = [
        email
        for email in (settings.email_from_email, *settings.forecast_report_recipients)
        if email_domain(email) in PLACEHOLDER_EMAIL_DOMAINS
    ]
    if placeholder_emails:
        raise ForecastEmailError(
            "Replace placeholder email settings before sending: "
            + ", ".join(placeholder_emails)
        )


def build_forecast_email_body() -> str:
    settings = get_settings()
    return "\n".join(
        [
            "Hello,",
            "",
            "The latest 2-week sales forecast has been generated successfully.",
            "The forecast CSV is attached.",
            "",
            f"Forecast horizon: {settings.forecast_horizon_days} days",
            "",
            "Regards,",
            settings.email_from_name,
        ]
    )


def build_forecast_email_params(result_path: Path) -> "resend.Emails.SendParams":
    settings = get_settings()
    attachment_content = base64.b64encode(result_path.read_bytes()).decode("ascii")

    return {
        "from": formataddr((settings.email_from_name, settings.email_from_email)),
        "to": list(settings.forecast_report_recipients),
        "subject": settings.forecast_email_subject,
        "text": build_forecast_email_body(),
        "attachments": [
            {
                "filename": result_path.name,
                "content": attachment_content,
                "content_type": "text/csv",
            }
        ],
    }


def send_forecast_email() -> None:
    settings = get_settings()
    result_path = settings.forecast_result_file
    if not result_path.exists():
        raise ForecastEmailError(f"Forecast CSV was not found at '{result_path}'.")
    if result_path.stat().st_size == 0:
        raise ForecastEmailError(f"Forecast CSV at '{result_path}' is empty.")

    validate_email_settings()
    resend.api_key = settings.resend_api_key
    resend.Emails.send(build_forecast_email_params(result_path))
