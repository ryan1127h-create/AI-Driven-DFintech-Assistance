import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Briefcase, GraduationCap, User } from "lucide-react";
import { StepIndicator } from "./LandingStep";
import {
  FormField,
  PageHeader,
  Select,
  SubmitButton,
  TextInput,
} from "../apiWidgets";

const lifecycleOptions = [
  { value: "prospact", label: "Prospective student" },
  { value: "applicant", label: "Applicant" },
];
const degreeOptions = [
  { value: "", label: "Select degree" },
  { value: "bachelors", label: "Bachelor's" },
  { value: "masters", label: "Master's" },
  { value: "doctorate", label: "Doctorate" },
  { value: "other", label: "Other" },
];
const academicOptions = [
  { value: "", label: "Select field of study" },
  { value: "finance", label: "Finance" },
  { value: "cs_computing", label: "Computer Science & Computing" },
  { value: "engineering", label: "Engineering" },
  { value: "business", label: "Business" },
  { value: "other", label: "Other" },
];
const schoolTierOptions = [
  { value: "", label: "Select school tier" },
  { value: "tier_1", label: "Tier 1" },
  { value: "tier_2", label: "Tier 2" },
  { value: "tier_3", label: "Tier 3" },
  { value: "other", label: "Other" },
];
const levelOptions = [
  { value: "", label: "Select level" },
  { value: "none", label: "None" },
  { value: "basic", label: "Basic" },
  { value: "strong", label: "Strong" },
];
const roleOptions = [
  { value: "quant_risk", label: "Quantitative Risk" },
  { value: "data_analytics", label: "Data Analytics" },
  { value: "fintech_pm", label: "FinTech Product Management" },
  { value: "payments", label: "Payments" },
  { value: "digital_banking", label: "Digital Banking" },
  { value: "compliance_regtech", label: "Compliance & RegTech" },
];

function normaliseInitial(initial) {
  return {
    lifecycle_stage: initial?.lifecycle_stage === "applicant" ? "applicant" : "prospect",
    application_type: initial?.application_type || "",
    degree_level: initial?.degree_level || "",
    academic_background_std: initial?.academic_background_std || initial?.field_of_study || "",
    academic_background_raw: initial?.academic_background_raw || "",
    school_tier: initial?.school_tier || "",
    work_years: initial?.work_years ?? "",
    gmat: initial?.gmat ?? "",
    gre: initial?.gre ?? "",
    toefl: initial?.toefl ?? "",
    ielts: initial?.ielts ?? "",
    tech_level_std: initial?.tech_level_std || initial?.technical_proficiency || "",
    tech_level_raw: initial?.tech_level_raw || "",
    target_roles: Array.isArray(initial?.target_roles)
      ? initial.target_roles
      : initial?.target_role_raw
        ? initial.target_role_raw.split("/").map((role) => role.trim()).filter(Boolean)
        : initial?.target_role_std
          ? [initial.target_role_std]
          : [],
    target_role_std: initial?.target_role_std || "",
    target_role_raw: initial?.target_role_raw || "",
    target_industry_std: initial?.target_industry_std || "",
    completed_courses: Array.isArray(initial?.completed_courses)
      ? initial.completed_courses.join(", ")
      : initial?.completed_modules || "",
    finance_knowledge: initial?.finance_knowledge || "",
    cv_uploaded: Boolean(initial?.cvFile),
  };
}

export default function FormStep({ initial, onBack, onSave, loading, error }) {
  const [form, setForm] = useState(() => normaliseInitial(initial));

  useEffect(() => {
    setForm(normaliseInitial(initial));
  }, [initial]);

  const setField = (key, value) => setForm((previous) => ({ ...previous, [key]: value }));
  const isApplicant = form.lifecycle_stage === "applicant";

  const submit = (event) => {
    event.preventDefault();
    if (loading) return;

    const targetRoles = form.target_roles.filter(Boolean);
    onSave({
      ...form,
      target_role_std: targetRoles[0] || null,
      target_role_raw: targetRoles.join(" / "),
      completed_courses: form.completed_courses
        .split(",")
        .map((course) => course.trim())
        .filter(Boolean),
    });
  };

  return (
    <div className="max-w-3xl mx-auto px-4 lg:px-0 py-8 animate-fadeIn">
      <PageHeader
        icon={User}
        title="Review Extracted Information"
        subtitle="Confirm your CV information or complete the profile manually before continuing."
      />
      <StepIndicator current={2} />

      <form onSubmit={submit} className="space-y-4 mt-6">
        {error && <div className="rounded-lg p-3 bg-red-500/10 border border-red-400/20 text-sm text-red-400">{error}</div>}

        <section className="card p-5 space-y-4">
          <SectionHeading icon={User} title="Identity" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FormField label="Lifecycle stage" required>
              <Select options={lifecycleOptions} value={form.lifecycle_stage} onChange={(event) => setField("lifecycle_stage", event.target.value)} />
            </FormField>
          </div>
        </section>

        <section className="card p-5 space-y-4">
          <SectionHeading icon={GraduationCap} title="Academic Background" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FormField label="Highest degree">
              <Select options={degreeOptions} value={form.degree_level} onChange={(event) => setField("degree_level", event.target.value)} />
            </FormField>
            <FormField label="Academic background">
              <Select options={academicOptions} value={form.academic_background_std} onChange={(event) => setField("academic_background_std", event.target.value)} />
            </FormField>
            <FormField label="Academic background details" hint="Use this when your field is not in the list.">
              <TextInput value={form.academic_background_raw} onChange={(event) => setField("academic_background_raw", event.target.value)} placeholder="e.g. BSc Computer Science" />
            </FormField>
            <FormField label="School tier">
              <Select options={schoolTierOptions} value={form.school_tier} onChange={(event) => setField("school_tier", event.target.value)} />
            </FormField>
            <FormField label="Completed courses" hint="Comma-separated course codes.">
              <TextInput value={form.completed_courses} onChange={(event) => setField("completed_courses", event.target.value)} placeholder="FT5005, IT5001" />
            </FormField>
          </div>
        </section>

        <section className="card p-5 space-y-4">
          <SectionHeading icon={Briefcase} title="Experience & Goals" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FormField label="Years of work experience" >
              <TextInput type="number" min="0" value={form.work_years} onChange={(event) => setField("work_years", event.target.value)} placeholder="e.g. 2" />
            </FormField>
            <FormField label="Technical proficiency">
              <Select options={levelOptions} value={form.tech_level_std} onChange={(event) => setField("tech_level_std", event.target.value)} />
            </FormField>
            <FormField label="Technical skills details">
              <TextInput value={form.tech_level_raw} onChange={(event) => setField("tech_level_raw", event.target.value)} placeholder="e.g. Python, SQL, machine learning" />
            </FormField>
            <FormField label="GMAT" hint="Optional, 200-800.">
              <TextInput type="number" min="200" max="800" value={form.gmat} onChange={(event) => setField("gmat", event.target.value)} placeholder="Optional" />
            </FormField>
            <FormField label="GRE" hint="Optional, 260-340.">
              <TextInput type="number" min="260" max="340" value={form.gre} onChange={(event) => setField("gre", event.target.value)} placeholder="Optional" />
            </FormField>
            <FormField label="TOEFL" hint="Optional, 0-120.">
              <TextInput type="number" min="0" max="120" value={form.toefl} onChange={(event) => setField("toefl", event.target.value)} placeholder="Optional" />
            </FormField>
            <FormField label="IELTS" hint="Optional, 0-9.">
              <TextInput type="number" min="0" max="9" step="0.5" value={form.ielts} onChange={(event) => setField("ielts", event.target.value)} placeholder="Optional" />
            </FormField>
            <FormField label="Target roles" hint="Select one or more roles.">
              <div className="flex flex-wrap gap-2">
                {roleOptions.map((role) => {
                  const selected = form.target_roles.includes(role.value);
                  return (
                    <button
                      key={role.value}
                      type="button"
                      onClick={() => setField("target_roles", selected
                        ? form.target_roles.filter((value) => value !== role.value)
                        : [...form.target_roles, role.value])}
                      className={`rounded-lg border px-3 py-2 text-sm transition ${selected
                        ? "bg-brand-500/20 border-brand-500 text-brand-300"
                        : "bg-app-hover border-app-input text-app-secondary"}`}
                    >
                      {role.label}
                    </button>
                  );
                })}
              </div>
            </FormField>
            <FormField label="Finance knowledge">
              <Select options={levelOptions} value={form.finance_knowledge} onChange={(event) => setField("finance_knowledge", event.target.value)} />
            </FormField>
            <FormField label="Target industry">
              <TextInput maxLength={100} value={form.target_industry_std} onChange={(event) => setField("target_industry_std", event.target.value)} placeholder="e.g. digital banking" />
            </FormField>
          </div>
        </section>

        <section className="card p-5 space-y-3">
          <SectionHeading icon={User} title="Profile source" />
          {form.cv_uploaded && <p className="text-xs text-emerald2-400">CV uploaded and used for extraction. You can correct any field above.</p>}
          {!form.cv_uploaded && <p className="text-xs text-app-muted">Profile details were entered manually.</p>}
        </section>

        <div className="flex items-center justify-between pt-2">
          <button type="button" onClick={onBack} className="btn-ghost text-sm" disabled={loading}><ArrowLeft size={14} /> Back</button>
          <SubmitButton loading={loading}><ArrowRight size={16} /> Finish and open chat</SubmitButton>
        </div>
      </form>
    </div>
  );
}

function SectionHeading({ icon: Icon, title }) {
  return (
    <div className="flex items-center gap-2 mb-1">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300"><Icon size={16} /></div>
      <h2 className="text-sm font-semibold text-app-primary">{title}</h2>
    </div>
  );
}
