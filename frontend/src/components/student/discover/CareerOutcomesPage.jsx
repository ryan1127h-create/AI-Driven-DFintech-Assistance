import { TrendingUp } from "lucide-react";
import { careerOutcomes } from "../../../data/programme";
import { PageHeader } from "../PageParts";
import { Card, Badge } from "../../ui";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from "recharts";

export function CareerOutcomesPage() {
  const chartData = careerOutcomes.map((c) => ({ name: c.role.split(" ")[0], value: c.share }));
  return (
    <div>
      <PageHeader icon={TrendingUp} title="Career Outcomes" subtitle="Where MSc DFT graduates work" />
      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Role Distribution</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 20 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" tick={{ fill: "#aab1d4", fontSize: 11 }} width={70} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {chartData.map((_, i) => <Cell key={i} fill={["#3366ff", "#8b5cf6", "#22d3ee", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#14b8a6", "#6366f1"][i]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Salary Ranges</h3>
          <div className="space-y-2.5">
            {careerOutcomes.map((c, i) => (
              <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-app-hover">
                <span className="text-sm text-app-primary">{c.role}</span>
                <div className="flex items-center gap-3">
                  <Badge color="brand">{c.share}%</Badge>
                  <span className="text-sm font-medium text-emerald2-400">{c.salary}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
