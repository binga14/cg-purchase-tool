<!-- The backend runs saved demand forecasting artifacts on a schedule, stores the forecast CSV, tracks job status, and emails the generated CSV report. -->

## Tech Stack

- FastAPI
- Python
- Pandas
- NumPy
- Prophet
- Celery
- Redis
- Resend

## Main Backend Responsibilities

1. Load saved forecast artifacts from `storage/forecast_artifacts`.
2. Generate the 2-week forecast CSV in `storage/forecasts`.
3. Track forecast and email job state in `storage/status/job-status.json`.
4. Expose `GET /health` and `GET /status`.
5. Schedule forecast and email jobs through Celery Beat.
6. Email the latest forecast CSV through Resend.

## Structure

```txt
backend/
  app/
    main.py
    core/
      config.py
    services/
      forecast_service.py
      email_service.py
      job_status_service.py
      forecasting/
        predict_from_saved_models.py
    workers/
      celery_app.py
      tasks.py
  storage/
    forecast_artifacts/
    forecasts/
    status/
```
