import { useEffect, useState } from "react";
import { ArrowLeft, Mail, Shield, Trash2, UserRound, ClipboardList } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteAdminUser, getAdminUser, updateAdminUser } from "../../api";
import AdminLoadingState from "../components/admin/AdminLoadingState";

export default function AdminUserProfilePage() {
  const { userId } = useParams();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { getAdminUser(userId).then(setUser).catch((err) => setError(err.message)); }, [userId]);
  if (error) return <main className="admin-overview-page"><p role="alert">{error}</p></main>;
  if (!user) return <AdminLoadingState label="Loading user profile…" />;
  const save = async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); setUser(await updateAdminUser(userId, { full_name: form.get("full_name"), role: form.get("role"), account_status: form.get("account_status") })); };
  const remove = async () => { if (window.confirm("Delete this user account?")) { await deleteAdminUser(userId); navigate("/admin/users"); } };
  return <main className="admin-overview-page admin-user-profile-page">
    <button type="button" className="admin-back-button" onClick={() => navigate("/admin/users")}><ArrowLeft size={15} /> Back to users</button>
    <header className="admin-profile-header">
      <div className="admin-profile-avatar"><UserRound size={28} /></div>
      <div><p className="admin-eyebrow">ACCOUNT PROFILE</p><h1>{user.full_name || "Unnamed user"}</h1><p><Mail size={14} /> {user.email}</p></div>
      <span className={`admin-profile-status ${user.account_status}`}>{user.account_status}</span>
    </header>
    <form className="admin-profile-layout" onSubmit={save}>
      <section className="admin-card admin-profile-card"><div className="admin-card-title"><span className="admin-title-icon"><UserRound size={15} /></span><strong>Personal information</strong></div><label>Full name<input name="full_name" defaultValue={user.full_name} /></label><label>Email<input value={user.email} disabled /></label></section>
      <section className="admin-card admin-profile-card"><div className="admin-card-title"><span className="admin-title-icon"><Shield size={15} /></span><strong>Access and status</strong></div><label>Role<select name="role" defaultValue={user.role}><option value="user">User</option><option value="admin">Admin</option></select></label><label>Account status<select name="account_status" defaultValue={user.account_status}><option value="active">Active</option><option value="disabled">Disabled</option></select></label><dl className="admin-profile-meta"><div><dt>Created</dt><dd>{new Date(user.created_at).toLocaleString()}</dd></div><div><dt>Last login</dt><dd>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Never"}</dd></div></dl></section>
      <div className="admin-profile-actions"><button type="button" className="admin-secondary-button" onClick={() => navigate("/admin/users")}>Cancel</button><button type="submit" className="admin-primary-button">Save changes</button><button type="button" className="admin-danger-button" onClick={remove}><Trash2 size={15} /> Delete user</button></div>
    </form>
    {user.role === "user" && <section className="admin-card admin-user-related-card"><div className="admin-card-title"><strong>Conversation history</strong><span>{(user.conversations || []).length} conversations</span></div>{user.conversations?.length ? <div className="admin-user-conversation-list">{user.conversations.map((conversation) => <Link className="admin-user-conversation-item" key={conversation.conversation_id} to={`/admin/conversations/${conversation.conversation_id}`}><span>{conversation.conversation_id.slice(0, 8)}…</span><small>{conversation.turn_count} turns · {conversation.status}</small></Link>)}</div> : <p className="admin-subline">No conversations found for this user.</p>}</section>}
    {user.role === "user" && <section className="admin-card admin-user-related-card"><div className="admin-card-title"><strong><ClipboardList size={15} /> Applications</strong><span>{(user.applications || []).length} applications</span></div>{user.applications?.length ? <div className="admin-user-conversation-list">{user.applications.map((application) => <Link className="admin-user-conversation-item" key={application.application_id} to={`/admin/applications/${application.application_id}`}><span>{application.application_no || application.application_id.slice(0, 8) + "…"}</span><small>{application.admission_term || "No term"} · {application.status || "Unknown"}</small></Link>)}</div> : <p className="admin-subline">No applications found for this user.</p>}</section>}
  </main>;
}
