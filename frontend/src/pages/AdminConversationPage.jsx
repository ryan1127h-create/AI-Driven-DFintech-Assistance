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

export default function AdminConversationPage() {
  const { conversationId } = useParams(); const navigate = useNavigate(); const [conversation, setConversation] = useState(null); const [error, setError] = useState("");
  useEffect(() => { getAdminConversation(conversationId).then(setConversation).catch((err) => setError(err.message)); }, [conversationId]);
  const messages = useMemo(() => conversation ? readMessages(conversation) : [], [conversation]);
  if (error) return <main className="admin-overview-page"><p role="alert">{error}</p></main>;
  if (!conversation) return <AdminLoadingState label="Loading conversation…" />;
  return <main className="admin-overview-page"><button className="admin-back-button" type="button" onClick={() => navigate("/admin/conversations")}>← Back to conversations</button><header className="admin-shared-page-header"><p className="admin-eyebrow">CONVERSATION DETAILS</p><h1>{conversation.conversation_id.slice(0, 8)}…</h1><p>User: {conversation.user_name || conversation.user_email || conversation.user_id || "Unknown"}</p></header>{conversation.cases?.length > 0 && <section className="admin-card admin-user-related-card"><div className="admin-card-title"><strong>Escalation cases from this conversation</strong><span>{conversation.cases.length} case{conversation.cases.length === 1 ? "" : "s"}</span></div><div className="admin-user-conversation-list">{conversation.cases.map((item) => <Link className="admin-user-conversation-item" key={item.id} to={`/admin/escalations?case=${item.id}`}><span>#{item.shortId} · {item.category}</span><small>{item.status} · {new Date(item.createdAt).toLocaleString()}</small></Link>)}</div></section>}<section className="admin-card admin-conversation-card"><div className="admin-conversation-header"><div className="admin-card-title"><strong>Conversation transcript</strong></div><span>{conversation.status} · {conversation.turn_count} turns</span></div><div className="admin-chat-transcript">{messages.length ? messages.map((message, index) => <div className={`admin-chat-message ${message.type}`} key={`${message.type}-${index}`}><span className="admin-chat-avatar">{message.type === "human" ? <UserRound size={15} /> : <Bot size={15} />}</span><div className="admin-chat-content"><small>{message.type === "human" ? "User" : "AI assistant"}</small>{message.type === "ai" ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown> : <p>{message.content}</p>}</div></div>) : <p className="admin-conversation-empty">No readable messages are available for this conversation.</p>}</div></section></main>;
}
