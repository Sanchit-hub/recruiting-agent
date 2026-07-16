import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { extractTextFromFile } from "../lib/fileText.js";

const MIN_JD_LENGTH = 50;

export default function NewRun() {
  const [jdText, setJdText] = useState("");
  const [fileName, setFileName] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  async function handleFileChange(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setError("");
    setFileName(file.name);
    setIsExtracting(true);
    try {
      const text = await extractTextFromFile(file);
      setJdText(text.trim());
    } catch (err) {
      setError(`Could not read ${file.name}: ${err.message}`);
    } finally {
      setIsExtracting(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = jdText.trim();
    if (trimmed.length < MIN_JD_LENGTH) {
      setError("Please provide a complete job description.");
      return;
    }

    setError("");
    setIsSubmitting(true);
    try {
      const { jd_run_id: jdRunId } = await api.createRun(trimmed);
      navigate(`/runs/${jdRunId}`);
    } catch (err) {
      setError(err.message);
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold text-slate-900">Find Candidates</h1>
      <p className="mt-1 text-sm text-slate-600">
        Paste a job description or upload a file, and the agent will source, score, and research candidates.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div>
          <label htmlFor="jd-text" className="block text-sm font-medium text-slate-700">
            Job Description
          </label>
          <textarea
            id="jd-text"
            rows={16}
            className="mt-2 w-full rounded-lg border border-slate-300 p-4 text-sm text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            placeholder="Paste your Job Description here"
            value={jdText}
            onChange={(event) => setJdText(event.target.value)}
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Upload .txt or .pdf
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.pdf"
            className="hidden"
            onChange={handleFileChange}
          />
          {isExtracting && <span className="text-sm text-slate-500">Extracting text…</span>}
          {!isExtracting && fileName && <span className="text-sm text-slate-500">{fileName}</span>}
        </div>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting || isExtracting}
          className="rounded-md bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? "Starting…" : "Find Candidates"}
        </button>
      </form>
    </div>
  );
}
