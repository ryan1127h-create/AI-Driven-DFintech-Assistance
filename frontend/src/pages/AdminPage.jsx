/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, AlertTriangle, BarChart3, BookOpen, Bot, ChevronRight, Clock3, FileText, MessageSquare, RefreshCw, Users } from "lucide-react";
import { getAdminOverview } from "../../api";
import AdminLoadingState from "../components/admin/AdminLoadingState";

const Card = ({ children, className = "", onClick, ...props }) => <section className={`admin-card ${className}`} onClick={onClick} {...props}>{children}</section>;
const CardTitle = ({ icon: Icon, children, badge }) => <div className="admin-card-title"><span className="admin-title-icon"><Icon size={15} /></span><strong>{children}</strong>{badge && <span className="admin-card-action">{badge}</span>}</div>;
const Stat = ({ icon: Icon, label, value, tone, onClick }) => <Card className="admin-stat-card" onClick={onClick} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined} onKeyDown={onClick ? (event) => { if (event.key === "Enter" || event.key === " ") onClick(); } : undefined}><span className={`admin-stat-icon ${tone}`}><Icon size={22} /></span><span className="admin-stat-copy"><small>{label}</small><b>{value}</b></span><ChevronRight size={15} className="text-app-faint" /></Card>;

// Question topics come from the intent classifier (no message text is kept),
// so the card counts topics, not literal questions.
const AUDIENCE_TABS = [["all", "All"], ["applicant", "Applicants"], ["enrolled_student", "Enrolled Students"]];
const formatLatency = (ms) => (ms == null ? "—" : `${(ms / 1000).toFixed(1)}s`);

export default function AdminPage() {
  const [audience, setAudience] = useState("all");
  const [updated, setUpdated] = useState("—");
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const loadOverview = () => getAdminOverview().then((data) => { setOverview(data); setError(""); setUpdated(new Date(data.generated_at).toLocaleTimeString()); }).catch((err) => setError(err.message));
  useEffect(() => { loadOverview(); }, []);
  const applicationInsights = overview?.application_insights || {};
  const applicationStatus = useMemo(() => Object.entries(overview?.applications || {}).map(([label, total]) => ({ label, total })), [overview]);
  const applicationTotal = applicationStatus.reduce((sum, item) => sum + item.total, 0);
  const usage = overview?.usage;
  const days = overview?.days ?? 7;
  const topics = usage?.top_topics?.[audience] || [];
  const topTopicTotal = Math.max(...topics.map((topic) => topic.total), 1);
  const usageEmpty = (text) => <p className="admin-subline">{usage && !usage.available ? "Usage statistics are not set up yet." : text}</p>;
  if (!overview && !error) return <AdminLoadingState label="Loading admin overview…" />;

  return (
    <div className="admin-overview-page">
      <header className="admin-overview-header"><div><h1>Admin Dashboard</h1><p>System overview and items requiring attention</p></div><div className="admin-header-actions"><span className="admin-updated"><Clock3 size={13} /> Last updated {updated}</span><button className="admin-refresh" type="button" onClick={loadOverview}><RefreshCw size={13} /> Refresh</button></div></header>
      {error && <p role="alert" className="admin-subline">Unable to load live overview: {error}</p>}
      <div className="admin-stats-grid"><Stat icon={Users} label="Active Users" value={overview?.users?.active ?? "—"} tone="blue" onClick={() => navigate("/admin/users")} /><Stat icon={MessageSquare} label={`Conversations (${days} days)`} value={overview?.conversations?.total ?? "—"} tone="blue" onClick={() => navigate("/admin/conversations")} /><Stat icon={AlertTriangle} label="Outstanding Checklist Items" value={overview?.checklist?.outstanding ?? "—"} tone="red" onClick={() => navigate("/admin/applications")} /><Stat icon={Activity} label="Applications" value={overview ? Object.values(overview.applications).reduce((sum, value) => sum + value, 0) : "—"} tone="orange" onClick={() => navigate("/admin/applications")} /></div>
      <div className="admin-overview-grid"><Card><CardTitle icon={MessageSquare} badge={`Last ${days} days`}>Top Question Topics</CardTitle><div className="admin-tabs">{AUDIENCE_TABS.map(([value, label]) => <button key={value} type="button" className={audience === value ? "selected" : ""} onClick={() => setAudience(value)}>{label}</button>)}</div>{topics.length ? <div className="admin-questions">{topics.map((topic, i) => <div className="admin-question" key={topic.label}><em>{i + 1}</em><span>{topic.label}</span><div><i style={{ width: `${(topic.total / topTopicTotal) * 100}%` }} /></div><b>{topic.total}</b></div>)}</div> : usageEmpty(`No questions in the last ${days} days.`)}</Card><Card><CardTitle icon={AlertTriangle}>Needs Attention</CardTitle>{[[`${overview?.cases?.open ?? 0} open cases`, "Cases awaiting staff action", "red", "/admin/escalations"], [`${overview?.checklist?.outstanding ?? 0} incomplete items`, "Application documents still missing", "orange", "/admin/applications"], [`${applicationInsights.average_processing_days ?? 0} days`, "Average time to final decision", "blue", null]].map(([title, copy, tone, path]) => <div className="admin-attention-item" key={title} role={path ? "button" : undefined} tabIndex={path ? 0 : undefined} onClick={path ? () => navigate(path) : undefined} onKeyDown={path ? (event) => { if (event.key === "Enter" || event.key === " ") navigate(path); } : undefined}><span className={`admin-attention-dot ${tone}`} /><div><strong>{title}</strong><small>{copy}</small></div>{path && <ChevronRight size={14} />}</div>)}</Card></div>
      <div className="admin-overview-grid admin-insights-grid"><Card><CardTitle icon={BarChart3}>Applications by Admission Term</CardTitle><div className="admin-bar-list">{(applicationInsights.by_term || []).slice(0, 6).map((item) => <div className="admin-bar-row" key={item.label}><span>{item.label}</span><div><i style={{ width: `${Math.max(8, (item.total / Math.max(...(applicationInsights.by_term || []).map((entry) => entry.total), 1)) * 100)}%` }} /></div><b>{item.total}</b></div>)}</div></Card><Card><CardTitle icon={Activity}>Application Status Distribution</CardTitle><div className="admin-bar-list">{applicationStatus.map((item) => <div className="admin-bar-row" key={item.label}><span>{item.label}</span><div><i style={{ width: `${Math.max(8, (item.total / Math.max(applicationTotal, 1)) * 100)}%` }} /></div><b>{item.total}</b></div>)}</div></Card></div>
      <Card className="admin-agents-card"><CardTitle icon={Bot} badge={`Last ${days} days`}>Agent Monitoring</CardTitle>{usage?.agents?.length ? <div className="admin-table-wrap"><table><thead><tr><th>Agent</th><th>Requests</th><th>Success</th><th>Failed</th><th>Avg Response</th><th>Status</th></tr></thead><tbody>{usage.agents.map((agent) => <tr key={agent.name}><td>{agent.label}</td><td>{agent.requests}</td><td className="admin-success">{agent.success}</td><td className="admin-failed">{agent.failed}</td><td>{formatLatency(agent.avg_latency_ms)}</td><td><span className={`admin-status-dot ${agent.status === "Degraded" ? "degraded" : ""}`} /> {agent.status}</td></tr>)}</tbody></table></div> : usageEmpty(`No agent activity in the last ${days} days.`)}</Card>
      <div className="admin-overview-grid admin-bottom-grid"><Card><CardTitle icon={BookOpen}>Knowledge Base Status</CardTitle><div className="admin-kb-stats">{[["Universities", overview?.catalogue?.universities ?? "—"], ["Programs", overview?.catalogue?.programs ?? "—"], ["Courses", overview?.catalogue?.courses ?? "—"], ["Checklist outstanding", overview?.checklist?.outstanding ?? "—"]].map(([label, value], i) => <div key={label}><small>{label}</small><b className={i === 3 ? "warning" : ""}>{value}</b></div>)}</div></Card><Card><CardTitle icon={Clock3}>Recently Updated Applications</CardTitle><div className="admin-activity">{(overview?.recent_activity || []).map((item) => <div key={item.id}><FileText size={13} /><span>{item.type}: {item.detail}</span><small>{item.updated_at ? new Date(item.updated_at).toLocaleString() : "—"}</small></div>)}</div></Card></div>
    </div>
  );
}
