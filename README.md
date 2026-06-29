# Forecast Email Backend

This backend runs the packaged Prophet forecasting artifacts, writes the latest
forecast as both CSV and a styled Excel report, tracks job status, and emails
the report on a schedule.

Current workflow:

1. Celery Beat schedules the forecast job for Monday at 9 AM.
2. The forecast job loads the registry, metadata, and saved models from `storage/`.
3. The generated reports are written to:
   - `storage/forecasts/top_300_weekly_forecast.csv`
   - `storage/forecasts/top_300_weekly_forecast.xlsx`
4. Celery Beat schedules the email job for Monday at 10 AM.
5. The email job attaches the styled Excel report and sends it through Resend.

The generated reports are not committed to git. The `storage/forecasts/` folder
is kept with `.gitkeep`, and the CSV/XLSX files appear there after the forecast
job runs.

## API

- `GET /health` - service health check.
- `GET /status` - latest forecast/email job status from
  `storage/status/job-status.json`.

Run locally:

```bash
python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI is available at `http://localhost:8000/docs`.

## Requirements

Use a virtual environment if possible:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

The forecast runner requires `numpy`, `pandas`, `prophet`, and `holidays` in
addition to the API, worker, Redis, and email dependencies.

## Environment

Create `.env` from `.env.example` and fill in real email values:

```bash
cp .env.example .env
```

Required runtime values:

```env
RESEND_API_KEY=re_your_api_key
EMAIL_FROM_EMAIL=forecast@your-verified-domain.com
FORECAST_REPORT_RECIPIENT_EMAIL=client@example.com
```

`FORECAST_REPORT_RECIPIENT_EMAIL` accepts one or more comma-separated addresses.

The rest of the app has defaults in `app/core/config.py`. Current defaults:

```env
SCHEDULED_TIMEZONE=America/Mexico_City

SCHEDULED_FORECAST_ENABLED=true
SCHEDULED_FORECAST_DAY_OF_WEEK=mon
SCHEDULED_FORECAST_HOUR=9
SCHEDULED_FORECAST_MINUTE=0

SCHEDULED_EMAIL_ENABLED=true
SCHEDULED_EMAIL_DAY_OF_WEEK=mon
SCHEDULED_EMAIL_HOUR=10
SCHEDULED_EMAIL_MINUTE=0

FORECAST_MODEL_CALLABLE=app.services.forecasting.predict_from_saved_models:run_saved_model_forecast
FORECAST_HORIZON_DAYS=28
FORECAST_RESULT_FILE=storage/forecasts/top_300_weekly_forecast.csv
JOB_STATUS_FILE=storage/status/job-status.json

CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

EMAIL_FROM_NAME=Forecast Purchase App
FORECAST_EMAIL_SUBJECT=Weekly 4-week sales forecast
```

Set any of those in `.env` or server environment variables only when you need to
override the default, for example when Redis is not on localhost.

## Forecast Artifacts

The saved model runner expects:

```txt
storage/
  metadata/
    training_metadata.json
  models/
    *.json
  registry/
    model_registry.csv
```

The current artifacts are configured for:

- UOMs: `PIEZA`, `CAJA`, and `KG`
- Product/UOM combinations: top 300
- Horizon: controlled by `FORECAST_HORIZON_DAYS`; 28 days produces 4 weekly
  forecast periods.
- Output: one row per product/UOM with identity columns, one column for each
  forecast week, and a total column.

## Manual Testing

Compile/import check:

```bash
python3 -m compileall -q app
```

Run the forecast directly:

```bash
python3 - <<'PY'
from app.services.forecast_service import run_forecast

result = run_forecast()
print(result)
PY
```

With no argument, the forecast begins in the Monday-based week containing
today's date. To hardcode a specific start date in a Python call:

```bash
python3 - <<'PY'
from app.services.forecast_service import run_forecast

result = run_forecast(forecast_start_date="2026-07-06")
print(result)
PY
```

You can also pass a specific date directly to the predictor:

```bash
python3 -m app.services.forecasting.predict_from_saved_models \
  --forecast-start-date 2026-07-06 \
  --horizon-weeks 2
```

Dates use `YYYY-MM-DD`. A date that is not a Monday is aligned to the Monday at
the beginning of that week.

Verify the generated reports:

```bash
ls -lh storage/forecasts/
python3 - <<'PY'
import pandas as pd

path = "storage/forecasts/top_300_weekly_forecast.csv"
df = pd.read_csv(path)
print(df.shape)
print(df.head())
print(df["Código"].nunique())
PY
```

Run the API smoke test:

```bash
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/status
```

Run scheduled task functions manually without waiting for the clock:

```bash
python3 - <<'PY'
from app.workers.tasks import run_scheduled_forecast

print(run_scheduled_forecast())
PY
```

After configuring Resend with real values:

```bash
python3 - <<'PY'
from app.workers.tasks import send_forecast_email

print(send_forecast_email())
PY
```

## Scheduled Jobs

Scheduling runs on Celery + Celery Beat with Redis.

Start Redis:

```bash
docker run -d -p 6379:6379 redis:7
```

Start a worker:

```bash
celery -A app.workers.celery_app worker --loglevel=info
```

Start Beat in another terminal:

```bash
celery -A app.workers.celery_app beat --loglevel=info
```

Beat should register:

- `scheduled-forecast`
- `scheduled-forecast-email`

## Resend Setup

1. Create or log into a Resend account.
2. Create an API key and set `RESEND_API_KEY`.
3. Add and verify the sending domain in Resend.
4. Set `EMAIL_FROM_EMAIL` to an address on that verified domain.
5. Set `FORECAST_REPORT_RECIPIENT_EMAIL` to the real recipient list.

For a sandbox check, Resend can use `onboarding@resend.dev` as the sender, but
delivery is limited by Resend's sandbox rules. For a true end-to-end test, use a
verified sender domain and a recipient inbox you can check.
