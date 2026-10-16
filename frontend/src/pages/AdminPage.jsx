/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, AlertTriangle, BarChart3, BookOpen, Bot, CalendarDays, ChevronDown, ChevronRight, Clock3, FileText, MessageSquare, RefreshCw, Users } from "lucide-react";
import { getAdminOverview } from "../../api";
import AdminLoadingState from "../components/admin/AdminLoadingState";

export default function AdminPage() {
  const [range, setRange] = useState("7 Days");
  const [audience, setAudience] = useState("Applicants");
  const [updated, setUpdated] = useState("2 minutes ago");
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const rangeDays = Number.parseInt(range, 10) || 7;
  const loadOverview = () => getAdminOverview(rangeDays).then((data) => { setOverview(data); setError(""); setUpdated("just now"); }).catch((err) => setError(err.message));
  useEffect(() => { loadOverview(); }, [range]);
  const rangeLabel = useMemo(() => range === "7 Days" ? "Last 7 days" : `Last ${range.toLowerCase()}`, [range]);
  const questions = [["Eligibility", 86], ["Required Documents", 72], ["Application Deadlines", 58], ["Programme Comparison", 43], ["Application Status", 37]];
  const agents = [["Admissions", 98, 94, 4, "2.1s"], ["Course Recommendation", 112, 109, 3, "2.8s"], ["Programme Comparison", 76, 74, 2, "3.2s"], ["FAQ", 61, 58, 3, "2.4s"]];
  const applicationInsights = overview?.application_insights || {};
  const applicationStatus = useMemo(() => Object.entries(overview?.applications || {}).map(([label, total]) => ({ label, total })), [overview]);
  const applicationTotal = applicationStatus.reduce((sum, item) => sum + item.total, 0);
  const Card = ({ children, className = "", onClick, ...props }) => <section className={`admin-card ${className}`} onClick={onClick} {...props}>{children}</section>;
  const CardTitle = ({ icon: Icon, children, action }) => <div className="admin-card-title"><span className="admin-title-icon"><Icon size={15} /></span><strong>{children}</strong>{action && <span className="admin-card-action">{action} <ChevronRight size={13} /></span>}</div>;
  const Stat = ({ icon: Icon, label, value, tone, onClick }) => <Card className="admin-stat-card" onClick={onClick} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined} onKeyDown={onClick ? (event) => { if (event.key === "Enter" || event.key === " ") onClick(); } : undefined}><span className={`admin-stat-icon ${tone}`}><Icon size={22} /></span><span className="admin-stat-copy"><small>{label}</small><b>{value}</b></span><ChevronRight size={15} className="text-app-faint" /></Card>;
  if (!overview && !error) return <AdminLoadingState label="Loading admin overview…" />;

  return (
    <div className="admin-overview-page">
      <header className="admin-overview-header"><div><h1>Admin Dashboard</h1><p>System overview and items requiring attention</p></div><div className="admin-header-actions"><span className="admin-updated"><Clock3 size={13} /> Last updated {updated}</span><label className="admin-range"><CalendarDays size={14} /><select value={range} onChange={(e) => setRange(e.target.value)}><option>1 Day</option><option>7 Days</option><option>30 Days</option><option>60 Days</option></select><ChevronDown size={13} /></label><button className="admin-refresh" type="button" onClick={loadOverview}><RefreshCw size={13} /> Refresh</button></div></header>
      {error && <p role="alert" className="admin-subline">Unable to load live overview: {error}</p>}
      <div className="admin-stats-grid"><Stat icon={Users} label="Active Users" value={overview?.users?.active ?? "—"} tone="blue" onClick={() => navigate("/admin/users")} /><Stat icon={MessageSquare} label="Conversations" value={overview?.conversations?.total ?? "—"} tone="blue" onClick={() => navigate("/admin/conversations")} /><Stat icon={AlertTriangle} label="Outstanding Checklist Items" value={overview?.checklist?.outstanding ?? "—"} tone="red" onClick={() => navigate("/admin/applications")} /><Stat icon={Activity} label="Applications" value={overview ? Object.values(overview.applications).reduce((sum, value) => sum + value, 0) : "—"} tone="orange" onClick={() => navigate("/admin/applications")} /></div>
      <div className="admin-overview-grid"><Card><CardTitle icon={MessageSquare}>Top User Questions</CardTitle><div className="admin-tabs">{["All", "Applicants", "Enrolled Students"].map((tab) => <button key={tab} type="button" className={audience === tab ? "selected" : ""} onClick={() => setAudience(tab)}>{tab}</button>)}</div><p className="admin-subline">{audience} questions · {rangeLabel}</p><div className="admin-questions">{questions.map(([label, value], i) => <div className="admin-question" key={label}><em>{i + 1}</em><span>{label}</span><div><i style={{ width: `${value}%` }} /></div><b>{value}</b></div>)}</div></Card><Card><CardTitle icon={AlertTriangle}>Needs Attention</CardTitle>{[[`${overview?.cases?.open ?? 0} open cases`, "Cases awaiting staff action", "red"], [`${overview?.checklist?.outstanding ?? 0} incomplete items`, "Application documents still missing", "orange"], [`${applicationInsights.average_processing_days ?? 0} days`, "Average time to final decision", "blue"]].map(([title, copy, tone]) => <div className="admin-attention-item" key={title}><span className={`admin-attention-dot ${tone}`} /><div><strong>{title}</strong><small>{copy}</small></div><ChevronRight size={14} /></div>)}</Card></div>
      <div className="admin-overview-grid admin-insights-grid"><Card><CardTitle icon={BarChart3}>Applications by Admission Term</CardTitle><div className="admin-bar-list">{(applicationInsights.by_term || []).slice(0, 6).map((item) => <div className="admin-bar-row" key={item.label}><span>{item.label}</span><div><i style={{ width: `${Math.max(8, (item.total / Math.max(...(applicationInsights.by_term || []).map((entry) => entry.total), 1)) * 100)}%` }} /></div><b>{item.total}</b></div>)}</div></Card><Card><CardTitle icon={Activity}>Application Status Distribution</CardTitle><div className="admin-bar-list">{applicationStatus.map((item) => <div className="admin-bar-row" key={item.label}><span>{item.label}</span><div><i style={{ width: `${Math.max(8, (item.total / Math.max(applicationTotal, 1)) * 100)}%` }} /></div><b>{item.total}</b></div>)}</div></Card></div>
      <Card className="admin-agents-card"><CardTitle icon={Bot} action="View all agents">Agent Monitoring</CardTitle><div className="admin-table-wrap"><table><thead><tr><th>Agent</th><th>Requests</th><th>Success</th><th>Failed</th><th>Avg Response</th><th>Status</th></tr></thead><tbody>{agents.map(([name, requests, success, failed, response]) => <tr key={name}><td>{name}</td><td>{requests}</td><td className="admin-success">{success}</td><td className="admin-failed">{failed}</td><td>{response}</td><td><span className="admin-status-dot" /> Healthy</td></tr>)}</tbody></table></div></Card>
      <div className="admin-overview-grid admin-bottom-grid"><Card><CardTitle icon={BookOpen}>Knowledge Base Status</CardTitle><div className="admin-kb-stats">{[["Universities", overview?.catalogue?.universities ?? "—"], ["Programs", overview?.catalogue?.programs ?? "—"], ["Courses", overview?.catalogue?.courses ?? "—"], ["Checklist outstanding", overview?.checklist?.outstanding ?? "—"]].map(([label, value], i) => <div key={label}><small>{label}</small><b className={i === 3 ? "warning" : ""}>{value}</b></div>)}</div></Card><Card><CardTitle icon={Clock3} action="View all activity">Recent Administrative Activity</CardTitle><div className="admin-activity">{(overview?.recent_activity || []).map((item) => <div key={item.id}><FileText size={13} /><span>{item.type}: {item.detail}</span><small>{item.updated_at ? new Date(item.updated_at).toLocaleString() : "—"}</small></div>)}</div></Card></div>
    </div>
  );
}
