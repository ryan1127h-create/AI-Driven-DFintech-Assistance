import { GitCompare } from "lucide-react";
import { compareProgrammes } from "../../../data/programme";
import { PageHeader } from "../PageParts";
import { Card, Badge } from "../../ui";
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer } from "recharts";

export function ComparePage() {
  const radarData = compareProgrammes.map((p) => ({ programme: p.name.split("(")[0].trim(), score: p.score }));
  return (
    <div>
      <PageHeader icon={GitCompare} title="Compare Programmes" subtitle="Side-by-side comparison with similar NUS and NTU programmes" />
      <Card className="mb-4">
        <ResponsiveContainer width="100%" height={300}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="#2f3668" />
            <PolarAngleAxis dataKey="programme" tick={{ fill: "#aab1d4", fontSize: 11 }} />
            <Radar dataKey="score" stroke="#3366ff" fill="#3366ff" fillOpacity={0.3} />
          </RadarChart>
        </ResponsiveContainer>
      </Card>
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-app-subtle">
                <th className="text-left py-3 px-3 text-app-muted font-medium">Programme</th>
                <th className="text-left py-3 px-3 text-app-muted font-medium">Focus</th>
                <th className="text-left py-3 px-3 text-app-muted font-medium">Duration</th>
                <th className="text-left py-3 px-3 text-app-muted font-medium">Capstone</th>
                <th className="text-left py-3 px-3 text-app-muted font-medium">Industry</th>
                <th className="text-left py-3 px-3 text-app-muted font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {compareProgrammes.map((p, i) => (
                <tr key={i} className="border-b border-app-soft hover:bg-app-hover transition">
                  <td className="py-3 px-3 text-app-primary font-medium">{p.name}</td>
                  <td className="py-3 px-3 text-app-secondary">{p.focus}</td>
                  <td className="py-3 px-3 text-app-secondary">{p.duration}</td>
                  <td className="py-3 px-3">{p.capstone ? <Badge color="emerald2">Yes</Badge> : <Badge color="ink">No</Badge>}</td>
                  <td className="py-3 px-3 text-app-secondary">{p.industry}</td>
                  <td className="py-3 px-3"><span className="font-display font-bold text-brand-300">{p.score}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
