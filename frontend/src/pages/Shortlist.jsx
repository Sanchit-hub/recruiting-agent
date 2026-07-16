import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api.js";
import PipelineStatus from "../components/PipelineStatus.jsx";
import CandidateCard from "../components/CandidateCard.jsx";
import FeedbackModal from "../components/FeedbackModal.jsx";

const POLL_INTERVAL_MS = 3000;

const TABS = [
  { key: "shortlist", label: "Top" },
  { key: "medium_tier", label: "Medium" },
  { key: "low_tier", label: "Low" },
  { key: "insufficient_evidence", label: "Insufficient Evidence" },
];

export default function Shortlist() {
  const { runId } = useParams();
  const [run, setRun] = useState(null);
  const [shortlist, setShortlist] = useState(null);
  const [feedbackByCandidate, setFeedbackByCandidate] = useState({});
  const [activeTab, setActiveTab] = useState("shortlist");
  const [feedbackTarget, setFeedbackTarget] = useState(null);
  const [error, setError] = useState("");

  const loadRun = useCallback(async () => {
    try {
      const data = await api.getRun(runId);
      setRun(data);
      return data;
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, [runId]);

  const loadCompletedData = useCallback(async () => {
    try {
      const [shortlistData, feedbackList] = await Promise.all([
        api.getShortlist(runId),
        api.getFeedback(runId),
      ]);
      setShortlist(shortlistData);
      setFeedbackByCandidate(
        Object.fromEntries(feedbackList.map((record) => [record.candidate_id, record]))
      );
    } catch (err) {
      setError(err.message);
    }
  }, [runId]);

  useEffect(() => {
    let cancelled = false;
    let intervalId;

    async function tick() {
      const data = await loadRun();
      if (cancelled || !data) return;
      if (data.status === "completed") {
        clearInterval(intervalId);
        loadCompletedData();
      } else if (data.status === "failed") {
        clearInterval(intervalId);
      }
    }

    tick();
    intervalId = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [loadRun, loadCompletedData]);

  const tabCandidates = useMemo(() => {
    if (!shortlist) return [];
    return shortlist[activeTab] || [];
  }, [shortlist, activeTab]);

  function handleFeedbackSubmitted(record) {
    setFeedbackByCandidate((prev) => ({ ...prev, [record.candidate_id]: record }));
    setFeedbackTarget(null);
  }

  if (error) {
    return <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>;
  }

  if (!run) {
    return <p className="text-sm text-slate-500">Loading run…</p>;
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">
        {run.scorecard?.role_title || "Sourcing Run"}
      </h1>

      {run.status !== "completed" && (
        <div className="mt-6">
          <PipelineStatus run={run} />
        </div>
      )}

      {run.status === "completed" && shortlist && (
        <div className="mt-6">
          <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3">
            <p className="text-sm text-slate-700">
              <span className="font-semibold">{shortlist.total_discovered}</span> discovered →{" "}
              <span className="font-semibold">{shortlist.total_after_filtering}</span> passed filtering →{" "}
              <span className="font-semibold">{shortlist.shortlist.length}</span> in top tier
            </p>
            <a
              href={api.reportUrl(runId)}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Download Report
            </a>
          </div>

          <div className="mt-4 flex gap-2 border-b border-slate-200">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`border-b-2 px-3 py-2 text-sm font-medium ${
                  activeTab === tab.key
                    ? "border-slate-900 text-slate-900"
                    : "border-transparent text-slate-500 hover:text-slate-700"
                }`}
              >
                {tab.label} ({shortlist[tab.key]?.length ?? 0})
              </button>
            ))}
          </div>

          <div className="mt-4 space-y-4">
            {tabCandidates.length === 0 && (
              <p className="text-sm text-slate-500">No candidates in this tier.</p>
            )}
            {tabCandidates.map((candidate) => (
              <CandidateCard
                key={candidate.candidate_id}
                candidate={candidate}
                feedback={feedbackByCandidate[candidate.candidate_id]}
                onAddFeedback={setFeedbackTarget}
              />
            ))}
          </div>
        </div>
      )}

      {feedbackTarget && (
        <FeedbackModal
          candidate={feedbackTarget}
          jdRunId={runId}
          onClose={() => setFeedbackTarget(null)}
          onSubmitted={handleFeedbackSubmitted}
        />
      )}
    </div>
  );
}
