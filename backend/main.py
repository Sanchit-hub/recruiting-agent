"""FastAPI application: routes + background pipeline orchestration."""
from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from db.mongo import (  # noqa: E402
    candidates_collection,
    check_connection,
    ensure_indexes,
    feedback_collection,
    jd_runs_collection,
)
from models.candidate import Candidate  # noqa: E402
from models.feedback import FeedbackCreate, FeedbackRecord  # noqa: E402
from models.jd_run import JDRun, JDRunCreate  # noqa: E402
from pipeline import deep_research, discovery, filter_tier, jd_parser, output_writer  # noqa: E402

MIN_JD_LENGTH = 50


@asynccontextmanager
async def lifespan(app: FastAPI):
    if check_connection():
        ensure_indexes()
    else:
        logger.warning("MongoDB unavailable at startup; will retry per-request.")
    yield


app = FastAPI(title="AI Recruiting Sourcing Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_db() -> None:
    if not check_connection():
        raise HTTPException(status_code=503, detail="Database unavailable.")


def _update_run(jd_run_id: str, **fields) -> None:
    jd_runs_collection().update_one({"jd_run_id": jd_run_id}, {"$set": fields})


# ---------------------------------------------------------------------------
# Pipeline orchestration (runs as a FastAPI background task)
# ---------------------------------------------------------------------------

def run_pipeline(jd_run_id: str, jd_text: str) -> None:
    try:
        _update_run(jd_run_id, status_detail="parsing_jd")
        scorecard = jd_parser.parse_jd(jd_text)
        _update_run(jd_run_id, scorecard=scorecard.model_dump(), status_detail="discovering")

        def _on_discovery_progress(count: int) -> None:
            _update_run(jd_run_id, total_discovered=count)

        candidates = discovery.discover_candidates(
            scorecard, jd_run_id, on_progress=_on_discovery_progress
        )

        if not candidates:
            _update_run(
                jd_run_id,
                status="failed",
                status_detail="failed",
                error="No candidates found. Try broadening the JD.",
            )
            return

        _update_run(jd_run_id, total_discovered=len(candidates), status_detail="filtering")
        survivors, insufficient = filter_tier.filter_and_tier(candidates, scorecard)

        _update_run(jd_run_id, status_detail="researching")
        deep_research.run_deep_research(survivors, scorecard)

        _update_run(jd_run_id, status_detail="writing_output")
        top = [c for c in survivors if c.tier == "top"]
        medium = [c for c in survivors if c.tier == "medium"]
        low = [c for c in survivors if c.tier == "low"]

        shortlist_json = output_writer.build_shortlist_json(
            jd_run_id, scorecard, len(candidates), len(survivors), top, medium, low, insufficient
        )
        markdown_text = output_writer.render_markdown(shortlist_json)
        json_path, md_path = output_writer.write_output(jd_run_id, shortlist_json, markdown_text)

        now = datetime.now(timezone.utc).isoformat()
        all_candidates = survivors + insufficient
        for candidate in all_candidates:
            candidate.created_at = now
        if all_candidates:
            candidates_collection().insert_many([c.model_dump() for c in all_candidates])

        _update_run(
            jd_run_id,
            status="completed",
            status_detail="done",
            total_shortlisted=len(survivors),
            output_path=md_path,
            output_json_path=json_path,
        )
        logger.info("Pipeline completed for jd_run_id=%s", jd_run_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed for jd_run_id=%s", jd_run_id)
        _update_run(jd_run_id, status="failed", status_detail="failed", error=str(exc))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    if not check_connection():
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return {"status": "ok"}


@app.post("/api/runs", status_code=202)
def create_run(payload: JDRunCreate, background_tasks: BackgroundTasks):
    jd_text = payload.jd_text.strip()
    if len(jd_text) < MIN_JD_LENGTH:
        raise HTTPException(status_code=400, detail="Please provide a complete job description.")

    _require_db()

    run = JDRun(created_at=datetime.now(timezone.utc).isoformat(), jd_raw_text=jd_text, status="running")
    jd_runs_collection().insert_one(run.model_dump())

    background_tasks.add_task(run_pipeline, run.jd_run_id, jd_text)
    return {"jd_run_id": run.jd_run_id}


@app.get("/api/runs")
def list_runs():
    _require_db()
    runs = list(jd_runs_collection().find({}, {"_id": 0}).sort("created_at", -1))
    return runs


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    _require_db()
    run = jd_runs_collection().find_one({"jd_run_id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


@app.get("/api/runs/{run_id}/shortlist")
def get_shortlist(run_id: str):
    _require_db()
    run = jd_runs_collection().find_one({"jd_run_id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run["status"] != "completed":
        raise HTTPException(status_code=409, detail=f"Run is not yet complete (status={run['status']}).")

    json_path = run.get("output_json_path")
    if not json_path or not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Shortlist output not found.")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/runs/{run_id}/report")
def get_report(run_id: str):
    _require_db()
    run = jd_runs_collection().find_one({"jd_run_id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    md_path = run.get("output_path")
    if not md_path or not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(md_path, media_type="text/markdown", filename=f"shortlist_{run_id}.md")


@app.post("/api/feedback", status_code=201)
def submit_feedback(payload: FeedbackCreate):
    _require_db()
    record = FeedbackRecord(
        **payload.model_dump(),
        feedback_given_at=datetime.now(timezone.utc).isoformat(),
    )
    feedback_collection().insert_one(record.model_dump())
    return record.model_dump()


@app.get("/api/feedback/{run_id}")
def get_feedback_for_run(run_id: str):
    _require_db()
    records = list(feedback_collection().find({"jd_run_id": run_id}, {"_id": 0}))
    return records
