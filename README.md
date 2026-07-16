# AI Recruiting Sourcing Agent

An AI agent that takes a job description, sources candidates from the web via Exa,
scores and tiers them, runs deep research on the top matches, and presents a
ranked shortlist through a web UI. HR feedback on each candidate is stored in
MongoDB for future runs.

## Architecture

- **Backend:** FastAPI + a pipeline of Gemini (JD parsing, semantic scoring,
  and deep research on the top tier) → Exa (candidate discovery).
- **Frontend:** React (Vite) + Tailwind CSS.
- **Database:** MongoDB.

See `recruiting_agent_PRD.md` for the full design spec.

### Deviations from the PRD (both required — see below)

- **Gemini model:** the PRD specifies `gemini-2.5-flash`. That model returns
  `404 "no longer available to new users"` on newly created Google API keys,
  so this build uses `gemini-3.5-flash` instead (`DEFAULT_GEMINI_MODEL` in
  `backend/pipeline/llm_utils.py`) — confirmed working live.
- **Deep research model:** the PRD specifies OpenAI GPT-5.4-mini. At the
  user's request (to avoid a dependency on OpenAI billing/quota), Step 5 uses
  Gemini instead — same model/provider as the rest of the pipeline. See
  `backend/pipeline/deep_research.py`. The OpenAI SDK stays in
  `requirements.txt` only as a transitive dependency of `exa-py`; nothing in
  this codebase calls OpenAI directly anymore.

## Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB running locally on `27017`, or a `MONGODB_URI` pointing at a hosted
  instance (e.g. MongoDB Atlas)
- API keys: Google (Gemini), Exa. (An `OPENAI_API_KEY` slot remains in
  `.env.example` for parity with the PRD, but it is unused by this build.)

## Setup & Run

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GOOGLE_API_KEY, OPENAI_API_KEY, EXA_API_KEY, MONGODB_URI
uvicorn main:app --reload --port 8000
```

The API is served at `http://localhost:8000`, with interactive docs at
`http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

The Vite dev server proxies `/api/*` requests to `http://localhost:8000`, so
no separate CORS configuration is needed in development.

### MongoDB

```bash
# macOS via Homebrew
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

Or point `MONGODB_URI` in `backend/.env` at a hosted cluster.

## Using the app

1. Open `http://localhost:5173`.
2. Paste a job description (or upload a `.txt`/`.pdf`) and click **Find Candidates**.
3. Watch the pipeline run — JD parsing, discovery, filtering, deep research —
   with live status on the run page.
4. Review the ranked shortlist across Top / Medium / Low / Insufficient
   Evidence tabs, with fit scores, evidence confidence, and research briefings.
5. Click a candidate's profile link to view them on the source site.
6. After outreach, log feedback (outcome, rejection reason, stage, notes) on
   each candidate via **Add Feedback** — this is stored in MongoDB for future
   pipeline runs.
7. Download the generated markdown report from the run page, or find raw
   JSON/markdown output under `backend/output/{jd_run_id}/`.

## Notes on scope

Per the PRD, this build intentionally excludes: automated outreach, GitHub as
a source, cross-source identity resolution, a vector DB / caching layer,
additional source adapters beyond Exa, authentication, and deployment
tooling.

The `education_score` component of `fit_breakdown` is always `0` in this
build: no education data is extracted anywhere in the discovery step (Exa
result heuristics only cover title/company/location), so there is nothing to
score it against yet. Extending discovery to extract education signals is a
natural next step if education scoring is needed.

### Fixes made during live testing against real API keys

- **Exa SDK:** `exa_py.Exa.search()` does not return result text/content —
  only `search_and_contents()` does. `discovery.py` was updated accordingly.
- **Exa result shape:** Exa's people-search `title` field is just the
  person's name (not `"Name | Title at Company"` as the PRD's heuristic
  assumed); title/company are instead parsed from the first line of the
  result body text. See `_parse_role_company_from_text()` in `discovery.py`.
- **`openai` SDK version:** the PRD-pinned `openai==1.51.0` is incompatible
  with the currently-installed `httpx` (dropped the `proxies` kwarg);
  bumped to `1.109.1`.
- **`ResearchBriefing.confirmed_signals` schema drift:** the prompt's
  original phrasing ("list what you know for certain vs what you inferred")
  led Gemini to sometimes return `{"certain": [...], "inferred": [...]}`
  instead of a flat array, breaking `pydantic` validation. Fixed by (a)
  making the prompt explicit that a flat string array is required, and (b)
  adding a defensive `field_validator` on `ResearchBriefing` that flattens a
  dict-shaped response instead of failing, in case any model drifts again.
