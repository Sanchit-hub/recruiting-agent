"""Pydantic models for candidates and their scoring/research data."""
from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

Tier = Literal["top", "medium", "low", "insufficient_evidence"]
EvidenceConfidence = Literal["high", "medium", "low"]
RoleFamilyMatch = Literal["same", "adjacent", "different"]


class FitBreakdown(BaseModel):
    """Component scores that sum to fit_score."""

    skills_score: int = 0
    experience_score: int = 0
    role_family_score: int = 0
    domain_score: int = 0
    education_score: int = 0


class SemanticCheckResult(BaseModel):
    """Result of the batched Gemini semantic check for a single candidate."""

    candidate_id: str
    role_family_match: RoleFamilyMatch = "different"
    role_family_score: int = 0
    skills_found: list[str] = Field(default_factory=list)
    skills_score: int = 0
    domain_match: bool = False
    domain_score: int = 0


def _coerce_to_string_list(value: Any) -> Any:
    """Some models return {"certain": [...], "inferred": [...]} instead of a flat
    list for fields we ask for as a list. Flatten dict-of-lists shapes defensively
    rather than failing validation over an LLM's harmless formatting choice."""
    if isinstance(value, dict):
        flattened: list[str] = []
        for key, items in value.items():
            if isinstance(items, list):
                flattened.extend(f"{key}: {item}" for item in items)
            else:
                flattened.append(f"{key}: {items}")
        return flattened
    return value


class ResearchBriefing(BaseModel):
    """Structured deep-research output from the deep research model."""

    trajectory: str = ""
    fit_reasoning: str = ""
    red_flags: list[str] = Field(default_factory=list)
    moveability: str = ""
    confirmed_signals: list[str] = Field(default_factory=list)
    fit_score_adjustment: int = 0

    @field_validator("red_flags", "confirmed_signals", mode="before")
    @classmethod
    def _normalize_list_fields(cls, value: Any) -> Any:
        return _coerce_to_string_list(value)


class Candidate(BaseModel):
    """A sourced candidate, from raw discovery through final scoring."""

    candidate_id: str = Field(default_factory=lambda: str(uuid4()))
    jd_run_id: str

    name: str = ""
    profile_url: str = ""
    headline: str = ""
    source: str = "exa"
    matched_path: str = ""
    raw_exa_data: dict[str, Any] = Field(default_factory=dict)

    current_title: Optional[str] = None
    current_company: Optional[str] = None
    location: Optional[str] = None
    work_history: list[str] = Field(default_factory=list)
    skills_mentioned: list[str] = Field(default_factory=list)

    tier: Tier = "insufficient_evidence"
    fit_score: int = 0
    fit_breakdown: FitBreakdown = Field(default_factory=FitBreakdown)
    evidence_confidence: EvidenceConfidence = "low"
    evidence_notes: str = ""
    location_flag: Optional[bool] = None

    research_briefing: Optional[ResearchBriefing] = None

    created_at: Optional[str] = None

    class Config:
        extra = "allow"
