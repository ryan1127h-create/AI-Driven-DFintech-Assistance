import { Calendar } from "lucide-react";
import { alumniEvents } from "../../../data/mock";
import { PageHeader } from "../PageParts";
import { Card, Badge } from "../../ui";

export function EventsPage() {
  return (
    <div>
      <PageHeader icon={Calendar} title="Alumni Events" subtitle="Upcoming networking and professional events" />
      <div className="space-y-3">
        {alumniEvents.map((e) => (
          <Card key={e.id}>
            <div className="flex items-start gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-500/15 text-brand-300 flex-shrink-0">
                <Calendar size={20} />
              </div>
              <div className="flex-1">
                <p className="font-medium text-app-primary">{e.title}</p>
                <p className="text-sm text-app-muted mt-0.5">{e.date} · {e.location}</p>
              </div>
              <Badge color="royal">{e.type}</Badge>
            </div>
            <button className="btn-outline w-full mt-3 text-xs">RSVP</button>
          </Card>
        ))}
      </div>
    </div>
  );
}
