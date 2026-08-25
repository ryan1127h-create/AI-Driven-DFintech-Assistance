import { getProfile, updateProfile } from "../../api";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  User, GraduationCap, Briefcase, Award, Globe, Calendar, BookOpen,
  RefreshCw, Save, X, Pencil,
} from "lucide-react";
import { useApiCall, ErrorBanner, SuccessBanner, PageHeader, LoadingSpinner, FormField, TextInput, Select, SubmitButton } from "../components/student/apiWidgets";
import { cn } from "../utils/cn";

const lifecycleOptions = ["", "prospect", "applicant", "admitted", "enrolled", "alumni"];
const academicBgOptions = [
  { value: "", label: "Select Field of Study" },
  { value: "finance", label: "Finance" },
  { value: "cs_computing", label: "Computer Science & Computing" },
  { value: "engineering", label: "Engineering" },
  { value: "business", label: "Business" },
  { value: "other", label: "Other" },
];
const techLevelOptions = [
  { value: "", label: "Select Level" },
  { value: "none", label: "None" },
  { value: "basic", label: "Basic" },
  { value: "strong", label: "Strong" },
];
const targetRoleOptions = [
  { value: "", label: "Select Target Role" },
  { value: "quant_risk", label: "Quantitative Risk" },
  { value: "data_analytics", label: "Data Analytics" },
  { value: "fintech_pm", label: "FinTech Product Management" },
  { value: "payments", label: "Payments" },
  { value: "digital_banking", label: "Digital Banking" },
  { value: "compliance_regtech", label: "Compliance & RegTech" },
];
const schoolTierOptions = [
  { value: "", label: "Select School Tier" },
  { value: "tier_1", label: "Tier 1" },
  { value: "tier_2", label: "Tier 2" },
  { value: "tier_3", label: "Tier 3" },
  { value: "other", label: "Other" },
];
const roleLabelMap = Object.fromEntries(
  targetRoleOptions.map((r) => [r.value, r.label])
);

export default function ProfilePage() {
  const navigate = useNavigate();
  const { loading, error, call, setError } = useApiCall();
  const [profile, setProfile] = useState(null);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [saved, setSaved] = useState(false);

  const fetchProfile = async () => {
    const result = await call(() => getProfile());

    setProfile(result); // result can be object or null

    if (result === null) {
      setError(null);
    }
  };

  useEffect(() => { fetchProfile(); }, []);

  const startEdit = () => {
    setEditForm({ ...profile,
      target_role_raw:
        typeof profile.target_role_raw === "string"
        ? profile.target_role_raw
        .split("/")
        .map((s) => s.trim())
        .filter(Boolean)
        : profile.target_role_raw || [],
     });
    setEditing(true);
    setSaved(false);
    setError(null);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditForm({});
    fetchProfile();
  };

  const setField = (key, value) => setEditForm((prev) => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    const payload = {};
    for (const key of Object.keys(editForm)) {
      if (editForm[key] !== profile[key] && editForm[key] !== "" && editForm[key] !== null) {
        if (key === "completed_courses") {
          payload[key] = typeof editForm[key] === "string"
            ? editForm[key].split(",").map((s) => s.trim()).filter(Boolean)
            : editForm[key];
        } else if (["work_years", "gmat", "gre", "toefl", "intake_year"].includes(key)) {
          payload[key] = Number(editForm[key]);
        } else if (key === "ielts") {
          payload[key] = Number(editForm[key]);
        } else if (key === "target_role_raw") {
          payload[key] = Array.isArray(editForm[key])
            ? editForm[key].join(" / ")
            : editForm[key];
        } else {
          payload[key] = editForm[key];
        }
      }
    }
    if (Object.keys(payload).length === 0) {
      setEditing(false);
      return;
    }
    const result = await call(() => updateProfile(payload));
    if (result.ok) {
      setProfile(result.body);
      setEditing(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    }
  };

  if (loading && !profile) return <LoadingSpinner label="Loading profile..." />;

  if (!profile && !loading) {
    return (
      <div className="max-w-3xl mx-auto animate-fadeIn">
        <PageHeader icon={User} title="My Profile" subtitle="Your structured applicant profile." />
        {/* <ErrorBanner error={error} /> */}
        {/* <div className="card p-8 text-center">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-app-hover text-app-muted mb-4">
            <User size={28} />
          </div>
          <p className="text-sm font-medium text-app-primary mb-1">No profile yet</p>
          <p className="text-xs text-app-muted mb-4">
            Upload your CV to auto-generate a profile, or create one by editing.
          </p>
          <button onClick={fetchProfile} className="btn-outline text-xs">
            <RefreshCw size={14} /> Retry
          </button>
        </div>
         */}
         <div className="card p-8 text-center">
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-app-hover text-app-muted mb-4">
              <User size={28} />
            </div>

            <p className="text-sm font-medium text-app-primary mb-1">
              No profile yet
            </p>

            <p className="text-xs text-app-muted mb-4">
              Upload your CV and create your MSc DFT profile to unlock personalised recommendations.
            </p>

            <div className="flex justify-center gap-2">
              <button
                onClick={() => navigate("/app")}
                className="btn-primary"
              >
                Create Profile
              </button>

              <button
                onClick={fetchProfile}
                className="btn-outline"
              >
                <RefreshCw size={14} />
                Retry
              </button>
            </div>
          </div>
      </div>
    );
  }



  return (
    <div className="max-w-3xl mx-auto animate-fadeIn">
      <PageHeader icon={User} title="My Profile" subtitle="Your structured applicant profile from the AI backend." />

      <ErrorBanner error={error} />
      {saved && <SuccessBanner>Profile updated successfully.</SuccessBanner>}

      {/* Action bar */}
      <div className="flex items-center gap-2 mb-6">
        {editing ? (
          <>
            <SubmitButton loading={loading} onClick={handleSave}>
              <Save size={16} /> Save Changes
            </SubmitButton>
            <button onClick={cancelEdit} className="btn-ghost text-sm">
              <X size={14} /> Cancel
            </button>
          </>
        ) : (
          <>
            <button onClick={startEdit} className="btn-outline">
              <Pencil size={16} /> Edit Profile
            </button>
          </>
        )}
      </div>

      {editing ? (
        <EditView form={editForm} setField={setField} />
      ) : (
        <DisplayView profile={profile} />
      )}
    </div>
  );
}

function DisplayView({ profile }) {
  const sections = [
    {
      icon: User, title: "Identity", color: "bg-brand-500/15 text-brand-300",
      fields: [
        { label: "Lifecycle Stage", key: "lifecycle_stage" },
        { label: "Application Term", key: "application_term" },
        { label: "Intake Year", key: "intake_year" },
      ],
    },
    {
      icon: GraduationCap, title: "Academic Background", color: "bg-royal-500/15 text-royal-300",
      fields: [
        { label: "Academic Background (raw)", key: "academic_background_raw" },
        { label: "Academic Background (std)", key: "academic_background_std" },
        { label: "School Tier", key: "school_tier" },
      ],
    },
    {
      icon: Award, title: "Test Scores", color: "bg-amber-500/15 text-amber-300",
      fields: [
        { label: "GMAT", key: "gmat" },
        { label: "GRE", key: "gre" },
        { label: "TOEFL", key: "toefl" },
        { label: "IELTS", key: "ielts" },
      ],
    },
    {
      icon: Briefcase, title: "Experience & Goals", color: "bg-emerald2-500/15 text-emerald2-400",
      fields: [
        { label: "Work Years", key: "work_years" },
        { label: "Tech Level (raw)", key: "tech_level_raw" },
        { label: "Tech Level (std)", key: "tech_level_std" },
        { label: "Interested Career Roles", key: "target_role_raw" },
        { label: "Target Role", key: "target_role_std" },
        { label: "Target Industry (raw)", key: "target_industry_raw" },
        { label: "Target Industry (std)", key: "target_industry_std" },
      ],
    },
  ];

  return (
    <div className="space-y-4">
      {sections.map((sec) => {
        const Icon = sec.icon;
        const hasData = sec.fields.some((f) => profile[f.key] !== null && profile[f.key] !== undefined && profile[f.key] !== "");
        return (
          <div key={sec.title} className="card p-5">
            <div className="flex items-center gap-2 mb-4">
              <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", sec.color)}>
                <Icon size={16} />
              </div>
              <h3 className="text-sm font-semibold text-app-primary">{sec.title}</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {sec.fields.map((f) => (
                <FieldDisplay
                  key={f.key}
                  fieldKey={f.key}
                  label={f.label}
                  value={profile[f.key]}
                />
              ))}
            </div>
            {!hasData && (
              <p className="text-xs text-app-faint mt-2 italic">No data in this section yet.</p>
            )}
          </div>
        );
      })}

      {/* Completed courses */}
      <div className="card p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan2-500/15 text-cyan2-400">
            <BookOpen size={16} />
          </div>
          <h3 className="text-sm font-semibold text-app-primary">Completed Courses</h3>
        </div>
        {profile.completed_courses?.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {profile.completed_courses.map((c) => (
              <span key={c} className="chip border border-app-input bg-app-hover text-app-secondary text-xs">
                {c}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-xs text-app-faint italic">No completed courses recorded.</p>
        )}
      </div>

      {/* Raw JSON */}
      {/* <details className="card p-5">
        <summary className="text-sm font-medium text-app-secondary cursor-pointer">View raw JSON</summary>
        <pre className="mt-3 overflow-x-auto text-xs font-mono text-app-muted max-h-64 overflow-y-auto">
          {JSON.stringify(profile, null, 2)}
        </pre>
      </details> */}
    </div>
  );
}

function FieldDisplay({ fieldKey, label, value }) {
  const isEmpty =
    value === null ||
    value === undefined ||
    value === "";

  if (fieldKey === "target_role_raw") {
    const roles = Array.isArray(value)
      ? value
      : String(value || "")
          .split("/")
          .map((x) => x.trim())
          .filter(Boolean);

    return (
      <div className="rounded-lg p-3 bg-app-hover border border-app-soft">
        <p className="text-[10px] uppercase tracking-wider text-app-faint mb-2">
          {label}
        </p>

        {roles.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {roles.map((role) => (
              <span
                key={role}
                className="chip border border-app-input bg-app-hover"
              >
                {roleLabelMap[role] || role}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-app-faint italic">—</p>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-lg p-3 bg-app-hover border border-app-soft">
      <p className="text-[10px] uppercase tracking-wider text-app-faint mb-1">
        {label}
      </p>

      <p
        className={cn(
          "text-sm",
          isEmpty
            ? "text-app-faint italic"
            : "text-app-primary"
        )}
      >
        {isEmpty ? "—" : String(value)}
      </p>
    </div>
  );
}

function EditView({ form, setField }) {
  const toggleInterestRole = (roleValue) => {
    const current = Array.isArray(form.target_role_raw)
      ? form.target_role_raw
      : [];

    setField(
      "target_role_raw",
      current.includes(roleValue)
        ? current.filter((r) => r !== roleValue)
        : [...current, roleValue]
    );
  };


  const coursesStr = Array.isArray(form.completed_courses)
    ? form.completed_courses.join(", ")
    : form.completed_courses || "";

  return (
    <div className="space-y-4">
      {/* Identity */}
      <div className="card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-app-primary">Identity</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="Lifecycle Stage">
            <div className="px-3 py-2 rounded-lg bg-app-hover border border-app-soft text-app-secondary">
              {form.lifecycle_stage || "-"}
            </div>
          </FormField>
          <FormField label="Application Term">
            <TextInput type="text" maxLength={50} placeholder="e.g. Round 2" value={form.application_term || ""} onChange={(e) => setField("application_term", e.target.value)} />
          </FormField>
          <FormField label="Intake Year">
            <TextInput type="number" placeholder="e.g. 2026" value={form.intake_year || ""} onChange={(e) => setField("intake_year", e.target.value)} />
          </FormField>
        </div>
      </div>

      {/* Academic Background */}
      <div className="card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-app-primary">Academic Background</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="Academic Background (raw)" hint="Enter your latest completed degree, diploma or qualification. (max 300 chars)">
            <TextInput type="text" maxLength={300} placeholder="e.g. BSc Computer Science" value={form.academic_background_raw || ""} onChange={(e) => setField("academic_background_raw", e.target.value)} />
          </FormField>
          <FormField label="Academic Background (std)">
            <Select options={academicBgOptions} value={form.academic_background_std || ""} onChange={(e) => setField("academic_background_std", e.target.value)} />
          </FormField>
          <FormField label="School Tier" hint="Max 50 chars">
            <Select
              options={schoolTierOptions}
              value={form.school_tier || ""}
              onChange={(e) =>
                setField("school_tier", e.target.value)
              }
            />
          </FormField>
        </div>
      </div>

      {/* Test Scores */}
      <div className="card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-app-primary">Test Scores</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <FormField label="GMAT" hint="200–800">
            <TextInput type="number" min={200} max={800} placeholder="—" value={form.gmat || ""} onChange={(e) => setField("gmat", e.target.value)} />
          </FormField>
          <FormField label="GRE" hint="260–340">
            <TextInput type="number" min={260} max={340} placeholder="—" value={form.gre || ""} onChange={(e) => setField("gre", e.target.value)} />
          </FormField>
          <FormField label="TOEFL" hint="0–120">
            <TextInput type="number" min={0} max={120} placeholder="—" value={form.toefl || ""} onChange={(e) => setField("toefl", e.target.value)} />
          </FormField>
          <FormField label="IELTS" hint="0–9">
            <TextInput type="number" min={0} max={9} step={0.5} placeholder="—" value={form.ielts || ""} onChange={(e) => setField("ielts", e.target.value)} />
          </FormField>
        </div>
      </div>

      {/* Experience & Goals */}
      <div className="card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-app-primary">Experience & Goals</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="Work Years" hint="0–80">
            <TextInput type="number" min={0} max={80} placeholder="e.g. 3" value={form.work_years || ""} onChange={(e) => setField("work_years", e.target.value)} />
          </FormField>
          <FormField label="Tech Level (raw)" hint="Describe your technical skills, tools, programming languages, projects, etc. (max 300 chars)">
            <TextInput type="text" maxLength={300} placeholder="e.g. strong Python skills" value={form.tech_level_raw || ""} onChange={(e) => setField("tech_level_raw", e.target.value)} />
          </FormField>
          <FormField label="Tech Level (std)">
            <Select options={techLevelOptions} value={form.tech_level_std || ""} onChange={(e) => setField("tech_level_std", e.target.value)} />
          </FormField>
          <FormField
            label="Interested Career Roles"
            hint="Select one or more career interests"
          >
            <div className="flex flex-wrap gap-2">
              {targetRoleOptions.slice(1).map((role) => {
                const selected =
                  (form.target_role_raw || []).includes(role.value);

                return (
                  <button
                    key={role.value}
                    type="button"
                    onClick={() => toggleInterestRole(role.value)}
                    className={`px-3 py-2 rounded-lg border text-sm transition ${
                      selected
                        ? "bg-brand-500/20 border-brand-500 text-brand-300"
                        : "bg-app-hover border-app-input text-app-secondary"
                    }`}
                  >
                    {role.label}
                  </button>
                );
              })}
            </div>
          </FormField>
          <FormField label="Target Role">
            <Select options={targetRoleOptions} value={form.target_role_std || ""} onChange={(e) => setField("target_role_std", e.target.value)} />
          </FormField>
          {/* <FormField label="Target Industry (raw)" hint="Free text, max 300 chars">
            <TextInput type="text" maxLength={300} placeholder="e.g. Digital Banking" value={form.target_industry_raw || ""} onChange={(e) => setField("target_industry_raw", e.target.value)} />
          </FormField> */}
          <FormField label="Target Industry" hint="Free text, max 300 chars">
            <TextInput type="text" maxLength={300} placeholder="e.g. digital_banking" value={form.target_industry_std || ""} onChange={(e) => setField("target_industry_std", e.target.value)} />
          </FormField>
        </div>
      </div>

      {/* Completed Courses */}
      <div className="card p-5 space-y-3">
        <h3 className="text-sm font-semibold text-app-primary">Completed Courses</h3>
        <FormField label="Completed Courses" hint="Comma-separated, max 50 items">
          <TextInput type="text" placeholder="IS5452, CS5340, ..." value={coursesStr} onChange={(e) => setField("completed_courses", e.target.value)} />
        </FormField>
      </div>
    </div>
  );
}
