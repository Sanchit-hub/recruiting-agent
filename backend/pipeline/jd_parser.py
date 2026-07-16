"""Step 1: JD -> scorecard + candidate path framings.

Single Groq call that returns both the structured scorecard and the
natural-language candidate path framings used to drive discovery.
"""
from __future__ import annotations

import logging

from models.jd_run import Scorecard
from pipeline.llm_utils import DEFAULT_GROQ_MODEL, call_with_retry, get_llm_model, log_token_usage, parse_json_response

logger = logging.getLogger(__name__)

MODEL_NAME = DEFAULT_GROQ_MODEL

_PROMPT_TEMPLATE = """You are an expert technical recruiter. Read the job description below and \
extract a structured scorecard plus candidate path framings.

Rules:
- Extract only what is explicitly stated or strongly implied in the JD.
- Do not invent requirements not in the JD.
- `candidate_paths` must be 2-3 natural language sentences (not boolean queries, not keywords).
- Each path should describe a different *type* of ideal candidate.
- `work_mode` is one of "onsite", "hybrid", or "remote":
  - "remote" if the JD says the role is remote, remote-friendly,
    remote-first, or work-from-anywhere.
  - "hybrid" if the JD describes a mix of in-office and remote days.
  - "onsite" otherwise (default).
- `remote_geo_constraint` is ONLY set when `work_mode` is "remote" AND the JD
  restricts who can apply by country/region (e.g. "remote within the US",
  "must be based in the EU", "remote, APAC only"). It captures that
  restriction (e.g. "United States"), not a city. Leave it null when the
  role is remote with no such restriction ("remote, work from anywhere"),
  or when work_mode is not "remote".
- `location` captures a plain city/office location: the required work
  location for onsite/hybrid roles, or an HQ/reference city mentioned
  alongside a remote role (informational only in that case - it is not a
  constraint on where remote candidates must be).
- Return ONLY valid JSON, no preamble, no markdown code blocks.

Examples of the work_mode / remote_geo_constraint / location distinction:
- "This role is fully remote, work from anywhere" -> work_mode="remote", remote_geo_constraint=null, location=null
- "Remote role, but you must be based in the United States" -> work_mode="remote", remote_geo_constraint="United States", location=null
- "Remote-first team; our HQ is in San Francisco" -> work_mode="remote", remote_geo_constraint=null, location="San Francisco, CA"
- "Hybrid, 3 days/week in our Austin office" -> work_mode="hybrid", remote_geo_constraint=null, location="Austin, TX"
- "Must work on-site in New York" -> work_mode="onsite", remote_geo_constraint=null, location="New York, NY"

Return JSON matching exactly this schema:
{{
  "role_title": "string",
  "must_have_skills": ["string"],
  "nice_to_have_skills": ["string"],
  "experience_years_min": integer or null,
  "experience_years_max": integer or null,
  "seniority": "string or null",
  "domain": "string or null",
  "target_companies": ["string"],
  "education_preference": "string or null",
  "location": "string or null",
  "work_mode": "onsite" or "hybrid" or "remote",
  "remote_geo_constraint": "string or null",
  "candidate_paths": ["string", "string"]
}}

Job Description:
\"\"\"
{jd_text}
\"\"\"
"""


def parse_jd(jd_text: str) -> Scorecard:
    """Parse raw JD text into a Scorecard via a single Groq call."""
    model = get_llm_model(MODEL_NAME)
    prompt = _PROMPT_TEMPLATE.format(jd_text=jd_text)

    def _call():
        return model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )

    response = call_with_retry(_call, retries=1)

    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        log_token_usage(
            "groq",
            MODEL_NAME,
            usage.prompt_token_count,
            usage.candidates_token_count,
        )

    data = parse_json_response(response.text)
    scorecard = Scorecard(**data)
    logger.info(
        "Parsed JD -> role=%s paths=%d must_have=%d",
        scorecard.role_title,
        len(scorecard.candidate_paths),
        len(scorecard.must_have_skills),
    )
    return scorecard
