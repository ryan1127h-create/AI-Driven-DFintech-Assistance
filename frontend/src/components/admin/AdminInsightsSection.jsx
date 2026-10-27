/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CircleHelp, Filter, Gauge, Layers, Users } from "lucide-react";
import { getAdminInsights } from "../../../api";
import { formatDateTime } from "../../utils/format";

// The proposal's analytics (backend admin service get_insights): how many
// questions the assistant settles without a person, who asks what at each
// stage, what it couldn't answer, the student funnel and alumni use.

const PERIODS = [[7, "7 days"], [30, "30 days"], [90, "90 days"]];
const percent = (rate) => (rate == null ? "—" : `${Math.round(rate * 100)}%`);

// The dashboard orders its blocks with CSS `order`; this one comes last.
const Section = ({ children }) => <div className="admin-insights-section">{children}</div>;
const Card = ({ children, className = "" }) => <section className={`admin-card ${className}`}>{children}</section>;
const CardTitle = ({ icon: Icon, children, badge }) => <div className="admin-card-title"><span className="admin-title-icon"><Icon size={15} /></span><strong>{children}</strong>{badge && <span className="admin-card-action">{badge}</span>}</div>;
const Bar = ({ label, total, max }) => <div className="admin-bar-row"><span>{label}</span><div><i style={{ width: `${Math.max(6, (total / Math.max(max, 1)) * 100)}%` }} /></div><b>{total}</b></div>;
const Figure = ({ value, label }) => <div className="admin-insight-figure"><b>{value}</b><small>{label}</small></div>;

export default function AdminInsightsSection() {
  const [days, setDays] = useState(30);
  const [insights, setInsights] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    getAdminInsights(days).then((data) => { setInsights(data); setError(""); }).catch((err) => setError(err.message));
  }, [days]);

  const periods = <div className="admin-tabs">{PERIODS.map(([value, label]) => <button key={value} type="button" className={days === value ? "selected" : ""} onClick={() => setDays(value)}>{label}</button>)}</div>;
  if (error) return <Section><Card className="admin-insights-card">{periods}<p role="alert" className="admin-subline">Unable to load insights: {error}</p></Card></Section>;
  if (!insights) return null;
  if (!insights.available) return <Section><Card className="admin-insights-card">{periods}<p className="admin-subline">Usage statistics are not set up yet.</p></Card></Section>;

  const { resolution, stages, gaps, funnel, alumni } = insights;
  const maxStage = Math.max(...stages.map((stage) => stage.questions), 1);
  const maxFunnel = Math.max(...funnel.map((step) => step.total), 1);
  return (
    <Section>
      <header className="admin-insights-header"><div><h2>Assistant Insights</h2><p>How well questions are answered, and who asks what</p></div>{periods}</header>
      <div className="admin-overview-grid admin-insights-grid">
        <Card>
          <CardTitle icon={Gauge} badge={`Last ${days} days`}>Automatic Resolution</CardTitle>
          <div className="admin-insight-figures">
            <Figure value={percent(resolution.rate)} label="answered without staff" />
            <Figure value={resolution.turns} label="questions" />
            <Figure value={resolution.unresolved_turns} label="not answered" />
            <Figure value={resolution.escalated} label="handed to staff" />
          </div>
          <p className="admin-subline">Questions the assistant couldn&apos;t answer, and cases students opened for staff, count against the rate.</p>
        </Card>
        <Card>
          <CardTitle icon={Layers} badge={`Last ${days} days`}>Questions by Stage</CardTitle>
          {stages.length ? <div className="admin-bar-list">{stages.map((stage) => <div key={stage.stage}><Bar label={stage.label} total={stage.questions} max={maxStage} /><small className="admin-insight-topics">{stage.top_topics.map((topic) => `${topic.label} ${topic.total}`).join(" · ")}</small></div>)}</div> : <p className="admin-subline">No questions in this period.</p>}
        </Card>
      </div>
      <Card className="admin-agents-card">
        <CardTitle icon={CircleHelp} badge={`Latest ${gaps.length}`}>Questions the Assistant Couldn&apos;t Answer</CardTitle>
        {gaps.length ? <div className="admin-table-wrap"><table><thead><tr><th>When</th><th>Stage</th><th>Topic</th><th>Unanswered by</th><th>Handed to staff</th><th>Conversation</th></tr></thead><tbody>{gaps.map((gap) => <tr key={`${gap.conversation_id}-${gap.created_at}`}><td>{formatDateTime(gap.created_at)}</td><td>{gap.stage}</td><td>{gap.topics.join(", ") || "—"}</td><td>{gap.agents.join(", ") || "—"}</td><td>{gap.case_summary || "—"}</td><td>{gap.conversation_id ? <Link className="admin-related-link" to={`/admin/conversations/${gap.conversation_id}`}>Open</Link> : "—"}</td></tr>)}</tbody></table></div> : <p className="admin-subline">Every question in this period was answered.</p>}
      </Card>
      <div className="admin-overview-grid admin-insights-grid">
        <Card>
          <CardTitle icon={Filter} badge="Now">Student Funnel</CardTitle>
          <div className="admin-bar-list">{funnel.map((step) => <div key={step.stage}><Bar label={step.label} total={step.total} max={maxFunnel} />{step.breakdown.length > 0 && <small className="admin-insight-topics">{step.breakdown.map((part) => `${part.label} ${part.total}`).join(" · ")}</small>}</div>)}</div>
        </Card>
        <Card>
          <CardTitle icon={Users} badge={`Last ${days} days`}>Alumni Connections</CardTitle>
          <div className="admin-insight-figures">
            <Figure value={alumni.questions} label="alumni questions" />
            <Figure value={alumni.requests} label="requests sent" />
            <Figure value={percent(alumni.acceptance_rate)} label="accepted" />
            <Figure value={alumni.pending} label="awaiting reply" />
          </div>
          <p className="admin-subline">{alumni.listed} of {alumni.alumni} alumni are listed · {alumni.story_for_applicants} share their story with applicants · {alumni.story_for_students} with current students</p>
        </Card>
      </div>
    </Section>
  );
}
