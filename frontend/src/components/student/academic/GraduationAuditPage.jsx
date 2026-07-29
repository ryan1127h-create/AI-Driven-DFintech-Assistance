import { CheckSquare, FileText } from "lucide-react";
import { graduationAudit } from "../../../data/mock";
import { PageHeader, StatusBadge } from "../PageParts";
import { Card } from "../../ui";

export function GraduationAuditPage() {
  return (
    <div>
      <PageHeader icon={CheckSquare} title="Graduation Audit" subtitle="Check your eligibility to graduate" />
      <Card className={`mb-4 ${graduationAudit.eligible ? "border-emerald2-400/20 bg-emerald2-500/5" : "border-amber-400/20 bg-amber-500/5"}`}>
        <div className="flex items-center gap-3">
          {graduationAudit.eligible ? <CheckSquare size={24} className="text-emerald2-400" /> : <FileText size={24} className="text-amber-300" />}
          <div>
            <p className="font-display text-lg font-bold text-app-primary">{graduationAudit.eligible ? "Eligible to Graduate" : "1 Requirement Remaining"}</p>
            <p className="text-sm text-app-secondary">{graduationAudit.remaining}</p>
          </div>
        </div>
      </Card>
      <Card>
        <h3 className="font-display text-base font-semibold text-app-primary mb-3">Requirements</h3>
        <div className="space-y-2">
          {graduationAudit.requirements.map((r, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-app-hover">
              {r.status === "met" ? <CheckSquare size={16} className="text-emerald2-400" /> : <FileText size={16} className="text-amber-400" />}
              <span className="text-sm text-app-primary flex-1">{r.name}</span>
              <span className="text-xs text-app-muted">{r.completed}/{r.required}</span>
              <StatusBadge status={r.status} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
