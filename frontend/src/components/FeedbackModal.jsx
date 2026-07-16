import { useState } from "react";
import { api } from "../lib/api.js";

const OUTCOMES = [
  { value: "shortlisted", label: "Shortlisted" },
  { value: "contacted", label: "Contacted" },
  { value: "interviewed", label: "Interviewed" },
  { value: "offer_made", label: "Offer Made" },
  { value: "offer_accepted", label: "Offer Accepted" },
  { value: "offer_declined", label: "Offer Declined" },
  { value: "rejected_by_us", label: "Rejected by Us" },
  { value: "no_response", label: "No Response" },
  { value: "withdrew", label: "Withdrew" },
];

const REJECTION_REASONS = [
  { value: "compensation_mismatch", label: "Compensation Mismatch" },
  { value: "role_not_fit", label: "Role Not a Fit" },
  { value: "competing_offer", label: "Competing Offer" },
  { value: "location_issue", label: "Location Issue" },
  { value: "last_minute_dropout", label: "Last-Minute Dropout" },
  { value: "unresponsive", label: "Unresponsive" },
  { value: "other", label: "Other" },
];

const STAGES = [
  { value: "shortlist", label: "Shortlist" },
  { value: "outreach", label: "Outreach" },
  { value: "screening", label: "Screening" },
  { value: "interview", label: "Interview" },
  { value: "offer", label: "Offer" },
];

const REJECTION_OUTCOMES = new Set(["offer_declined", "rejected_by_us", "withdrew"]);
const NOTES_MAX_LENGTH = 300;

export default function FeedbackModal({ candidate, jdRunId, onClose, onSubmitted }) {
  const [outcome, setOutcome] = useState("shortlisted");
  const [rejectionReason, setRejectionReason] = useState("");
  const [stageAtExit, setStageAtExit] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const showRejectionReason = REJECTION_OUTCOMES.has(outcome);
  const showStageAtExit = outcome !== "shortlisted";

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const record = await api.submitFeedback({
        candidate_id: candidate.candidate_id,
        jd_run_id: jdRunId,
        outcome,
        rejection_reason: showRejectionReason && rejectionReason ? rejectionReason : null,
        stage_at_exit: showStageAtExit && stageAtExit ? stageAtExit : null,
        notes: notes.trim() || null,
      });
      onSubmitted(record);
    } catch (err) {
      setError(err.message);
      setIsSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Feedback for {candidate.name}</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label htmlFor="outcome" className="block text-sm font-medium text-slate-700">
              Outcome
            </label>
            <select
              id="outcome"
              value={outcome}
              onChange={(event) => setOutcome(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            >
              {OUTCOMES.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {showRejectionReason && (
            <div>
              <label htmlFor="rejection-reason" className="block text-sm font-medium text-slate-700">
                Rejection Reason
              </label>
              <select
                id="rejection-reason"
                value={rejectionReason}
                onChange={(event) => setRejectionReason(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                <option value="">Select a reason…</option>
                {REJECTION_REASONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {showStageAtExit && (
            <div>
              <label htmlFor="stage-at-exit" className="block text-sm font-medium text-slate-700">
                Stage at Exit
              </label>
              <select
                id="stage-at-exit"
                value={stageAtExit}
                onChange={(event) => setStageAtExit(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                <option value="">Select a stage…</option>
                {STAGES.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label htmlFor="notes" className="block text-sm font-medium text-slate-700">
              Notes
            </label>
            <textarea
              id="notes"
              rows={3}
              maxLength={NOTES_MAX_LENGTH}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            />
            <p className="mt-1 text-right text-xs text-slate-400">
              {notes.length}/{NOTES_MAX_LENGTH}
            </p>
          </div>

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? "Saving…" : "Submit"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
