"""Pydantic models for a JD run and its parsed scorecard."""
from __future__ import annotations

from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

RunStatus = Literal["running", "completed", "failed"]
WorkMode = Literal["onsite", "hybrid", "remote"]


class Scorecard(BaseModel):
    """Structured requirements extracted from a JD, plus candidate path framings."""

    role_title: str
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None
    seniority: Optional[str] = None
    domain: Optional[str] = None
    target_companies: list[str] = Field(default_factory=list)
    education_preference: Optional[str] = None
    location: Optional[str] = None
    work_mode: WorkMode = "onsite"
    # Only set when work_mode is "remote" and the JD restricts it to a
    # country/region (e.g. "United States", "EU"). None means unrestricted
    # remote (candidates anywhere are fine).
    remote_geo_constraint: Optional[str] = None
    candidate_paths: list[str] = Field(default_factory=list)


class JDRunCreate(BaseModel):
    """Request body for POST /api/runs."""

    jd_text: str


class JDRun(BaseModel):
    """A single pipeline execution, from JD input to completed shortlist."""

    jd_run_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str
    jd_raw_text: str
    scorecard: Optional[Scorecard] = None
    status: RunStatus = "running"
    status_detail: Optional[str] = None
    total_discovered: int = 0
    total_shortlisted: int = 0
    output_path: Optional[str] = None
    error: Optional[str] = None

    class Config:
        extra = "allow"
