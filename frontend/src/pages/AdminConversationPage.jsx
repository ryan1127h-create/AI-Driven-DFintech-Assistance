import { useEffect, useMemo, useState } from "react";
import { Bot, UserRound } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getAdminConversation, getAdminUser } from "../../api";
import AdminLoadingState from "../components/admin/AdminLoadingState";

function readMessages(conversation) {
  const messages = [];
  const walk = (value) => {
    if (Array.isArray(value)) return value.forEach(walk);
    if (!value || typeof value !== "object") return;
    const data = value.data || value;
    if ((data.type === "human" || data.type === "ai") && data.content != null) messages.push({ type: data.type, content: String(data.content) });
    else Object.values(value).forEach(walk);
  };
  walk(conversation.archived_blocks); walk(conversation.raw_tail);
  return messages;
}

const dateTime = (value) => value ? new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "—";
const statusTone = (status) => ({ open: "open", resolved: "resolved", investigating: "investigating", critical: "critical" }[String(status || "").toLowerCase()] || "open");
const mailto = (email, subject) => `mailto:${encodeURIComponent(email || "")}?subject=${encodeURIComponent(subject)}`;
const MODULE_LABELS = { A: "Application and lifecycle", B: "Background", C: "Education", D: "Work experience", E: "Skills", F: "Career goals", G: "Goals and planning", H: "Programme choices", I: "Studies", J: "Career outcomes", K: "Account preferences", L: "Privacy and consent", M: "Derived insights" };
const displayLabel = (value) => MODULE_LABELS[value] || String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const displayValue = (value) => {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.map(displayValue).join(", ");
  if (typeof value === "object") return Object.entries(value).map(([key, item]) => `${displayLabel(key)}: ${displayValue(item)}`).join(" · ");
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}(T|$)/.test(value)) return new Date(value).toLocaleDateString([], { day: "2-digit", month: "short", year: "numeric" });
  return String(value).replaceAll("_", " ");
};
const profileGroups = (profile, lifecycleStage) => Object.entries((profile || []).filter((field) => field.field_key !== "application_record" && !(lifecycleStage === "current" && field.field_key === "current_modules")).reduce((groups, field) => { const module = field.module || "profile"; (groups[module] ||= []).push(field); return groups; }, {}));

export default function AdminConversationPage() {
  const { conversationId } = useParams(); const navigate = useNavigate(); const [conversation, setConversation] = useState(null); const [userDetails, setUserDetails] = useState(null); const [showUserProfile, setShowUserProfile] = useState(false); const [error, setError] = useState("");
  useEffect(() => { getAdminConversation(conversationId).then(setConversation).catch((err) => setError(err.message)); }, [conversationId]);
  useEffect(() => { if (conversation?.user_id) getAdminUser(conversation.user_id).then(setUserDetails).catch(() => setUserDetails(null)); }, [conversation?.user_id]);
  const messages = useMemo(() => conversation ? readMessages(conversation) : [], [conversation]);
  if (error) return <main className="admin-overview-page"><p role="alert">{error}</p></main>;
  if (!conversation) return <AdminLoadingState label="Loading conversation…" />;
  const cases = conversation.cases || [];
  const replySubject = `Follow-up regarding your support request – Case #${cases[0]?.shortId || conversation.conversation_id.slice(0, 8)}`;
  return <main className="admin-overview-page admin-conversation-details-page">
    <button className="admin-back-button" type="button" onClick={() => navigate("/admin/escalations")}>← Back to escalation cases</button>
    <header className="conversation-hero"><div><p className="admin-eyebrow">CONVERSATION DETAILS</p><h1>Conversation <span>{conversation.conversation_id.slice(0, 8)}…</span></h1></div><span className={`conversation-status-badge ${statusTone(conversation.status)}`}>{conversation.status || "Unknown"}</span></header>
    <div className="conversation-workspace"><div className="conversation-main-column">
      <section className="admin-card conversation-cases-card"><div className="conversation-section-heading"><div><p className="admin-eyebrow">ESCALATIONS</p><h2>Related cases</h2></div><span>{cases.length} total</span></div>{cases.length ? <div className="conversation-case-grid">{cases.map((item) => <Link className="conversation-case-card" key={item.id} to={`/admin/escalations?case=${item.id}`}><div className="conversation-case-top"><strong>#{item.shortId}</strong><span className={`conversation-status-badge ${statusTone(item.status)}`}>{item.status}</span></div><h3>{item.category}</h3><time>{dateTime(item.createdAt)}</time><span className="conversation-case-link">Open case →</span></Link>)}</div> : <div className="conversation-empty-state">No escalation cases are linked to this conversation.</div>}</section>
      <section className="admin-card admin-conversation-card conversation-transcript-card"><div className="conversation-section-heading"><div><p className="admin-eyebrow">ACTIVITY</p><h2>Conversation transcript</h2></div><span>{conversation.turn_count ?? messages.length} turns</span></div><div className="admin-chat-transcript">{messages.length ? messages.map((message, index) => <div className={`admin-chat-message ${message.type}`} key={`${message.type}-${index}`}><span className="admin-chat-avatar">{message.type === "human" ? <UserRound size={16} /> : <Bot size={16} />}</span><div className="admin-chat-content"><div className="conversation-message-meta"><strong>{message.type === "human" ? "User" : "AI assistant"}</strong></div>{message.type === "ai" ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown> : <p>{message.content}</p>}</div></div>) : <p className="admin-conversation-empty">No readable messages are available for this conversation.</p>}</div></section>
    </div><aside className="conversation-sidebar"><section className="admin-card conversation-side-card conversation-user-card"><p className="admin-eyebrow">USER INFORMATION</p><div className="conversation-user-profile"><span className="conversation-user-avatar">{(conversation.user_name || "U").slice(0, 1).toUpperCase()}</span><div><div className="conversation-user-name-row"><h2>{conversation.user_name || "Unknown user"}</h2>{userDetails && <span className="conversation-user-stage-tag">{displayValue(userDetails.lifecycle_stage)}</span>}</div><a href={conversation.user_email ? mailto(conversation.user_email, replySubject) : undefined}>{conversation.user_email || conversation.user_id || "No email available"}</a></div></div>{userDetails && <div className="conversation-user-actions">{conversation.user_email && <a className="conversation-reply-button" href={mailto(conversation.user_email, replySubject)}><span>✉</span> Reply via Outlook</a>}<button type="button" className="conversation-profile-link conversation-profile-button" onClick={() => setShowUserProfile(true)}>View user profile</button></div>}</section>{userDetails && userDetails.lifecycle_stage === "current" && <section className="admin-card conversation-side-card conversation-detail-card"><div className="conversation-section-heading"><div><p className="admin-eyebrow">SIS ENROLLMENT</p><h2>Enrolled courses</h2></div><span>{(userDetails.course_enrollments || []).length}</span></div>{userDetails.course_enrollments?.length ? <div className="admin-user-conversation-list">{userDetails.course_enrollments.map((course) => <div className="admin-user-conversation-item" key={course.id}><strong>{course.course_code || "—"}</strong><small>{course.term || "No term"} · {course.status || "Unknown"}</small></div>)}</div> : <p className="admin-subline">No course enrollments found in the SIS.</p>}</section>}</aside></div>{showUserProfile && userDetails && <div className="admin-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowUserProfile(false); }}><section className="admin-card admin-modal admin-modal-scroll conversation-profile-modal" role="dialog" aria-modal="true" aria-labelledby="conversation-profile-title"><button type="button" className="admin-modal-close" aria-label="Close user profile" onClick={() => setShowUserProfile(false)}>×</button><div className="conversation-profile-modal-header"><span className="conversation-profile-avatar">{(userDetails.full_name || "U").slice(0, 1).toUpperCase()}</span><div className="conversation-profile-identity"><p className="admin-eyebrow">USER PROFILE</p><h2 id="conversation-profile-title">{userDetails.full_name || "User profile"}</h2><p className="admin-subline">{userDetails.email}</p></div><span className="conversation-profile-stage">{displayValue(userDetails.lifecycle_stage)}</span></div><div className="conversation-profile-groups">{profileGroups(userDetails.profile, userDetails.lifecycle_stage).map(([module, fields]) => <section className="conversation-profile-group" key={module}><h3>{displayLabel(module)}</h3><dl className="conversation-profile-fields">{fields.map((field) => <div key={field.field_key}><dt>{field.label || displayLabel(field.field_key)}</dt><dd>{displayValue(field.value)}</dd></div>)}</dl></section>)}</div>{userDetails.lifecycle_stage === "current" && <section className="conversation-profile-group conversation-enrollment-group"><h3>Enrolled courses</h3>{userDetails.course_enrollments?.length ? <div className="conversation-profile-course-list">{userDetails.course_enrollments.map((course) => <div className="conversation-profile-course-row" key={course.id}><strong>{course.course_code || "—"}</strong><span>{course.term || "No term"}</span><span>{course.status || "Unknown"}</span><span>{course.credits ?? "—"} credits</span></div>)}</div> : <p className="admin-subline">No course enrollments found in the SIS.</p>}</section>}</section></div>}
  </main>;
}
