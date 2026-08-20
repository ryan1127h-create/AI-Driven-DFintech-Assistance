import { useState } from "react";
import { Upload, FileText, ArrowRight, Pencil, MessageSquare } from "lucide-react";

const STEPS = [
  { n: 1, label: "Select profile and provide information" },
  { n: 2, label: "Confirm profile" },
];

export default function LandingStep({ onAdvance, onOpenSettings, onSkip, loading, error }) {
  const [mode, setMode] = useState(null);
  const [cvFile, setCvFile] = useState(null);
  const [cvName, setCvName] = useState("");

  const submit = (e) => {
    e.preventDefault();
    onAdvance({ cvFile: mode === "upload" ? cvFile : null });
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6 animate-fadeIn">
      <div className="text-center">
        <h1 className="font-display text-2xl font-bold text-app-primary">
          Select your profile type and get tailored guidance
        </h1>
        <p className="text-app-muted mt-2 text-sm">
          This MVP supports two flows: applicant and current student. Applicants receive material
          checks, application status, programme comparison, and course/career advice. Current
          students receive course planning, skill-gap, and career-path advice only.
        </p>
      </div>

      <StepIndicator current={1} />

      <form onSubmit={submit} className="space-y-6">
        {loading && (
          <div className="rounded-lg border border-app-subtle bg-app-hover p-3 text-sm text-app-primary flex items-center gap-2">
            <span className="h-4 w-4 rounded-full border-2 border-brand-300 border-t-transparent animate-spin" />
            Extracting profile data...
          </div>
        )}
        {error && (
          <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">
            {error}
          </div>
        )}
        <div className="card p-5">
          <h2 className="font-display text-base font-semibold text-app-primary mb-3">
            1. Choose how to provide your profile
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <ModeCard
              active={mode === "upload"}
              onClick={() => setMode("upload")}
              icon={Upload}
              title="Upload CV"
              desc="Let the AI extract your profile information from a PDF or Word CV."
            />
            <ModeCard
              active={mode === "manual"}
              onClick={() => setMode("manual")}
              icon={Pencil}
              title="Fill in manually"
              desc="Enter and confirm your profile information yourself."
            />
          </div>
        </div>

        {mode === "upload" && (
          <div className="card p-5">
            <h2 className="font-display text-base font-semibold text-app-primary mb-1">2. Upload your CV</h2>
            <p className="text-xs text-app-muted mb-3">Supports PDF and Word files. Your CV will be used to extract profile information.</p>
            <label className="text-sm font-medium text-app-secondary">Choose CV file</label>
            <div className="mt-1.5 flex items-center gap-2">
              <label className="btn-outline cursor-pointer">
                <Upload size={14} /> Choose file
                <input type="file" accept=".docx,.pdf" className="hidden" onChange={(e) => {
                  const file = e.target.files?.[0] || null;
                  setCvFile(file);
                  setCvName(file?.name || "");
                }} />
              </label>
              {cvName && <span className="flex items-center gap-1.5 text-xs text-app-muted"><FileText size={12} /> {cvName}</span>}
            </div>
          </div>
        )}

        <div className="flex items-center justify-between">
          {mode && (
            <button type="submit" className="btn-primary" disabled={loading || (mode === "upload" && !cvFile)}>
              {loading ? "Processing..." : mode === "upload" ? "Extract CV and confirm" : "Next: confirm profile"}
              <ArrowRight size={16} />
            </button>
          )}
          <div className="flex items-center gap-3">
            <button type="button" onClick={onSkip} className="btn-outline text-xs">
              <MessageSquare size={14} />
              Skip to chat
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

function ModeCard({ active, onClick, icon: Icon, title, desc }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-left rounded-xl p-4 border transition-all ${
        active
          ? "border-brand-400/40 bg-brand-500/10 ring-1 ring-brand-500/30"
          : "border-app-input bg-app-hover hover:border-brand-400/20"
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <div
          className={`flex h-8 w-8 items-center justify-center rounded-lg ${
            active ? "bg-brand-500 text-white" : "bg-brand-500/15 text-brand-300"
          }`}
        >
          <Icon size={16} />
        </div>
        <span className="font-display text-sm font-semibold text-app-primary">{title}</span>
      </div>
      <p className="text-xs text-app-muted leading-relaxed">{desc}</p>
    </button>
  );
}

export function StepIndicator({ current }) {
  return (
    <ol className="flex items-center gap-2 text-xs">
      {STEPS.map((s, i) => (
        <li key={s.n} className="flex items-center gap-2">
          <span
            className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-medium ${
              i < current - 1
                ? "bg-emerald2-500 text-white"
                : i === current - 1
                  ? "bg-brand-500 text-white"
                  : "bg-app-hover text-app-faint"
            }`}
          >
            {i < current - 1 ? "✓" : s.n}
          </span>
          <span className={i === current - 1 ? "text-app-primary font-medium" : "text-app-faint"}>
            {s.label}
          </span>
          {i < STEPS.length - 1 && <span className="w-8 h-px bg-app-subtle mx-1" />}
        </li>
      ))}
    </ol>
  );
}