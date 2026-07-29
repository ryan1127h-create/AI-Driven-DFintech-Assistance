import { useState, useEffect } from "react";
import { ArrowRight, ArrowLeft, Lock, Upload, FileText, X } from "lucide-react";
import {
  applicationTypes,
  degreeLevels,
  fields,
  proficiencies,
  roles,
  materials,
} from "../../../data/wizard";
import { StepIndicator } from "./LandingStep";

export default function FormStep({ initial, onBack, onGenerate, loading, error }) {
  const isApplicant = initial?.lifecycle_stage === "applicant";
  const [form, setForm] = useState(() => ({
    lifecycle_stage: initial?.lifecycle_stage || "applicant",
    application_type: initial?.application_type || "",
    degree_level: initial?.degree_level || "",
    field_of_study: initial?.field_of_study || "",
    work_years: initial?.work_years || "",
    country: initial?.country || "",
    technical_proficiency: initial?.technical_proficiency || "",
    finance_knowledge: initial?.finance_knowledge || "",
    target_roles: Array.isArray(initial?.target_roles) ? initial.target_roles : [],
    priority: initial?.priority || "role_fit",
    completed_modules: initial?.completed_modules || "",
    uploads: {},
  }));

  useEffect(() => {
    setForm((prev) => ({
      ...prev,
      lifecycle_stage: initial?.lifecycle_stage || "applicant",
      application_type: initial?.application_type || "",
      degree_level: initial?.degree_level || "",
      field_of_study: initial?.field_of_study || "",
      work_years: initial?.work_years || "",
      country: initial?.country || "",
      technical_proficiency: initial?.technical_proficiency || "",
      finance_knowledge: initial?.finance_knowledge || "",
      target_roles: Array.isArray(initial?.target_roles) ? initial.target_roles : [],
      priority: initial?.priority || "role_fit",
      completed_modules: initial?.completed_modules || "",
    }));
  }, [initial]);

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const toggleRole = (role) => {
    setForm((f) => ({
      ...f,
      target_roles: f.target_roles.includes(role)
        ? f.target_roles.filter((r) => r !== role)
        : [...f.target_roles, role],
    }));
  };

  const handleUpload = (key, file) => {
    setForm((f) => ({ ...f, uploads: { ...f.uploads, [key]: file } }));
  };

  const removeUpload = (key) => {
    setForm((f) => {
      const next = { ...f.uploads };
      delete next[key];
      return { ...f, uploads: next };
    });
  };

  const submit = (e) => {
    e.preventDefault();
    if (!loading) {
      onGenerate(form);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6 animate-fadeIn">
      <StepIndicator current={2} />

      <div className="text-center">
        <h1 className="font-display text-2xl font-bold text-app-primary">
          {isApplicant ? "Applicant profile confirmation" : "Current student profile confirmation"}
        </h1>
        <p className="text-app-muted mt-2 text-sm">
          {isApplicant
            ? "Please confirm your background, application goals, and upload actual application materials. The system checks missing items from uploaded files instead of assuming submission through checkboxes."
            : "You selected the current-student flow. Application fields and material uploads are locked; only undergraduate background, completed modules, and career goals are needed."}
        </p>
      </div>

      <form onSubmit={submit} className="space-y-6">
        {loading && (
          <div className="rounded-lg border border-app-subtle bg-app-hover p-3 text-sm text-app-primary flex items-center gap-2">
            <span className="h-4 w-4 rounded-full border-2 border-brand-300 border-t-transparent animate-spin" />
            Generating analysis...
          </div>
        )}
        <div className="card p-5">
          <h2 className="font-display text-base font-semibold text-app-primary mb-2">Identity</h2>
          <div className="flex items-center gap-2 text-xs text-app-muted">
            Current flow:
            <span className="font-medium text-app-primary">
              {isApplicant ? "Applicant" : "Current Student"}
            </span>
            <button type="button" onClick={onBack} className="text-brand-300 hover:underline ml-2">
              Change selection
            </button>
          </div>
        </div>

        <div className="card p-5 space-y-4">
          <h2 className="font-display text-base font-semibold text-app-primary">Basic background</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Application type" locked={!isApplicant} hint="Not required for current students.">
              <select
                className="input"
                value={form.application_type}
                disabled={!isApplicant}
                onChange={(e) => setField("application_type", e.target.value)}
              >
                <option value="">(Undecided)</option>
                {applicationTypes.map((a) => (
                  <option key={a.value} value={a.value}>{a.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Highest degree">
              <select
                className="input"
                value={form.degree_level}
                onChange={(e) => setField("degree_level", e.target.value)}
              >
                <option value="">(Select)</option>
                {degreeLevels.map((d) => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Undergraduate major / prior academic background">
              <select
                className="input"
                value={form.field_of_study}
                onChange={(e) => setField("field_of_study", e.target.value)}
              >
                <option value="">(Select)</option>
                {fields.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Years of work experience" locked={!isApplicant} hint="Not required for current students.">
              <input
                type="number"
                min="0"
                className="input"
                placeholder="e.g. 2"
                value={form.work_years}
                disabled={!isApplicant}
                onChange={(e) => setField("work_years", e.target.value)}
              />
            </Field>
            <Field label="Country/region (two-letter code, e.g. SG / IN)" locked={!isApplicant} hint="Not required for current students.">
              <input
                type="text"
                maxLength={2}
                className="input"
                placeholder="SG"
                value={form.country}
                disabled={!isApplicant}
                onChange={(e) => setField("country", e.target.value)}
              />
            </Field>
          </div>
        </div>

        <div className="card p-5 space-y-4">
          <h2 className="font-display text-base font-semibold text-app-primary">Skills and goals</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Technical proficiency">
              <select
                className="input"
                value={form.technical_proficiency}
                onChange={(e) => setField("technical_proficiency", e.target.value)}
              >
                <option value="">(Select)</option>
                {proficiencies.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Finance knowledge">
              <select
                className="input"
                value={form.finance_knowledge}
                onChange={(e) => setField("finance_knowledge", e.target.value)}
              >
                <option value="">(Select)</option>
                {proficiencies.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </Field>
          </div>

          <div>
            <label className="text-sm font-medium text-app-secondary">Target roles (multiple selection allowed)</label>
            <div className="mt-2 flex flex-wrap gap-2">
              {roles.map((r) => (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => toggleRole(r.value)}
                  className={`chip border transition ${
                    form.target_roles.includes(r.value)
                      ? "bg-brand-500/20 text-brand-300 border-brand-400/30"
                      : "bg-app-hover text-app-muted border-app-input hover:border-brand-400/20"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
          <Field label="Main priority for programme comparison" locked={!isApplicant} hint="Not needed for current students.">
            <select
              className="input"
              value={form.priority}
              disabled={!isApplicant}
              onChange={(e) => setField("priority", e.target.value)}
            >
              <option value="role_fit">Role fit</option>
              <option value="cost">Tuition cost (lower is better)</option>
              <option value="duration">Duration (shorter is better)</option>
            </select>
          </Field>
        </div>

        <div className={`card p-5 space-y-4 ${!isApplicant ? "opacity-50" : ""}`}>
          <h2 className="font-display text-base font-semibold text-app-primary flex items-center gap-2">
            Application material upload
            {!isApplicant && <Lock size={14} className="text-app-faint" />}
            <span className="text-xs font-normal text-app-muted">
              {isApplicant ? "required for applicants" : "not needed for current students"}
            </span>
          </h2>
          {isApplicant ? (
            <>
              <p className="text-xs text-app-muted">
                Supports PDF / Word / image files. The real NUS Graduate Admission System requires
                online material uploads in PDF, in English or with certified English translations.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {materials.map((m) => (
                  <UploadCard
                    key={m.key}
                    material={m}
                    file={form.uploads[m.key]}
                    onUpload={(file) => handleUpload(m.key, file)}
                    onRemove={() => removeUpload(m.key)}
                  />
                ))}
              </div>
            </>
            ) : (
              <p className="text-xs text-app-muted">
                This section is locked. You are already enrolled, so no application files are needed.
              </p>
            )}
        </div>

        <div className="card p-5 space-y-3">
          <h2 className="font-display text-base font-semibold text-app-primary flex items-center gap-2">
            Completed modules
            <span className="text-xs font-normal text-app-muted">
              {isApplicant ? "optional for applicants" : "important for current students"}
            </span>
          </h2>
          <p className="text-xs text-app-muted">
            Enter completed module codes to generate course planning and graduation progress.
            Example: BMD5301, IT5001, FT5005.
          </p>
          <input
            type="text"
            className="input"
            placeholder="BMD5301, IT5001, FT5005"
            value={form.completed_modules}
            onChange={(e) => setField("completed_modules", e.target.value)}
          />
        </div>

        <div className="flex items-center gap-3">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Generating..." : "Generate analysis"}
            <ArrowRight size={16} />
          </button>
          <button type="button" onClick={onBack} className="btn-ghost text-sm" disabled={loading}>
            <ArrowLeft size={14} />
            Change profile type
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children, locked, hint }) {
  return (
    <div className={locked ? "opacity-50" : ""}>
      <label className="text-sm font-medium text-app-secondary flex items-center gap-1">
        {locked && <Lock size={11} className="text-app-faint" />}
        {label}
      </label>
      <div className="mt-1.5" title={locked ? hint : ""}>
        {children}
      </div>
    </div>
  );
}

function UploadCard({ material, file, onUpload, onRemove }) {
  const pillClass = (req) =>
    req === "required"
      ? "bg-red-500/15 text-red-300 border-red-400/20"
      : req === "conditional"
        ? "bg-amber-500/15 text-amber-300 border-amber-400/20"
        : "bg-app-hover text-app-muted border-app-input";

  return (
    <div className="rounded-xl border border-app-input bg-app-hover p-3">
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-sm font-medium text-app-primary">{material.label}</span>
        <span className={`chip border ${pillClass(material.required)}`}>
          {material.required === "required" ? "Required" : material.required === "conditional" ? "Conditional" : "Optional"}
        </span>
      </div>
      <p className="text-[11px] text-app-muted mb-2">{material.hint}</p>
      {file ? (
        <div className="flex items-center gap-2 text-xs text-app-secondary">
          <FileText size={12} className="text-brand-300" />
          <span className="truncate flex-1">{file.name}</span>
          <button type="button" onClick={onRemove} className="text-app-faint hover:text-red-400">
            <X size={12} />
          </button>
        </div>
      ) : (
        <label className="btn-outline cursor-pointer text-xs w-full">
          <Upload size={12} />
          Upload
          <input
            type="file"
            accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
          />
        </label>
      )}
    </div>
  );
}
