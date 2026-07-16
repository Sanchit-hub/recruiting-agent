"""Step 3: Filter & tier candidates, then Step 4: score and tier them.

Three sub-steps run in order, each only on survivors of the previous:
  3a. Evidence baseline gate (Python, no LLM)
  3b. Structured checks: location + experience band (Python, no LLM)
  3c. Semantic check: role family / skills / domain (one batched Groq call)

Followed by final fit_score computation and tiering.
"""
from __future__ import annotations

import json
import logging
import re

from models.candidate import Candidate, EvidenceConfidence, FitBreakdown, SemanticCheckResult, Tier
from models.jd_run import Scorecard
from pipeline.llm_utils import DEFAULT_GROQ_MODEL, call_with_retry, get_llm_model, log_token_usage, parse_json_response

logger = logging.getLogger(__name__)

MODEL_NAME = DEFAULT_GROQ_MODEL

_EXPERIENCE_RE = re.compile(r"(\d+)\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)

TOP_THRESHOLD = 75
MEDIUM_THRESHOLD = 50

_US_STATE_ABBREVIATIONS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}
_US_ALIASES = {"united states", "usa", "u.s.", "u.s.a.", "us"}


def _is_within_country(candidate_location: str, country: str) -> bool | None:
    """Best-effort check for whether a candidate's location is within a
    country/region a remote role is restricted to. Returns None when we
    can't confidently tell (we only have real heuristics for the US today) -
    callers should treat None as "don't flag" rather than risk a false
    mismatch on a country/region we can't recognize.
    """
    country_norm = country.strip().lower()
    if country_norm not in _US_ALIASES:
        return None
    loc = candidate_location.strip().lower()
    if any(alias in loc for alias in _US_ALIASES):
        return True
    tail = loc.split(",")[-1].strip().upper()
    return tail in _US_STATE_ABBREVIATIONS


# ---------------------------------------------------------------------------
# 3a. Evidence baseline gate
# ---------------------------------------------------------------------------

def _is_valid_url(url: str) -> bool:
    return bool(url) and url.strip().lower().startswith(("http://", "https://"))


def passes_evidence_gate(candidate: Candidate) -> bool:
    has_name = bool(candidate.name and candidate.name.strip())
    has_title_or_headline = bool(candidate.current_title) or (
        bool(candidate.headline) and len(candidate.headline.strip()) > 20
    )
    has_url = _is_valid_url(candidate.profile_url)
    return has_name and has_title_or_headline and has_url


# ---------------------------------------------------------------------------
# 3b. Structured checks
# ---------------------------------------------------------------------------

def apply_location_check(candidate: Candidate, scorecard: Scorecard) -> None:
    if scorecard.work_mode == "remote":
        if not scorecard.remote_geo_constraint or not candidate.location:
            candidate.location_flag = None
            return
        within = _is_within_country(candidate.location, scorecard.remote_geo_constraint)
        candidate.location_flag = within is False
        return

    if not scorecard.location or not candidate.location:
        candidate.location_flag = None
        return
    candidate.location_flag = scorecard.location.strip().lower() not in candidate.location.strip().lower()


def _parse_years_of_experience(candidate: Candidate) -> int | None:
    match = _EXPERIENCE_RE.search(candidate.headline or "")
    if match:
        return int(match.group(1))
    if candidate.work_history:
        return len(candidate.work_history)
    return None


def apply_experience_check(candidate: Candidate, scorecard: Scorecard) -> int:
    years = _parse_years_of_experience(candidate)
    if years is None:
        candidate.evidence_notes = (candidate.evidence_notes + " " if candidate.evidence_notes else "") + (
            "Years of experience could not be determined from available text."
        )
        return 0

    min_years = scorecard.experience_years_min
    max_years = scorecard.experience_years_max
    if min_years is None and max_years is None:
        return 0

    lo = min_years if min_years is not None else max_years
    hi = max_years if max_years is not None else min_years
    if lo <= years <= hi:
        return 20
    edge_distance = min(abs(years - lo), abs(years - hi))
    return 12 if edge_distance <= 1 else 5


# ---------------------------------------------------------------------------
# 3c. Semantic check (single batched Groq call)
# ---------------------------------------------------------------------------

_SEMANTIC_PROMPT_TEMPLATE = """JD Requirements:
- Role family: {role_title}
- Must-have skills: {must_have_skills}
- Domain: {domain}

For each candidate below, return an entry with:
- candidate_id
- role_family_match: "same" | "adjacent" | "different"
- role_family_score: 15 (same) | 8 (adjacent) | 0 (different)
- skills_found: list of must-have skills explicitly confirmed or adjacent
- skills_score: 0-40 (full credit per confirmed skill, half credit per adjacent)
- domain_match: true | false
- domain_score: 0-15

Candidates:
{candidates_json}

Return ONLY a JSON object of the form {{"results": [...]}}, where "results" is
a JSON array with one entry per candidate as described above. No explanation.
"""


def run_semantic_check(candidates: list[Candidate], scorecard: Scorecard) -> dict[str, SemanticCheckResult]:
    """One batched Groq call scoring role family, skills, and domain for all candidates.

    On failure (after one retry), returns an empty mapping; callers must treat
    missing entries as a 0-scored, flagged semantic check per the PRD's error
    handling rules.
    """
    if not candidates:
        return {}

    candidates_payload = [
        {
            "candidate_id": c.candidate_id,
            "headline": c.headline,
            "title": c.current_title or "",
        }
        for c in candidates
    ]

    prompt = _SEMANTIC_PROMPT_TEMPLATE.format(
        role_title=scorecard.role_title,
        must_have_skills=", ".join(scorecard.must_have_skills),
        domain=scorecard.domain or "not specified",
        candidates_json=json.dumps(candidates_payload, indent=2),
    )

    model = get_llm_model(MODEL_NAME)

    def _call():
        return model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )

    try:
        response = call_with_retry(_call, retries=1)
    except Exception as exc:  # noqa: BLE001
        logger.error("Semantic check failed after retry, skipping: %s", exc)
        return {}

    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        log_token_usage("groq", MODEL_NAME, usage.prompt_token_count, usage.candidates_token_count)

    try:
        data = parse_json_response(response.text)["results"]
        results = {item["candidate_id"]: SemanticCheckResult(**item) for item in data}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse semantic check response, skipping: %s", exc)
        return {}

    return results


# ---------------------------------------------------------------------------
# Step 4: Scoring + tiering
# ---------------------------------------------------------------------------

def tier_for_score(fit_score: int) -> Tier:
    if fit_score >= TOP_THRESHOLD:
        return "top"
    if fit_score >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def _evidence_confidence(candidate: Candidate) -> EvidenceConfidence:
    confirmed_fields = 0
    if candidate.current_title:
        confirmed_fields += 1
    if candidate.current_company:
        confirmed_fields += 1
    if candidate.work_history or candidate.skills_mentioned:
        confirmed_fields += 1
    if confirmed_fields >= 3:
        return "high"
    if confirmed_fields == 2:
        return "medium"
    return "low"


def score_and_tier(candidate: Candidate, semantic: SemanticCheckResult | None, experience_score: int) -> None:
    # education_score is always 0 in this build: no education data is extracted
    # anywhere in the discovery step, so there is nothing to score it against.
    education_score = 0

    skills_score = semantic.skills_score if semantic else 0
    role_family_score = semantic.role_family_score if semantic else 0
    domain_score = semantic.domain_score if semantic else 0

    if semantic is None:
        candidate.evidence_notes = (candidate.evidence_notes + " " if candidate.evidence_notes else "") + (
            "Semantic check unavailable; role family, skills, and domain scores default to 0."
        )

    if semantic:
        candidate.skills_mentioned = semantic.skills_found

    candidate.fit_breakdown = FitBreakdown(
        skills_score=skills_score,
        experience_score=experience_score,
        role_family_score=role_family_score,
        domain_score=domain_score,
        education_score=education_score,
    )
    fit_score = skills_score + experience_score + role_family_score + domain_score + education_score
    candidate.fit_score = max(0, min(100, fit_score))
    candidate.tier = tier_for_score(candidate.fit_score)
    candidate.evidence_confidence = _evidence_confidence(candidate)


def filter_and_tier(candidates: list[Candidate], scorecard: Scorecard) -> tuple[list[Candidate], list[Candidate]]:
    """Run 3a -> 3b -> 3c -> scoring. Returns (scored_candidates, insufficient_evidence)."""
    survivors: list[Candidate] = []
    insufficient: list[Candidate] = []

    for candidate in candidates:
        if passes_evidence_gate(candidate):
            survivors.append(candidate)
        else:
            candidate.tier = "insufficient_evidence"
            insufficient.append(candidate)

    experience_scores: dict[str, int] = {}
    for candidate in survivors:
        apply_location_check(candidate, scorecard)
        experience_scores[candidate.candidate_id] = apply_experience_check(candidate, scorecard)

    semantic_results = run_semantic_check(survivors, scorecard)

    for candidate in survivors:
        score_and_tier(
            candidate,
            semantic_results.get(candidate.candidate_id),
            experience_scores[candidate.candidate_id],
        )

    logger.info(
        "Filter & tier complete: %d survivors, %d insufficient_evidence",
        len(survivors), len(insufficient),
    )
    return survivors, insufficient
