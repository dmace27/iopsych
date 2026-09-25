"""FastAPI application entry point for the IOPsych service."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Stable response contract for service health probes."""

    status: Literal["ok"]
    service: Literal["api"]
    version: str


app = FastAPI(
    title="IOPsych API",
    description="API foundation for the consented, human-reviewed IOPsych pilot.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse, tags=["operations"])
async def health() -> HealthResponse:
    """Return a dependency-free liveness response for local and hosted probes."""

    return HealthResponse(status="ok", service="api", version=app.version)
