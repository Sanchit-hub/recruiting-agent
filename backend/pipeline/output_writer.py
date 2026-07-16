"""Step 6: Output writer. Produces shortlist.json and a markdown report per run."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from models.candidate import Candidate
from models.jd_run import Scorecard

logger = logging.getLogger(__name__)

OUTPUT_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


def _candidate_to_dict(candidate: Candidate, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "candidate_id": candidate.candidate_id,
        "name": candidate.name,
        "current_title": candidate.current_title,
        "current_company": candidate.current_company,
        "profile_url": candidate.profile_url,
        "fit_score": candidate.fit_score,
        "fit_breakdown": candidate.fit_breakdown.model_dump(),
        "evidence_confidence": candidate.evidence_confidence,
        "evidence_notes": candidate.evidence_notes,
        "tier": candidate.tier,
        "location_flag": candidate.location_flag,
        "research_briefing": candidate.research_briefing.model_dump() if candidate.research_briefing else None,
    }


def _ranked(candidates: list[Candidate]) -> list[dict[str, Any]]:
    ordered = sorted(candidates, key=lambda c: c.fit_score, reverse=True)
    return [_candidate_to_dict(c, rank) for rank, c in enumerate(ordered, start=1)]


def build_shortlist_json(
    jd_run_id: str,
    scorecard: Scorecard,
    total_discovered: int,
    total_after_filtering: int,
    top: list[Candidate],
    medium: list[Candidate],
    low: list[Candidate],
    insufficient: list[Candidate],
) -> dict[str, Any]:
    return {
        "jd_run_id": jd_run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "role": scorecard.role_title,
        "total_discovered": total_discovered,
        "total_after_filtering": total_after_filtering,
        "shortlist": _ranked(top),
        "medium_tier": _ranked(medium),
        "low_tier": _ranked(low),
        "insufficient_evidence": _ranked(insufficient),
    }


def _render_candidate_section(candidate: dict[str, Any]) -> str:
    briefing = candidate.get("research_briefing")
    lines = [
        f"### {candidate['rank']}. {candidate['name']} — Score: {candidate['fit_score']}/100",
        f"**{candidate['current_title'] or 'Unknown title'}** | {candidate['evidence_confidence']} confidence",
        f"🔗 {candidate['profile_url']}",
        "",
    ]
    if briefing:
        red_flags = ", ".join(briefing.get("red_flags") or []) or "None identified"
        confirmed = ", ".join(briefing.get("confirmed_signals") or []) or "None recorded"
        lines += [
            f"**Trajectory:** {briefing.get('trajectory', '')}",
            f"**Fit Reasoning:** {briefing.get('fit_reasoning', '')}",
            f"**Red Flags:** {red_flags}",
            f"**Moveability:** {briefing.get('moveability', '')}",
            f"**Confirmed Signals:** {confirmed}",
        ]
    else:
        lines.append("_No deep research briefing available._")
    if candidate.get("evidence_notes"):
        lines.append(f"**Evidence Notes:** {candidate['evidence_notes']}")
    lines.append("")
    return "\n".join(lines)


def render_markdown(shortlist_json: dict[str, Any]) -> str:
    lines = [
        f"# Shortlist: {shortlist_json['role']}",
        f"Generated: {shortlist_json['generated_at']} | "
        f"{len(shortlist_json['shortlist']) + len(shortlist_json['medium_tier']) + len(shortlist_json['low_tier'])} "
        f"candidates shortlisted from {shortlist_json['total_discovered']} discovered",
        "",
    ]

    lines.append("## Top Candidates\n")
    if shortlist_json["shortlist"]:
        for candidate in shortlist_json["shortlist"]:
            lines.append(_render_candidate_section(candidate))
    else:
        lines.append("_None._\n")

    lines.append("## Medium Tier Candidates\n")
    if shortlist_json["medium_tier"]:
        for candidate in shortlist_json["medium_tier"]:
            lines.append(_render_candidate_section(candidate))
    else:
        lines.append("_None._\n")

    lines.append("## Low Tier Candidates\n")
    if shortlist_json["low_tier"]:
        for candidate in shortlist_json["low_tier"]:
            lines.append(_render_candidate_section(candidate))
    else:
        lines.append("_None._\n")

    insufficient = shortlist_json.get("insufficient_evidence") or []
    if insufficient:
        lines.append("## Insufficient Evidence\n")
        for candidate in insufficient:
            lines.append(f"- {candidate['name']} — {candidate['profile_url']}")
        lines.append("")

    return "\n".join(lines)


def write_output(jd_run_id: str, shortlist_json: dict[str, Any], markdown_text: str) -> tuple[str, str]:
    """Writes shortlist.json and report.md to backend/output/{jd_run_id}/. Returns (json_path, md_path)."""
    run_dir = os.path.join(OUTPUT_ROOT, jd_run_id)
    os.makedirs(run_dir, exist_ok=True)

    json_path = os.path.join(run_dir, "shortlist.json")
    md_path = os.path.join(run_dir, "report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(shortlist_json, f, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)

    logger.info("Wrote output for jd_run_id=%s to %s", jd_run_id, run_dir)
    return json_path, md_path
