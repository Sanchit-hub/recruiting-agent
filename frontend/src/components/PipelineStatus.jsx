const STAGE_ORDER = ["parsing_jd", "discovering", "filtering", "researching", "writing_output", "done"];

function stageIcon(state) {
  if (state === "done") return "✔";
  if (state === "current") return "⏳";
  return "○";
}

function stageTextClass(state) {
  if (state === "done") return "text-emerald-700";
  if (state === "current") return "text-amber-700";
  return "text-slate-400";
}

function stateFor(currentIndex, stageIndex) {
  if (currentIndex > stageIndex) return "done";
  if (currentIndex === stageIndex) return "current";
  return "pending";
}

export default function PipelineStatus({ run }) {
  if (run.status === "failed") {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        Pipeline failed: {run.error || "Unknown error."}
      </div>
    );
  }

  const currentIndex = STAGE_ORDER.indexOf(run.status_detail || "parsing_jd");
  const pathCount = run.scorecard?.candidate_paths?.length;

  const jdParseState = stateFor(currentIndex, 0);
  const discoverState = stateFor(currentIndex, 1);
  const filterState = stateFor(currentIndex, 2);
  const researchState = stateFor(currentIndex, 3);

  const lines = [
    { label: "JD parsed", state: jdParseState },
    {
      label:
        jdParseState === "done" && pathCount
          ? `${pathCount} candidate path${pathCount === 1 ? "" : "s"} generated`
          : "Generating candidate paths",
      state: jdParseState,
    },
    {
      label:
        discoverState === "current"
          ? `Discovering candidates... (found ${run.total_discovered ?? 0} so far)`
          : "Discovering candidates",
      state: discoverState,
    },
    { label: "Filtering & tiering", state: filterState },
    { label: "Deep research", state: researchState },
  ];

  return (
    <ul className="space-y-1.5 rounded-lg border border-slate-200 bg-white p-4">
      {lines.map((line) => (
        <li key={line.label} className={`flex items-center gap-2 text-sm ${stageTextClass(line.state)}`}>
          <span>{stageIcon(line.state)}</span>
          <span>{line.label}</span>
        </li>
      ))}
    </ul>
  );
}
