import { TrendingUp } from "lucide-react";
import { academicProgress } from "../../../data/mock";
import { PageHeader } from "../PageParts";
import { Card, Badge, ProgressBar } from "../../ui";
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis } from "recharts";

export function AcademicProgressPage() {
  const gradeData = academicProgress.completedModules.map((m) => ({ name: m.code, grade: m.grade === "A+" ? 5 : m.grade === "A" ? 4.5 : m.grade === "A-" ? 4 : 3.5 }));
  return (
    <div>
      <PageHeader icon={TrendingUp} title="Academic Progress" subtitle={academicProgress.semester} />
      <div className="grid sm:grid-cols-3 gap-4 mb-4">
        <Card className="text-center">
          <p className="font-display text-3xl font-bold text-app-primary">{academicProgress.creditsCompleted}/{academicProgress.creditsTotal}</p>
          <p className="text-sm text-app-muted">Credits Completed</p>
        </Card>
        <Card className="text-center">
          <p className="font-display text-3xl font-bold text-emerald2-400">{academicProgress.cap}</p>
          <p className="text-sm text-app-muted">Current CAP</p>
        </Card>
        <Card className="text-center">
          <p className="font-display text-3xl font-bold text-brand-300">{Math.round((academicProgress.creditsCompleted / academicProgress.creditsTotal) * 100)}%</p>
          <p className="text-sm text-app-muted">Progress</p>
        </Card>
      </div>
      <Card className="mb-4">
        <ProgressBar value={academicProgress.creditsCompleted} max={academicProgress.creditsTotal} color="brand" />
      </Card>
      <Card className="mb-4">
        <h3 className="font-display text-base font-semibold text-app-primary mb-4">Module Grades</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={gradeData}>
            <XAxis dataKey="name" tick={{ fill: "#aab1d4", fontSize: 10 }} />
            <YAxis domain={[0, 5]} tick={{ fill: "#aab1d4", fontSize: 11 }} />
            <Bar dataKey="grade" radius={[4, 4, 0, 0]}>
              {gradeData.map((_, i) => <Cell key={i} fill={["#3366ff", "#8b5cf6", "#22d3ee", "#10b981", "#f59e0b", "#ef4444"][i % 6]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>
      <Card>
        <h3 className="font-display text-base font-semibold text-app-primary mb-3">Completed Modules</h3>
        <div className="space-y-2">
          {academicProgress.completedModules.map((m, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-app-hover">
              <span className="font-mono text-xs text-brand-300 w-16">{m.code}</span>
              <span className="text-sm text-app-primary flex-1">{m.name}</span>
              <Badge color="ink">{m.credits} cr</Badge>
              <Badge color={m.grade.startsWith("A") ? "emerald2" : "amber"}>{m.grade}</Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
