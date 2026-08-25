import { FileText } from "lucide-react";
import { academicProgress } from "../../../data/mock";
import { PageHeader } from "../PageParts";
import { Card, Badge } from "../../ui";

export function TranscriptPage() {
  return (
    <div>
      <PageHeader icon={FileText} title="Transcript" subtitle="Official academic record" action={<button className="btn-outline">Request Official</button>} />
      <Card>
        <div className="flex items-center justify-between mb-4 pb-4 border-b border-app-subtle">
          <div>
            <p className="font-display text-lg font-bold text-app-primary">Sofia Rahman</p>
            <p className="text-sm text-app-muted">MSc Digital Financial Technology · NUS</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-app-muted">Cumulative CAP</p>
            <p className="font-display text-2xl font-bold text-emerald2-400">{academicProgress.cap}</p>
          </div>
        </div>
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
