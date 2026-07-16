const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // response had no JSON body
    }
    throw new Error(detail);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res.text();
}

export const api = {
  createRun: (jdText) =>
    request("/runs", { method: "POST", body: JSON.stringify({ jd_text: jdText }) }),
  listRuns: () => request("/runs"),
  getRun: (runId) => request(`/runs/${runId}`),
  getShortlist: (runId) => request(`/runs/${runId}/shortlist`),
  reportUrl: (runId) => `${BASE}/runs/${runId}/report`,
  submitFeedback: (payload) =>
    request("/feedback", { method: "POST", body: JSON.stringify(payload) }),
  getFeedback: (runId) => request(`/feedback/${runId}`),
};
