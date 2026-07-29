import { HandHeart } from "lucide-react";
import { mentorRequests } from "../../../data/mock";
import { PageHeader, StatusBadge } from "../PageParts";
import { Card } from "../../ui";

export function MentoringPage() {
  return (
    <div>
      <PageHeader icon={HandHeart} title="Mentoring" subtitle="Manage mentor requests and mentees" />
      <Card className="mb-4">
        <h3 className="font-display text-base font-semibold text-app-primary mb-3">Incoming Requests</h3>
        <div className="space-y-2">
          {mentorRequests.map((m) => (
            <div key={m.id} className="flex items-center gap-3 p-3 rounded-lg bg-app-hover">
              <HandHeart size={16} className="text-brand-300" />
              <div className="flex-1">
                <p className="text-sm text-app-primary">{m.student}</p>
                <p className="text-xs text-app-muted">{m.topic}</p>
              </div>
              <span className="text-xs text-app-faint">{m.date}</span>
              <StatusBadge status={m.status} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
