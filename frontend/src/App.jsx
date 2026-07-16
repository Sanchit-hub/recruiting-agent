import { NavLink, Route, Routes } from "react-router-dom";
import NewRun from "./pages/NewRun.jsx";
import RunList from "./pages/RunList.jsx";
import Shortlist from "./pages/Shortlist.jsx";

const navLinkClass = ({ isActive }) =>
  `px-3 py-2 rounded-md text-sm font-medium ${
    isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
  }`;

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <span className="text-lg font-semibold text-slate-900">AI Recruiting Sourcing Agent</span>
          <nav className="flex gap-2">
            <NavLink to="/" end className={navLinkClass}>
              New Run
            </NavLink>
            <NavLink to="/runs" className={navLinkClass}>
              Past Runs
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        <Routes>
          <Route path="/" element={<NewRun />} />
          <Route path="/runs" element={<RunList />} />
          <Route path="/runs/:runId" element={<Shortlist />} />
        </Routes>
      </main>
    </div>
  );
}
