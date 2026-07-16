import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";

const STATUS_STYLES = {
  running: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

function StatusBadge({ status }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
        STATUS_STYLES[status] || "bg-slate-100 text-slate-700"
      }`}
    >
      {status}
    </span>
  );
}

export default function RunList() {
  const [runs, setRuns] = useState([]);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api
      .listRuns()
      .then(setRuns)
      .catch((err) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return <p className="text-sm text-slate-500">Loading past runs…</p>;
  }

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="text-sm text-slate-600">
        No runs yet.{" "}
        <Link to="/" className="font-medium text-slate-900 underline">
          Start one
        </Link>
        .
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Past Runs</h1>
      <div className="mt-6 overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Date
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Role
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Candidates Found
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {runs.map((run) => (
              <tr key={run.jd_run_id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link to={`/runs/${run.jd_run_id}`} className="block text-sm text-slate-700">
                    {new Date(run.created_at).toLocaleString()}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <Link to={`/runs/${run.jd_run_id}`} className="block text-sm font-medium text-slate-900">
                    {run.scorecard?.role_title || "—"}
                  </Link>
                </td>
                <td className="px-4 py-3 text-sm text-slate-700">{run.total_discovered ?? 0}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={run.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
