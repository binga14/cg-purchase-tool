from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.forecasts import router as forecasts_router
from app.api.uploads import router as uploads_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(uploads_router, prefix=settings.api_prefix)
app.include_router(forecasts_router, prefix=settings.api_prefix)
