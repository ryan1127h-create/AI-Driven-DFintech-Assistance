import { useEffect, useState } from "react";
import { ArrowLeft, Check, ClipboardList, Clock3, LockKeyhole, Mail, Shield, Trash2, UserRound } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteAdminUser, getAdminUser, updateAdminUser } from "../../api";
import AdminLoadingState from "../components/admin/AdminLoadingState";

const humanizeLabel = (value) => {
  const replacements = {
    ml_ai: "Machine Learning and Artificial Intelligence",
    gpa: "Grade Point Average",
    cv: "Curriculum Vitae",
    ai: "Artificial Intelligence",
    id: "Identifier",
    url: "Link",
    nus: "National University of Singapore",
  };
  const raw = String(value || "").toLowerCase();
  if (replacements[raw]) return replacements[raw];
  return raw.split("_").map((word) => replacements[word] || word).join(" ").replace(/\b\w/g, (letter) => letter.toUpperCase());
};

const humanizeValue = (value) => {
  const replacements = {
    machine_learning_ai: "Machine Learning and Artificial Intelligence",
    data_analytics: "Data Analytics",
    software_engineering: "Software Engineering",
    data_engineering: "Data Engineering",
    first_class_equiv: "First Class Equivalent",
    self_family: "Self-funded / Family",
    social_media: "Social Media",
    thesis_only: "Thesis Only",
    full_time: "Full-time",
    part_time: "Part-time",
    south_asia: "South Asia",
    cs_se: "Computer Science and Software Engineering",
    job_prospects: "Job Prospects",
    brand_ranking: "Brand Ranking",
    linear_algebra: "Linear Algebra",
    probability_statistics: "Probability and Statistics",
  };
  const normalized = String(value).trim();
  if (/^[A-Z]{2,3}$/.test(normalized)) return normalized;
  if (replacements[normalized.toLowerCase()]) return replacements[normalized.toLowerCase()];
  return normalized.split("_").map((word) => word ? word[0].toUpperCase() + word.slice(1).toLowerCase() : word).join(" ");
};

const formatProfileValue = (value) => {
  if (value == null || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.map((item) => formatProfileValue(item)).join(", ");
  if (typeof value === "object") return Object.entries(value).map(([key, item]) => `${humanizeLabel(key)}: ${formatProfileValue(item)}`).join(" · ");
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}(T|$)/.test(value)) return formatDate(value);
  if (typeof value === "string") return value.split(",").map((item) => humanizeValue(item)).join(", ");
  return String(value);
};

const statusMeta = {
  active: { label: "Active", dot: "🟢", tone: "active", guidance: "User can access all features." },
  suspended: { label: "Suspended", dot: "🟡", tone: "suspended", guidance: "User temporarily loses access." },
  disabled: { label: "Disabled", dot: "🔴", tone: "disabled", guidance: "User account is permanently restricted until reactivated." },
  pending: { label: "Pending", dot: "⚪", tone: "pending", guidance: "User has not completed account activation." },
};

const formatDate = (value, fallback = "Never") => value ? new Date(value).toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }) : fallback;

export default function AdminUserProfilePage() {
  const { userId } = useParams();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState("");
  const [activeTab, setActiveTab] = useState("account-status");
  useEffect(() => { getAdminUser(userId).then(setUser).catch((err) => setError(err.message)); }, [userId]);
  if (error) return <main className="admin-overview-page"><p role="alert">{error}</p></main>;
  if (!user) return <AdminLoadingState label="Loading user profile…" />;
  const currentStatus = statusMeta[user.account_status] || statusMeta.pending;
  const save = async (event) => {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    setSaving(true); setActionError(""); setSaved("");
    try { setUser({ ...user, ...(await updateAdminUser(userId, { account_status: form.get("account_status") })) }); setSaved("Account status updated."); }
    catch (err) { setActionError(err.message); } finally { setSaving(false); }
  };
  const remove = async () => {
    if (!window.confirm("Delete this user account? This also deletes their sign-in, profile and applications, and cannot be undone.")) return;
    setSaving(true); setActionError("");
    try { await deleteAdminUser(userId); navigate("/admin/users"); } catch (err) { setActionError(err.message); setSaving(false); }
  };
  return <main className="admin-overview-page admin-user-profile-page">
    <button type="button" className="admin-back-button" onClick={() => navigate("/admin/users")}><ArrowLeft size={15} /> Back to users</button>
    <header className="admin-profile-header">
      <div className="admin-profile-avatar">{(user.full_name || "U").slice(0, 1).toUpperCase()}</div>
      <div className="admin-profile-identity"><p className="admin-eyebrow">ACCOUNT PROFILE</p><h1>{user.full_name || "Unnamed user"}</h1><p><Mail size={14} /> {user.email}</p><div className="admin-profile-badges"><span className="admin-role-badge">{user.role === "admin" ? "Administrator" : "Applicant"}</span><span className={`admin-profile-status ${currentStatus.tone}`}><i />{currentStatus.label}</span></div></div>
    </header>
    <nav className="admin-profile-nav" aria-label="User profile sections" role="tablist"><button type="button" role="tab" aria-selected={activeTab === "account-status"} className={activeTab === "account-status" ? "selected" : ""} onClick={() => setActiveTab("account-status")}>Account status</button>{user.role === "user" && <><button type="button" role="tab" aria-selected={activeTab === "user-profile"} className={activeTab === "user-profile" ? "selected" : ""} onClick={() => setActiveTab("user-profile")}>User profile</button><button type="button" role="tab" aria-selected={activeTab === "applications"} className={activeTab === "applications" ? "selected" : ""} onClick={() => setActiveTab("applications")}>Applications</button></>}</nav>
    {activeTab === "account-status" && <form id="account-status" className="admin-profile-layout" onSubmit={save}>
      <section className="admin-card admin-profile-card readonly-card"><div className="admin-card-title"><span className="admin-title-icon"><UserRound size={15} /></span><strong>Personal information</strong><span className="admin-readonly-badge"><LockKeyhole size={11} /> Read only</span></div><p className="admin-readonly-note">These details are managed from the user profile and cannot be edited here.</p><label><span><LockKeyhole size={12} /> Full name</span><input className="admin-readonly-field" name="full_name" defaultValue={user.full_name} readOnly aria-readonly="true" /></label><label><span><LockKeyhole size={12} /> Email</span><input className="admin-readonly-field" value={user.email} disabled /></label><label><span><LockKeyhole size={12} /> Role</span><input className="admin-readonly-field" value={user.role === "admin" ? "Administrator" : "Applicant"} disabled /></label></section>
      <section id="account-status" className="admin-card admin-profile-card status-card"><div className="admin-card-title"><span className="admin-title-icon"><Shield size={15} /></span><strong>Account management</strong></div><p className="admin-status-note">Only account status can be changed from this page.</p><div className="admin-status-editor"><label>Account status<select name="account_status" defaultValue={user.account_status} className={`status-select ${currentStatus.tone}`}><option value="active">🟢 Active</option><option value="suspended">🟡 Suspended</option><option value="disabled">🔴 Disabled</option><option value="pending">⚪ Pending</option></select></label><p className="admin-status-guidance"><Check size={14} /> {currentStatus.guidance}</p></div></section>
      <section className="admin-card admin-profile-card metadata-card"><div className="admin-card-title"><span className="admin-title-icon"><Clock3 size={15} /></span><strong>Account information</strong></div><dl className="admin-profile-meta"><div><dt>Created</dt><dd>{formatDate(user.created_at)}</dd></div><div><dt>Last login</dt><dd>{formatDate(user.last_login_at)}</dd></div></dl></section>
      <div className="admin-profile-actions">{actionError && <p role="alert">{actionError}</p>}{saved && <p role="status">{saved}</p>}<button type="button" className="admin-secondary-button" onClick={() => navigate("/admin/users")}>Cancel</button><button type="submit" className="admin-primary-button" disabled={saving}>{saving ? "Saving…" : "Save status"}</button></div>
      <section className="admin-danger-zone"><div><strong>Delete user</strong><p>Permanently remove this account and all associated data.</p></div><button type="button" className="admin-danger-button" onClick={remove} disabled={saving}><Trash2 size={15} /> Delete user</button></section>
    </form>}
    {user.role === "user" && activeTab === "user-profile" && <section id="user-profile" className="admin-card admin-user-related-card admin-linked-profile-card"><div className="admin-card-title"><div className="admin-related-title"><UserRound size={16} /><strong>User profile</strong></div><span>{(user.profile || []).filter((field) => field.field_key !== "application_record").length} fields</span></div>{user.profile?.filter((field) => field.field_key !== "application_record").length ? <dl className="admin-linked-profile-grid">{user.profile.filter((field) => field.field_key !== "application_record").map((field) => <div key={field.field_key}><dt>{humanizeLabel(field.field_key)}</dt><dd>{formatProfileValue(field.value)}</dd></div>)}</dl> : <p className="admin-subline">No profile information has been completed.</p>}</section>}
    {user.role === "user" && activeTab === "applications" && <section id="applications" className="admin-card admin-user-related-card"><div className="admin-card-title"><div className="admin-related-title"><ClipboardList size={16} /><strong>Applications</strong></div><span>{(user.applications || []).length} applications</span></div>{user.applications?.length ? <div className="admin-user-conversation-list">{user.applications.map((application) => <Link className="admin-user-conversation-item" key={application.application_id} to={`/admin/applications/${application.application_id}`}><span>{application.application_no || application.application_id.slice(0, 8) + "…"}</span><small>{application.admission_term || "No term"} · {application.status || "Unknown"}</small></Link>)}</div> : <p className="admin-subline">No applications found for this user.</p>}</section>}
  </main>;
}
