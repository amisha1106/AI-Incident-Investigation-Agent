"""
IncidentIQ API request and response models.
"""

from pydantic import BaseModel, Field, field_validator


class InvestigationRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Incident description to investigate.",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()

        if "\x00" in value:
            raise ValueError("Query contains an invalid null character.")

        return value

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": (
                    "Checkout requests are failing because of "
                    "database connection pool exhaustion."
                )
            }
        }
    }


class InvestigationResponse(BaseModel):
    success: bool
    query: str

    # Correlation identifiers
    request_id: str | None = None
    job_id: str | None = None
    investigation_id: str | None = None

    observations: list[str]
    evidence: list[str]
    hypotheses: list[str]
    tools_used: list[str]
    evidence_gaps: list[str]
    confidence: float
    investigation_duration_seconds: float
    stop_reason: str
    final_result: dict


class MetricsResponse(BaseModel):
    metrics: list[dict]


class InvestigationJobResponse(BaseModel):
    job_id: str
    request_id: str | None = None
    status: str


class InvestigationJobStatusResponse(BaseModel):
    job_id: str
    request_id: str | None = None
    status: str
    created_at: float | None = None
    started_at: float | None = None
    completed_at: float | None = None
    result: dict | None = None
    error: str | None = None