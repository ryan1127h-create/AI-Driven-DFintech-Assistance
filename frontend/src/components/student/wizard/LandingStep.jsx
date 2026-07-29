import { useState } from "react";
import { Upload, FileText, ArrowRight, User, GraduationCap, MessageSquare } from "lucide-react";

const STEPS = [
  { n: 1, label: "Select profile and provide information" },
  { n: 2, label: "Confirm profile" },
  { n: 3, label: "Get recommendations" },
];

export default function LandingStep({ onAdvance, onOpenSettings, onSkip }) {
  const [stage, setStage] = useState("applicant");
  const [text, setText] = useState("");
  const [cvName, setCvName] = useState("");

  const submit = (e) => {
    e.preventDefault();
    onAdvance({ lifecycle_stage: stage, text, cvName });
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
        <div className="card p-5">
          <h2 className="font-display text-base font-semibold text-app-primary mb-3">
            1. Choose user type
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <RoleCard
              active={stage === "applicant"}
              onClick={() => setStage("applicant")}
              icon={User}
              title="Applicant"
              desc="Upload application materials, identify missing items, track application status, compare programmes, and get course/career guidance."
            />
            <RoleCard
              active={stage === "current"}
              onClick={() => setStage("current")}
              icon={GraduationCap}
              title="Current Student"
              desc="Skip application materials and generate course recommendations, skill strengthening, and career direction only."
            />
          </div>
        </div>

        <div className="card p-5">
          <h2 className="font-display text-base font-semibold text-app-primary mb-1">
            2. Enter your information or upload a CV
          </h2>
          <p className="text-xs text-app-muted mb-3">
            You can proceed with only the selected profile type and fill in details manually on the
            next page. If you paste a profile summary, the system will pre-fill some fields.
          </p>
          <label className="text-sm font-medium text-app-secondary">Profile summary</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            placeholder="Example: I majored in Computer Science, worked in banking for 2 years, come from India, want to become a fintech product manager, and plan to apply full-time."
            className="input mt-1.5 resize-none"
          />
        </div>

        <div className="card p-5">
          <h2 className="font-display text-base font-semibold text-app-primary mb-1">
            3. Upload CV (optional)
          </h2>
          <p className="text-xs text-app-muted mb-3">
            Supports .docx and .pdf files up to 5MB. Uploaded files are used to extract background
            information.
          </p>
          <label className="text-sm font-medium text-app-secondary">Choose CV file</label>
          <div className="mt-1.5 flex items-center gap-2">
            <label className="btn-outline cursor-pointer">
              <Upload size={14} />
              Choose file
              <input
                type="file"
                accept=".docx,.pdf"
                className="hidden"
                onChange={(e) => setCvName(e.target.files?.[0]?.name || "")}
              />
            </label>
            {cvName && (
              <span className="flex items-center gap-1.5 text-xs text-app-muted">
                <FileText size={12} /> {cvName}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <button type="submit" className="btn-primary">
            Next: confirm profile
            <ArrowRight size={16} />
          </button>
          <div className="flex items-center gap-3">
            <button type="button" onClick={onOpenSettings} className="btn-ghost text-xs">
              Credential settings
            </button>
            <button type="button" onClick={onSkip} className="btn-outline text-xs">
              <MessageSquare size={14} />
              Skip to chat
            </button>
          </div>
        </div>
        <p className="text-[11px] text-app-faint text-center">
          If DeepSeek is configured, fields will be extracted automatically. If not, you can still
          fill in the next page manually.
        </p>
      </form>
    </div>
  );
}

function RoleCard({ active, onClick, icon: Icon, title, desc }) {
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