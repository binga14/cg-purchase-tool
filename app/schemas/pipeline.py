from typing import Literal, Optional

from pydantic import BaseModel


PhaseName = Literal["weekly data upload", "train data prep", "forecasting"]
PhaseStatus = Literal["Yet to start", "Loading", "Successful", "Failed"]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorBody


class PipelinePhaseResponse(BaseModel):
    phase: PhaseName
    status: PhaseStatus
    startedAt: Optional[str]
    completedAt: Optional[str]
    errorMessage: Optional[str]


class PipelineStatusResponse(BaseModel):
    phases: list[PipelinePhaseResponse]
    latestUploadFileName: Optional[str]
    latestUploadUrl: Optional[str]
    trainDataPath: Optional[str]
    forecastResultPath: Optional[str]


class UploadResponse(BaseModel):
    fileName: str
    storedFileName: str
    staticUrl: str
    status: PhaseStatus


class TrainingDataResponse(BaseModel):
    fileName: str
    trainDataPath: str
    status: PhaseStatus
    message: str


class PhaseTriggerResponse(BaseModel):
    phase: PhaseName
    status: PhaseStatus
    message: str
