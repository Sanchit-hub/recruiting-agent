"""Step 2: Candidate discovery via the Exa API.

Runs one search per candidate path from the JD scorecard, falls back to Exa
deep search for any path that under-returns, deduplicates by profile URL, and
extracts a few structured fields from the raw text using simple heuristics
(no LLM involved in this step).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable
from uuid import uuid4

from exa_py import Exa

from models.candidate import Candidate
from models.jd_run import Scorecard

logger = logging.getLogger(__name__)

RESULTS_PER_PATH = 15
MAX_RESULTS_PER_PATH = 45
DEEP_SEARCH_THRESHOLD = 5

# Simple, non-exhaustive heuristic for location extraction from free text.
# Covers common global tech hubs; extend as needed.
KNOWN_CITIES = [
    "Bangalore", "Bengaluru", "Mumbai", "Delhi", "New Delhi", "Gurgaon", "Gurugram",
    "Hyderabad", "Pune", "Chennai", "Noida", "Kolkata", "Ahmedabad",
    "San Francisco", "New York", "Seattle", "Austin", "Boston", "Los Angeles",
    "Chicago", "Denver", "Atlanta", "Washington", "San Jose", "Palo Alto",
    "London", "Berlin", "Amsterdam", "Paris", "Dublin", "Madrid", "Lisbon",
    "Singapore", "Hong Kong", "Tokyo", "Sydney", "Melbourne", "Toronto",
    "Vancouver", "Dubai", "Tel Aviv", "Remote",
]

_TITLE_AT_COMPANY_RE = re.compile(r"^(?P<title>.*?)\s+(?:at|@)\s+(?P<company>.+)$", re.IGNORECASE)


def _get_client() -> Exa:
    return Exa(api_key=os.environ["EXA_API_KEY"])


def _safe_dict(obj: Any) -> dict[str, Any]:
    """Best-effort conversion of an Exa SDK result object into a JSON/BSON-safe dict."""
    raw = getattr(obj, "__dict__", {}) or {}
    try:
        return json.loads(json.dumps(raw, default=str))
    except (TypeError, ValueError):
        return {k: str(v) for k, v in raw.items()}


def _parse_name_title_company(title: str) -> tuple[str, str | None, str | None]:
    """Parse an Exa result title of the form 'Name | Title at Company'."""
    if not title:
        return "", None, None
    if "|" not in title:
        return title.strip(), None, None
    name_part, rest = title.split("|", 1)
    name = name_part.strip()
    rest = rest.strip()
    if not rest:
        return name, None, None
    match = _TITLE_AT_COMPANY_RE.match(rest)
    if match:
        return name, match.group("title").strip() or None, match.group("company").strip() or None
    return name, rest, None


def _parse_role_company_from_text(text: str) -> tuple[str | None, str | None]:
    """Fallback heuristic: Exa people-result text is typically markdown of the form
    '# Name\n\nTitle @ Company | skill • skill • skill\n\nCity, Country\n\n...'.
    Used when the result title is just a bare name with no '| Title at Company' pattern.
    """
    if not text:
        return None, None
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    lines = [line for line in lines if not line.startswith("#")]
    if not lines:
        return None, None
    role_line = lines[0].split("|", 1)[0].strip()
    if not role_line:
        return None, None
    match = _TITLE_AT_COMPANY_RE.match(role_line)
    if match:
        return match.group("title").strip() or None, match.group("company").strip() or None
    return role_line or None, None


def _extract_location(text: str) -> str | None:
    if not text:
        return None
    for city in KNOWN_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", text, re.IGNORECASE):
            return city
    return None


def _build_query(path: str, location: str | None) -> str:
    """Append location to the path framing so Exa's index filters by geography.

    If location is None, empty, or 'remote', no geography filter is added —
    remote roles have no location constraint.
    """
    if not location or not location.strip():
        return path
    if location.strip().lower() == "remote":
        return path
    return f"{path}, based in {location.strip()}"


def _search(client: Exa, query: str, *, num_results: int, deep: bool = False) -> list[Any]:
    kwargs: dict[str, Any] = dict(
        category="people",
        num_results=num_results,
        use_autoprompt=True,
        text=True,
    )
    if deep:
        kwargs["type"] = "deep"
    response = client.search_and_contents(query, **kwargs)
    return getattr(response, "results", []) or []


def _search_path(
    client: Exa, path: str, location: str | None, *, num_results: int, force_deep: bool
) -> list[Any]:
    query = _build_query(path, location)
    logger.info("Exa query: %r", query)
    results = _search(client, query, num_results=num_results, deep=force_deep)
    if not force_deep and len(results) < DEEP_SEARCH_THRESHOLD:
        logger.warning(
            "Path returned %d results (< %d), retrying with deep search: %s",
            len(results), DEEP_SEARCH_THRESHOLD, query,
        )
        deep_results = _search(client, query, num_results=num_results, deep=True)
        if deep_results:
            results = deep_results
    return results


def discover_candidates(
    scorecard: Scorecard,
    jd_run_id: str,
    on_progress: Callable[[int], None] | None = None,
    attempt: int = 1,
) -> list[Candidate]:
    """Run discovery across all candidate paths and return deduplicated candidates.

    If provided, on_progress is called with the cumulative raw result count
    after each path completes, so callers can surface live progress in the UI.

    `attempt` broadens the search on retries (the caller re-invokes this when
    an earlier attempt found no top-tier candidate): later attempts request
    more results per path, force Exa's deep search instead of only falling
    back to it on a low result count, and — from the third attempt on — drop
    the location filter entirely, since an overly narrow geography filter is
    a common reason a real match gets missed.
    """
    client = _get_client()
    if scorecard.work_mode == "remote":
        # A remote role's `location` (if any) is just an HQ/reference point,
        # not a search constraint. Only a stated geo restriction narrows it.
        location = scorecard.remote_geo_constraint
    else:
        location = scorecard.location
    if attempt > 2:
        location = None

    num_results = min(RESULTS_PER_PATH * attempt, MAX_RESULTS_PER_PATH)
    force_deep = attempt > 1

    all_results: list[tuple[Any, str]] = []

    for path in scorecard.candidate_paths:
        try:
            results = _search_path(
                client, path, location, num_results=num_results, force_deep=force_deep
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Exa search failed for path %r: %s", path, exc)
            continue
        logger.info("Path %r returned %d results", path, len(results))
        all_results.extend((result, path) for result in results)
        if on_progress is not None:
            on_progress(len(all_results))

    if not all_results:
        logger.warning(
            "All candidate paths returned 0 results for jd_run_id=%s (attempt %d)", jd_run_id, attempt
        )
        return []

    seen_urls: set[str] = set()
    candidates: list[Candidate] = []
    for result, path in all_results:
        url = getattr(result, "url", None)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        title_str = getattr(result, "title", "") or ""
        text = getattr(result, "text", "") or ""
        name, current_title, current_company = _parse_name_title_company(title_str)
        if not current_title:
            current_title, current_company = _parse_role_company_from_text(text)

        # The result body is markdown starting with a '# Name' heading; drop it
        # so the headline (used for evidence/experience checks) carries signal.
        body_text = re.sub(r"^#.*?\n+", "", text, count=1).strip()

        candidates.append(
            Candidate(
                candidate_id=str(uuid4()),
                jd_run_id=jd_run_id,
                name=name or title_str,
                profile_url=url,
                headline=body_text[:300] if body_text else "",
                source="exa",
                matched_path=path,
                raw_exa_data=_safe_dict(result),
                current_title=current_title,
                current_company=current_company,
                location=_extract_location(text or title_str),
                work_history=[],
                skills_mentioned=[],
            )
        )

    logger.info("Discovery produced %d deduplicated candidates for jd_run_id=%s", len(candidates), jd_run_id)
    return candidates