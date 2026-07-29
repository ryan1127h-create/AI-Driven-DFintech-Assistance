import {
  Activity, CheckCircle, AlertCircle, Clock, CheckCircle2,
} from "lucide-react";
import { applicationStatus } from "../../../data/mock";
import { PageHeader, StatusBadge } from "../PageParts";
import { Card, Badge } from "../../ui";

export function ApplicationStatusPage() {
  return (
    <div>
      <PageHeader icon={Activity} title="Application Status" subtitle={`Reference: ${applicationStatus.ref}`} />
      <Card className="mb-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm text-app-muted">Current Stage</p>
            <p className="font-display text-2xl font-bold text-app-primary">{applicationStatus.stage}</p>
          </div>
          <Badge color="amber">In Review</Badge>
        </div>
        <div className="flex items-center gap-2">
          {applicationStatus.rounds.map((r, i) => (
            <div key={i} className="flex-1">
              <div className="flex items-center gap-2">
                <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium ${r.done ? "bg-emerald2-500 text-app-primary" : r.active ? "bg-brand-500 text-app-primary" : "bg-app-hover text-app-faint"}`}>
                  {r.done ? <CheckCircle size={14} /> : i + 1}
                </div>
                {i < applicationStatus.rounds.length - 1 && <div className={`flex-1 h-0.5 ${r.done ? "bg-emerald2-500" : "bg-app-hover"}`} />}
              </div>
              <p className="text-xs text-app-secondary mt-1.5">{r.name}</p>
              <p className="text-[10px] text-app-faint">{r.date}</p>
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <h3 className="font-display text-base font-semibold text-app-primary mb-3">Documents</h3>
        <div className="space-y-2">
          {applicationStatus.documents.map((d, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-app-hover">
              {d.status === "verified" ? <CheckCircle2 size={16} className="text-emerald2-400" /> : d.status === "missing" ? <AlertCircle size={16} className="text-red-400" /> : <Clock size={16} className="text-amber-400" />}
              <span className="text-sm text-app-primary flex-1">{d.name}</span>
              <StatusBadge status={d.status} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
