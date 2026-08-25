import { CalendarClock, AlertCircle } from "lucide-react";
import { programme } from "../../../data/programme";
import { PageHeader, InfoRow } from "../PageParts";
import { Card, Badge } from "../../ui";

export function DeadlinesPage() {
  return (
    <div>
      <PageHeader icon={CalendarClock} title="Deadlines" subtitle="Application timeline and key dates" />
      <div className="space-y-3">
        <Card className="border-amber-400/20 bg-amber-500/5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/15 text-amber-300">
              <AlertCircle size={20} />
            </div>
            <div className="flex-1">
              <p className="font-medium text-app-primary">Round 2 Application Deadline</p>
              <p className="text-sm text-app-muted">{programme.deadlines.close}</p>
            </div>
            <Badge color="red">5 days left</Badge>
          </div>
        </Card>
        <Card>
          <InfoRow label="Applications Open" value={programme.deadlines.open} />
          <InfoRow label="Round 1 Deadline" value={programme.deadlines.round1} />
          <InfoRow label="Round 2 Deadline" value={programme.deadlines.round2} />
          <InfoRow label="Decision Notification" value="4-6 weeks after complete submission" />
          <InfoRow label="Offer Acceptance" value="2 weeks after offer" />
        </Card>
      </div>
    </div>
  );
}
