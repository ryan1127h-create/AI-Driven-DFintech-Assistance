import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteAdminApplication, getAdminApplication, updateAdminApplication } from "../../api";
import AdminLoadingState from "../components/admin/AdminLoadingState";

// Mirrors the check constraint on sis.applications.status (and the backend's
// APPLICATION_STATUSES): every status must be listed, or saving an application
// whose status is missing here would silently overwrite it.
const APPLICATION_STATUSES = [["DRAFT", "Draft"], ["SUBMITTED", "Submitted"], ["UNDER_REVIEW", "Under review"], ["DOCS_REQUIRED", "Documents required"], ["WAITLIST", "Waitlisted"], ["OFFER", "Offer"], ["ACCEPTED", "Accepted"], ["REJECTED", "Rejected"]];

export default function AdminApplicationPage() {
  const { applicationId } = useParams(); const navigate = useNavigate(); const [app, setApp] = useState(null); const [error, setError] = useState(""); const [actionError, setActionError] = useState(""); const [saving, setSaving] = useState(false); const [saved, setSaved] = useState("");
  useEffect(() => { getAdminApplication(applicationId).then(setApp).catch((err) => setError(err.message)); }, [applicationId]);
  if (error) return <main className="admin-overview-page"><p role="alert">{error}</p></main>;
  if (!app) return <AdminLoadingState label="Loading application…" />;
  const completed = (app.checklist || []).filter((item) => item.submitted).length; const total = (app.checklist || []).length; const completion = total ? Math.round((completed / total) * 100) : 0;
  const save = async (event) => {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    setSaving(true); setActionError(""); setSaved("");
    try { setApp(await updateAdminApplication(applicationId, { status: data.get("status"), final_decision: data.get("final_decision") || null })); setSaved("Changes saved."); }
    catch (err) { setActionError(err.message); } finally { setSaving(false); }
  };
  const reset = (event) => event.currentTarget.form.reset();
  const remove = async () => {
    if (!window.confirm("Delete this application and its checklist and status history? This cannot be undone.")) return;
    setSaving(true); setActionError("");
    try { await deleteAdminApplication(applicationId); navigate("/admin/applications"); } catch (err) { setActionError(err.message); setSaving(false); }
  };
  return <main className="admin-overview-page"><button className="admin-back-button" type="button" onClick={() => navigate("/admin/applications")}>← Back to applications</button><header className="admin-shared-page-header"><p className="admin-eyebrow">APPLICATION DETAILS</p><h1>{app.application_no || "Application"}</h1><p>{app.user_id ? <Link className="admin-related-link" to={`/admin/users/${app.user_id}`}>{app.user_name || app.applicant_email || "View profile"}</Link> : app.applicant_email || "No applicant email"}</p></header><form className="admin-card admin-profile-card" onSubmit={save}><label>Status<select name="status" defaultValue={app.status || ""}>{APPLICATION_STATUSES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label>Final decision<input name="final_decision" defaultValue={app.final_decision || ""} /></label><div className="admin-profile-actions">{actionError && <p role="alert">{actionError}</p>}{saved && <p role="status">{saved}</p>}<button className="admin-secondary-button" type="button" onClick={reset}>Reset</button><button className="admin-primary-button" type="submit" disabled={saving}>{saving ? "Saving…" : "Save changes"}</button><button className="admin-danger-button" type="button" onClick={remove} disabled={saving}>Delete application</button></div></form><section className="admin-card admin-checklist-card"><div className="admin-checklist-header"><div><div className="admin-card-title"><strong>Application checklist</strong></div><p>Student-provided documents. Admin view only.</p></div><strong className="admin-checklist-count">{completed}/{total} complete</strong></div><div className="admin-progress-track"><span style={{ width: `${completion}%` }} /></div><div className="admin-checklist-list">{(app.checklist || []).map((item) => <div className={`admin-checklist-row ${item.submitted ? "submitted" : "pending"}`} key={item.id}><span className="admin-checklist-name">{item.item_key.replaceAll("_", " ")}</span><span className="admin-checklist-status">{item.submitted ? "Submitted" : "Pending"}</span></div>)}</div></section></main>;
}
