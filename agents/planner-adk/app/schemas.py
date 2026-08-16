"""Pydantic mirrors of the JSON Schemas in /contracts/schemas.

Kept intentionally close to the shared contracts so the Planner's HTTP API
stays schema-compatible with contracts/schemas/travel-request.schema.json
and travel-response.schema.json. Do not fork field names here without
updating /contracts and explaining the incompatibility (PROJECT_SPEC.md §13
and §42 rule 6).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TravelRequest(BaseModel):
    request_id: str | None = None
    origin: str
    destination: str
    start_date: str
    end_date: str
    travelers: int = Field(ge=1)
    budget: float = Field(ge=0)
    currency: str = "BRL"
    preferences: list[str] = Field(default_factory=list)


class SubResult(BaseModel):
    status: Literal["SUCCESS", "PARTIAL", "UNAVAILABLE", "UNKNOWN"] = "UNAVAILABLE"


class FlightResult(SubResult):
    options: list[dict] = Field(default_factory=list)
    recommended_option_id: str | None = None
    notes: str = ""


class HotelResult(SubResult):
    options: list[dict] = Field(default_factory=list)
    notes: str = ""


class ActivityResult(SubResult):
    days: list[dict] = Field(default_factory=list)
    notes: str = ""


class BudgetResult(BaseModel):
    status: Literal["SUCCESS", "PARTIAL", "UNAVAILABLE", "UNKNOWN"] = "UNKNOWN"
    budget_status: Literal["WITHIN_BUDGET", "NEAR_LIMIT", "OVER_BUDGET", "UNKNOWN"] = "UNKNOWN"
    flight_cost: float | None = None
    hotel_cost: float | None = None
    activity_cost: float | None = None
    food_estimate: float | None = None
    transport_estimate: float | None = None
    total: float = 0
    limit: float = 0
    remaining: float = 0
    notes: str = ""


class EnrichmentResult(BaseModel):
    status: Literal["SUCCESS", "SKIPPED", "UNAVAILABLE"] = "SKIPPED"
    provider: str | None = None


class TravelResponseMetadata(BaseModel):
    trace_id: str = ""
    correlation_id: str = ""
    duration_ms: float = 0


class TravelResponse(BaseModel):
    request_id: str
    status: Literal["COMPLETED", "PARTIAL", "FAILED"]
    flight: FlightResult
    hotel: HotelResult
    activities: ActivityResult
    budget: BudgetResult
    enrichment: EnrichmentResult
    metadata: TravelResponseMetadata
