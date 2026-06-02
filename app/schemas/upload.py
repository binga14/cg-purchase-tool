from typing import Literal, Optional

from pydantic import BaseModel


JobStatus = Literal["uploaded", "queued", "processing", "completed", "failed"]


class UploadJobResponse(BaseModel):
    id: str
    uploadedFileName: str
    uploadDate: str
    status: JobStatus
    forecastStatus: JobStatus
    processingStatus: JobStatus
    startedAt: Optional[str]
    completedAt: Optional[str]
    errorMessage: Optional[str]
    outputAvailable: bool


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorBody
