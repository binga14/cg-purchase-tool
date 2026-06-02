from typing import Literal, Optional

from pydantic import BaseModel


ForecastJobStatus = Literal["queued", "processing", "completed", "failed"]


class ForecastJobResponse(BaseModel):
    id: str
    uploadedFileName: str
    status: ForecastJobStatus
    createdAt: str
    startedAt: Optional[str]
    completedAt: Optional[str]
    errorMessage: Optional[str]
    outputAvailable: bool
    downloadUrl: Optional[str]
