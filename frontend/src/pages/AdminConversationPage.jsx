import { useEffect, useMemo, useState } from "react";
import { Bot, UserRound } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getAdminConversation } from "../../api";
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
const mailto = (email, subject = "Regarding your conversation with NUS DFinTech") => `mailto:${encodeURIComponent(email || "")}?subject=${encodeURIComponent(subject)}`;

export default function AdminConversationPage() {
  const { conversationId } = useParams(); const navigate = useNavigate(); const [conversation, setConversation] = useState(null); const [error, setError] = useState("");
  useEffect(() => { getAdminConversation(conversationId).then(setConversation).catch((err) => setError(err.message)); }, [conversationId]);
  const messages = useMemo(() => conversation ? readMessages(conversation) : [], [conversation]);
  if (error) return <main className="admin-overview-page"><p role="alert">{error}</p></main>;
  if (!conversation) return <AdminLoadingState label="Loading conversation…" />;
  const cases = conversation.cases || [];
  return <main className="admin-overview-page admin-conversation-details-page">
    <button className="admin-back-button" type="button" onClick={() => navigate("/admin/escalations")}>← Back to escalation cases</button>
    <header className="conversation-hero"><div><p className="admin-eyebrow">CONVERSATION DETAILS</p><h1>Conversation <span>{conversation.conversation_id.slice(0, 8)}…</span></h1></div><span className={`conversation-status-badge ${statusTone(conversation.status)}`}>{conversation.status || "Unknown"}</span></header>
    <div className="conversation-workspace"><div className="conversation-main-column">
      <section className="admin-card conversation-cases-card"><div className="conversation-section-heading"><div><p className="admin-eyebrow">ESCALATIONS</p><h2>Related cases</h2></div><span>{cases.length} total</span></div>{cases.length ? <div className="conversation-case-grid">{cases.map((item) => <Link className="conversation-case-card" key={item.id} to={`/admin/escalations?case=${item.id}`}><div className="conversation-case-top"><strong>#{item.shortId}</strong><span className={`conversation-status-badge ${statusTone(item.status)}`}>{item.status}</span></div><h3>{item.category}</h3><time>{dateTime(item.createdAt)}</time><span className="conversation-case-link">Open case →</span></Link>)}</div> : <div className="conversation-empty-state">No escalation cases are linked to this conversation.</div>}</section>
      <section className="admin-card admin-conversation-card conversation-transcript-card"><div className="conversation-section-heading"><div><p className="admin-eyebrow">ACTIVITY</p><h2>Conversation transcript</h2></div><span>{conversation.turn_count ?? messages.length} turns</span></div><div className="admin-chat-transcript">{messages.length ? messages.map((message, index) => <div className={`admin-chat-message ${message.type}`} key={`${message.type}-${index}`}><span className="admin-chat-avatar">{message.type === "human" ? <UserRound size={16} /> : <Bot size={16} />}</span><div className="admin-chat-content"><div className="conversation-message-meta"><strong>{message.type === "human" ? "User" : "AI assistant"}</strong><span>Message {index + 1}</span></div>{message.type === "ai" ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown> : <p>{message.content}</p>}</div></div>) : <p className="admin-conversation-empty">No readable messages are available for this conversation.</p>}</div></section>
    </div><aside className="conversation-sidebar"><section className="admin-card conversation-side-card conversation-user-card"><p className="admin-eyebrow">USER INFORMATION</p><div className="conversation-user-profile"><span className="conversation-user-avatar">{(conversation.user_name || "U").slice(0, 1).toUpperCase()}</span><div><h2>{conversation.user_name || "Unknown user"}</h2><a href={conversation.user_email ? mailto(conversation.user_email) : undefined}>{conversation.user_email || conversation.user_id || "No email available"}</a></div></div>{conversation.user_email && <a className="conversation-reply-button" href={mailto(conversation.user_email)}><span>✉</span> Reply via Outlook</a>}</section></aside></div>
  </main>;
}
