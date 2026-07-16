import { useState } from "react";

const CONFIDENCE_STYLES = {
  high: "bg-emerald-100 text-emerald-800",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-red-100 text-red-800",
};

const OUTCOME_LABELS = {
  shortlisted: "Shortlisted",
  contacted: "Contacted",
  interviewed: "Interviewed",
  offer_made: "Offer Made",
  offer_accepted: "Offer Accepted",
  offer_declined: "Offer Declined",
  rejected_by_us: "Rejected by Us",
  no_response: "No Response",
  withdrew: "Withdrew",
};

const REJECTION_LABELS = {
  compensation_mismatch: "Compensation Mismatch",
  role_not_fit: "Role Not a Fit",
  competing_offer: "Competing Offer",
  location_issue: "Location Issue",
  last_minute_dropout: "Last-Minute Dropout",
  unresponsive: "Unresponsive",
  other: "Other",
};

function ScoreBadge({ score }) {
  const color = score >= 75 ? "bg-emerald-600" : score >= 50 ? "bg-amber-500" : "bg-slate-400";
  return (
    <div
      className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-lg font-bold text-white ${color}`}
    >
      {score}
    </div>
  );
}

export default function CandidateCard({ candidate, feedback, onAddFeedback }) {
  const [expanded, setExpanded] = useState(false);
  const briefing = candidate.research_briefing;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <ScoreBadge score={candidate.fit_score} />
          <div>
            <h3 className="text-base font-semibold text-slate-900">{candidate.name}</h3>
            <p className="text-sm text-slate-600">
              {candidate.current_title || "Unknown title"}
              {candidate.current_company ? ` at ${candidate.current_company}` : ""}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  CONFIDENCE_STYLES[candidate.evidence_confidence] || "bg-slate-100 text-slate-700"
                }`}
              >
                {candidate.evidence_confidence} confidence
              </span>
              {candidate.location_flag && (
                <span className="rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-medium text-orange-800">
                  Location mismatch
                </span>
              )}
              <a
                href={candidate.profile_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs font-medium text-slate-500 underline hover:text-slate-700"
              >
                View profile
              </a>
            </div>
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-2">
          {feedback ? (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
              {OUTCOME_LABELS[feedback.outcome] || feedback.outcome}
              {feedback.rejection_reason ? ` · ${REJECTION_LABELS[feedback.rejection_reason]}` : ""}
            </span>
          ) : (
            <button
              type="button"
              onClick={() => onAddFeedback(candidate)}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Add Feedback
            </button>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="mt-3 text-xs font-medium text-slate-500 hover:text-slate-700"
      >
        {expanded ? "Hide details ▲" : "Show details ▼"}
      </button>

      {expanded && (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3 text-sm text-slate-700">
          {briefing ? (
            <>
              <p>
                <span className="font-semibold">Trajectory: </span>
                {briefing.trajectory}
              </p>
              <p>
                <span className="font-semibold">Fit Reasoning: </span>
                {briefing.fit_reasoning}
              </p>
              <p>
                <span className="font-semibold">Red Flags: </span>
                {briefing.red_flags?.length ? briefing.red_flags.join(", ") : "None identified"}
              </p>
              <p>
                <span className="font-semibold">Moveability: </span>
                {briefing.moveability}
              </p>
              <p>
                <span className="font-semibold">Confirmed Signals: </span>
                {briefing.confirmed_signals?.length ? briefing.confirmed_signals.join(", ") : "None recorded"}
              </p>
            </>
          ) : (
            <p className="italic text-slate-500">No deep research briefing available for this candidate.</p>
          )}
          {candidate.evidence_notes && (
            <p>
              <span className="font-semibold">Evidence Notes: </span>
              {candidate.evidence_notes}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
