"""Step 5: Deep research on top-tier candidates via Groq.

The PRD specifies GPT-5.4-mini for this step, but at the user's request this
build originally used Gemini (same provider/model as the rest of the
pipeline) to avoid an OpenAI billing/quota dependency, then switched to Groq
once the Gemini free-tier quota was exhausted. See llm_utils.py.

Runs one API call per top-tier candidate (sorted by fit_score descending,
capped at 15). Failures are isolated per-candidate: research_briefing stays
None and the candidate's tier/score from Step 4 is left untouched.
"""
from __future__ import annotations

import logging

from db.mongo import learned_patterns_collection
from models.candidate import Candidate, ResearchBriefing
from models.jd_run import Scorecard
from pipeline.filter_tier import tier_for_score
from pipeline.llm_utils import DEFAULT_GROQ_MODEL, call_with_retry, get_llm_model, log_token_usage, parse_json_response

logger = logging.getLogger(__name__)

MODEL_NAME = DEFAULT_GROQ_MODEL
DEEP_RESEARCH_CAP = 15
MIN_PATTERNS_FOR_CONTEXT = 20

_PROMPT_TEMPLATE = """You are a senior technical recruiter doing deep research on a candidate for a specific role.

JD Summary:
{scorecard_summary}

Candidate Profile:
Name: {name}
Current Title: {current_title}
Headline: {headline}
Profile: {profile_url}

{pattern_context}

Produce a structured research briefing with exactly these fields:
1. trajectory: 2-3 sentences on career direction and momentum
2. fit_reasoning: specific reasons this candidate fits or doesn't fit the JD (reference actual skills/experience)
3. red_flags: list of specific concerns (empty list if none)
4. moveability: assessment of how likely this person is to be open to this role and why
5. confirmed_signals: a flat JSON array of strings noting what you know for certain vs what you
   inferred, e.g. ["Confirmed: 5 years experience (stated in headline)", "Inferred: Strong AWS skills (based on job title)"].
   Do NOT return an object/dict for this field - it must be a flat array of strings.
6. fit_score_adjustment: integer -10 to +10 (suggest adjustment to base score if research reveals something significant)

Return ONLY valid JSON matching this schema. No preamble.
"""


def _scorecard_summary(scorecard: Scorecard) -> str:
    return "\n".join(
        [
            f"Role: {scorecard.role_title}",
            f"Must-have skills: {', '.join(scorecard.must_have_skills) or 'n/a'}",
            f"Nice-to-have skills: {', '.join(scorecard.nice_to_have_skills) or 'n/a'}",
            f"Experience: {scorecard.experience_years_min}-{scorecard.experience_years_max} years",
            f"Seniority: {scorecard.seniority or 'n/a'}",
            f"Domain: {scorecard.domain or 'n/a'}",
            f"Target companies: {', '.join(scorecard.target_companies) or 'n/a'}",
            f"Location: {scorecard.location or 'n/a'}",
        ]
    )


def _load_pattern_context() -> str:
    patterns = list(learned_patterns_collection().find({"active": True}))
    if len(patterns) < MIN_PATTERNS_FOR_CONTEXT:
        return ""
    lines = [f"Historical note from {len(patterns)} past hiring records:"]
    for p in patterns:
        lines.append(
            f"- {p.get('pattern_description', '')} "
            f"(acceptance_rate={p.get('acceptance_rate', 0):.0%}, "
            f"decline_rate={p.get('offer_decline_rate', 0):.0%}, "
            f"common dropout stage={p.get('most_common_dropout_stage', 'n/a')}, "
            f"n={p.get('sample_size', 0)})"
        )
    return "\n".join(lines)


def _select_top_candidates(candidates: list[Candidate]) -> list[Candidate]:
    top_tier = [c for c in candidates if c.tier == "top"]
    top_tier.sort(key=lambda c: c.fit_score, reverse=True)
    return top_tier[:DEEP_RESEARCH_CAP]


def _research_one(candidate: Candidate, scorecard_summary: str, pattern_context: str) -> None:
    prompt = _PROMPT_TEMPLATE.format(
        scorecard_summary=scorecard_summary,
        name=candidate.name,
        current_title=candidate.current_title or "unknown",
        headline=candidate.headline,
        profile_url=candidate.profile_url,
        pattern_context=pattern_context,
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
        logger.error("Deep research failed for candidate_id=%s: %s", candidate.candidate_id, exc)
        candidate.research_briefing = None
        return

    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        log_token_usage("groq", MODEL_NAME, usage.prompt_token_count, usage.candidates_token_count)

    try:
        data = parse_json_response(response.text)
        briefing = ResearchBriefing(**data)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse deep research response for candidate_id=%s: %s", candidate.candidate_id, exc)
        candidate.research_briefing = None
        return

    candidate.research_briefing = briefing
    adjustment = max(-10, min(10, briefing.fit_score_adjustment))
    candidate.fit_score = max(0, min(100, candidate.fit_score + adjustment))
    candidate.tier = tier_for_score(candidate.fit_score)


def run_deep_research(candidates: list[Candidate], scorecard: Scorecard) -> None:
    """Research top-tier candidates in place (mutates research_briefing/fit_score/tier)."""
    targets = _select_top_candidates(candidates)
    if not targets:
        logger.info("No top-tier candidates to deep-research.")
        return

    scorecard_summary = _scorecard_summary(scorecard)
    pattern_context = _load_pattern_context()

    logger.info("Running deep research on %d top-tier candidates.", len(targets))
    for candidate in targets:
        _research_one(candidate, scorecard_summary, pattern_context)
