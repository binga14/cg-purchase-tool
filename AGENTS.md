The backend handles Excel uploads, demand forecasting, inventory comparison, purchase-order calculation, output Excel generation, job tracking, and scheduled execution.

## Tech Stack

- FastAPI
- Python
- Pandas
- openpyxl
- PostgreSQL
- SQLAlchemy or SQLModel
- Alembic for migrations
- APScheduler for background jobs

## Main Backend Responsibilities

1. Receive Excel upload.
2. Validate uploaded Excel.
3. Store uploaded file.
4. Create upload/job records.
5. Run demand forecasting.
6. Compare forecast with current inventory.
7. Calculate purchase quantities.
8. Generate purchase-order Excel.
9. Store output file.
10. Expose download endpoint.
11. Run scheduled jobs.

## Suggested Structure

```txt
backend/
  app/
    main.py
    core/
      config.py
      database.py
    api/
      uploads.py
      jobs.py
      downloads.py
    models/
      upload.py
      forecast_job.py
      purchase_order.py
    schemas/
      upload.py
      job.py
      purchase_order.py
    services/
      excel_service.py
      forecast_service.py
      inventory_service.py
      purchase_order_service.py
      file_storage_service.py
    workers/
      tasks.py
      scheduler.py
    utils/
      logging.py