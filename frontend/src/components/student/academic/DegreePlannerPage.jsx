import { Map } from "lucide-react";
import { degreePlan } from "../../../data/mock";
import { PageHeader } from "../PageParts";
import { Card, Badge } from "../../ui";

export function DegreePlannerPage() {
  return (
    <div>
      <PageHeader icon={Map} title="Degree Planner" subtitle={`Track: ${degreePlan.track}`} />
      <div className="space-y-4">
        {degreePlan.semesters.map((sem, i) => (
          <Card key={i}>
            <h3 className="font-display text-base font-semibold text-app-primary mb-3">{sem.name}</h3>
            <div className="space-y-2">
              {sem.modules.map((m, j) => (
                <div key={j} className="flex items-center gap-3 p-3 rounded-lg bg-app-hover">
                  <span className="font-mono text-xs text-brand-300 w-20">{m.code}</span>
                  <span className="text-sm text-app-primary flex-1">{m.name}</span>
                  <Badge color="ink">{m.credits} cr</Badge>
                  {m.status === "planned" && <Badge color="amber">Planned</Badge>}
                  {m.status === "inProgress" && <Badge color="brand">In Progress</Badge>}
                  {!m.status && <Badge color="emerald2">Completed</Badge>}
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
