from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class SearchRequest(BaseModel):
    product_id: str
    countries: list[str] = Field(default_factory=list)
    customer_types: list[str] = Field(default_factory=list)
    max_results_per_query: int = Field(default=8, ge=3, le=20)
    max_queries: int = Field(default=12, ge=4, le=30)
    search_provider: Literal["auto", "google_cse", "duckduckgo"] = "auto"
    fast_mode: bool = True


class GoogleSettingsRequest(BaseModel):
    google_api_key: str = ""
    google_cse_id: str = ""


class GoogleSettingsResponse(BaseModel):
    google_api_key: str
    google_cse_id: str
    configured: bool


class Lead(BaseModel):
    company_name: str = ""
    website: str = ""
    country: str = ""
    emails: list[str] = Field(default_factory=list)
    phone: str = ""
    description: str = ""
    score: int = 0
    reason: str = ""
    customer_type_guess: str = ""
    source_query: str = ""


class JobProgress(BaseModel):
    status: JobStatus
    message: str = ""
    total_queries: int = 0
    completed_queries: int = 0
    leads_found: int = 0
    leads_scored: int = 0
    total_steps: int = 0
    completed_steps: int = 0


class JobResult(BaseModel):
    id: str
    product_id: str
    product_name: str
    created_at: datetime
    progress: JobProgress
    queries: list[str] = Field(default_factory=list)
    leads: list[Lead] = Field(default_factory=list)
    error: str = ""


class ProductInfo(BaseModel):
    id: str
    name: str
    name_en: str
    description: str
    customer_types: list[str]
    market_label: str
    markets: list[dict[str, str]]


class ProductsResponse(BaseModel):
    products: list[ProductInfo]
