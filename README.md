## Run command
python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

python3 -m uvicorn app.main:app --reload --host localhost --port 8000

swagger link: http://localhost:8000/docs

## Scheduled forecast and email

Scheduling runs on **Celery + Celery Beat** with a Redis broker. By default the
forecast runs Sunday 10 PM and the forecast CSV is emailed Monday 10 AM. All
scheduled jobs share a single timezone (`SCHEDULED_TIMEZONE`, default GMT-6 /
America/Mexico_City).

Run the scheduler stack alongside the API:

```bash
# Redis broker
docker run -d -p 6379:6379 redis:7

# Worker (runs the tasks) and Beat (fires the schedule)
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info
```

Add these environment variables before starting the backend (see `.env.example`):

```env
# Single timezone for all scheduled jobs (IANA name). Mexico_City = permanent GMT-6.
SCHEDULED_TIMEZONE=America/Mexico_City

SCHEDULED_FORECAST_ENABLED=true
SCHEDULED_FORECAST_DAY_OF_WEEK=sun
SCHEDULED_FORECAST_HOUR=22
SCHEDULED_FORECAST_MINUTE=0
SCHEDULED_FORECAST_MAX_SALES_AGE_WEEKS=2

SCHEDULED_EMAIL_ENABLED=true
SCHEDULED_EMAIL_DAY_OF_WEEK=mon
SCHEDULED_EMAIL_HOUR=10
SCHEDULED_EMAIL_MINUTE=0

# Celery / Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Resend email
RESEND_API_KEY=re_your_api_key
EMAIL_FROM_EMAIL=forecast@yourdomain.com
EMAIL_FROM_NAME=Forecast Purchase App
FORECAST_REPORT_RECIPIENT_EMAIL=alice@example.com,bob@example.com
```

`FORECAST_REPORT_RECIPIENT_EMAIL` is where the weekly forecast email is sent —
one or more comma-separated addresses. The email includes the latest forecast CSV
as an attachment.

## Resend setup

1. Create or log into a [Resend](https://resend.com) account.
2. Go to **API Keys** and create a key; put it in `RESEND_API_KEY`.
3. Go to **Domains**, add and verify your sending domain.
4. Set `EMAIL_FROM_EMAIL` to an address on that verified domain.

For a quick test without verifying a domain, use `onboarding@resend.dev` as the
`EMAIL_FROM_EMAIL`.
