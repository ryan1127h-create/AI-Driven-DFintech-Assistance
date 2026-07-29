import { CheckSquare } from "lucide-react";
import { graduationAudit } from "../../../data/mock";
import { PageHeader, StatusBadge } from "../PageParts";
import { Card, ProgressBar } from "../../ui";

export function RequirementTrackerPage() {
  return (
    <div>
      <PageHeader icon={CheckSquare} title="Requirement Tracker" subtitle="Monitor your graduation requirements" />
      <Card>
        <div className="space-y-3">
          {graduationAudit.requirements.map((r, i) => (
            <div key={i}>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm text-app-primary">{r.name}</span>
                <StatusBadge status={r.status} />
              </div>
              <ProgressBar value={typeof r.completed === "number" && typeof r.required === "number" ? (r.completed / r.required) * 100 : 100} color={r.status === "met" ? "emerald2" : "amber"} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
