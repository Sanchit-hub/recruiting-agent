"""Pydantic models for HR feedback on candidates and learned hiring patterns."""
from __future__ import annotations

from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

Outcome = Literal[
    "shortlisted",
    "contacted",
    "interviewed",
    "offer_made",
    "offer_accepted",
    "offer_declined",
    "rejected_by_us",
    "no_response",
    "withdrew",
]

RejectionReason = Literal[
    "compensation_mismatch",
    "role_not_fit",
    "competing_offer",
    "location_issue",
    "last_minute_dropout",
    "unresponsive",
    "other",
]

StageAtExit = Literal["shortlist", "outreach", "screening", "interview", "offer"]


class FeedbackCreate(BaseModel):
    """Request body for POST /api/feedback."""

    candidate_id: str
    jd_run_id: str
    outcome: Outcome
    rejection_reason: Optional[RejectionReason] = None
    stage_at_exit: Optional[StageAtExit] = None
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def notes_max_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 300:
            raise ValueError("notes must be 300 characters or fewer")
        return v


class FeedbackRecord(FeedbackCreate):
    """A stored feedback record."""

    feedback_id: str = Field(default_factory=lambda: str(uuid4()))
    feedback_given_at: str


class LearnedPattern(BaseModel):
    """A historical hiring pattern derived from feedback, used to inform deep research."""

    pattern_id: str = Field(default_factory=lambda: str(uuid4()))
    pattern_description: str
    profile_group: str
    offer_decline_rate: float = 0.0
    acceptance_rate: float = 0.0
    most_common_dropout_stage: Optional[str] = None
    most_common_rejection_reason: Optional[str] = None
    sample_size: int = 0
    active: bool = True
    generated_at: str
