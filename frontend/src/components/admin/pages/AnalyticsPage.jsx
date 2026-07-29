import {
  BarChart3,
} from "lucide-react";
import {
  inquiryTrends, escalationRoots,
  lifecycleDistribution, applicationFunnel,
} from "../../../data/mock";
import { Card } from "../../ui";
import { PageHeader } from "../../student/PageParts";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, ResponsiveContainer, Tooltip,
} from "recharts";

export function AnalyticsPage() {
  return (
    <div>
      <PageHeader icon={BarChart3} title="Analytics" subtitle="Deep insights into AI assistant performance" />
      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Inquiry vs Escalation Trends</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={inquiryTrends}>
              <XAxis dataKey="month" tick={{ fill: "#aab1d4", fontSize: 11 }} />
              <YAxis tick={{ fill: "#aab1d4", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="inquiries" fill="#3366ff" radius={[4, 4, 0, 0]} />
              <Bar dataKey="escalated" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">User Lifecycle Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={lifecycleDistribution}>
              <XAxis dataKey="stage" tick={{ fill: "#aab1d4", fontSize: 10 }} />
              <YAxis tick={{ fill: "#aab1d4", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {lifecycleDistribution.map((_, i) => <Cell key={i} fill={["#3366ff", "#598bff", "#8b5cf6", "#a78bfa", "#22d3ee", "#10b981"][i]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Escalation Root Causes</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={escalationRoots} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name }) => name} labelLine={{ stroke: "#2f3668" }}>
                {escalationRoots.map((e, i) => <Cell key={i} fill={e.color} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", borderRadius: 8, fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Application Funnel</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={applicationFunnel}>
              <XAxis dataKey="stage" tick={{ fill: "#aab1d4", fontSize: 10 }} />
              <YAxis tick={{ fill: "#aab1d4", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]} fill="#8b5cf6" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
