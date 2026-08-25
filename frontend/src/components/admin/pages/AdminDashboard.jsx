import {
  MessageSquare, Cpu, AlertTriangle, Clock, Star, Users,
  TrendingUp,
} from "lucide-react";
import {
  adminKPIs, inquiryTrends, automationTrends, escalationRoots,
  applicationFunnel,
} from "../../../data/mock";
import { Card, StatCard } from "../../ui";
import { PageHeader } from "../../student/PageParts";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, ResponsiveContainer, Tooltip, Area, AreaChart,
} from "recharts";

const kpiIcons = { MessageSquare, Cpu, AlertTriangle, Clock, Star, Users };

export function AdminDashboard() {
  return (
    <div>
      <PageHeader icon={TrendingUp} title="Executive Dashboard" subtitle="AI assistant performance overview" />
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {adminKPIs.map((kpi) => {
          const Icon = kpiIcons[kpi.icon] || MessageSquare;
          return <StatCard key={kpi.id} label={kpi.label} value={kpi.value} delta={kpi.delta} trend={kpi.trend} icon={Icon} />;
        })}
      </div>
      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Inquiry Trends</h3>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={inquiryTrends}>
              <defs>
                <linearGradient id="inqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3366ff" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#3366ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="month" tick={{ fill: "#aab1d4", fontSize: 11 }} />
              <YAxis tick={{ fill: "#aab1d4", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", borderRadius: 8, fontSize: 12 }} />
              <Area type="monotone" dataKey="inquiries" stroke="#3366ff" fill="url(#inqGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Automation Rate</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={automationTrends}>
              <XAxis dataKey="month" tick={{ fill: "#aab1d4", fontSize: 11 }} />
              <YAxis domain={[60, 85]} tick={{ fill: "#aab1d4", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", borderRadius: 8, fontSize: 12 }} />
              <Line type="monotone" dataKey="rate" stroke="#10b981" strokeWidth={2} dot={{ fill: "#10b981", r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <div className="grid lg:grid-cols-3 gap-4">
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Escalation Root Causes</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={escalationRoots} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={45} outerRadius={80} paddingAngle={2}>
                {escalationRoots.map((e, i) => <Cell key={i} fill={e.color} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", borderRadius: 8, fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1 mt-2">
            {escalationRoots.map((e, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="h-2 w-2 rounded-full" style={{ background: e.color }} />
                <span className="text-app-secondary flex-1">{e.name}</span>
                <span className="text-app-muted">{e.value}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Application Funnel</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={applicationFunnel} layout="vertical" margin={{ left: 20 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="stage" tick={{ fill: "#aab1d4", fontSize: 11 }} width={80} />
              <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {applicationFunnel.map((_, i) => <Cell key={i} fill={["#3366ff", "#598bff", "#8b5cf6", "#a78bfa", "#22d3ee", "#10b981"][i]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
