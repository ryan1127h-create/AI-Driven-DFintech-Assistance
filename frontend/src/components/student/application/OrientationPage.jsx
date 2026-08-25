import { Users, Calendar } from "lucide-react";
import { PageHeader } from "../PageParts";
import { Card } from "../../ui";

export function OrientationPage() {
  return (
    <div>
      <PageHeader icon={Users} title="Orientation" subtitle="Welcome week schedule and activities" />
      <Card>
        <h3 className="font-display text-base font-semibold text-app-primary mb-3">Orientation Week · 3-7 August 2026</h3>
        <div className="space-y-2">
          {[
            { day: "Mon 3 Aug", event: "Welcome & Programme Briefing", time: "9:00 AM" },
            { day: "Tue 4 Aug", event: "Campus & FinTech Lab Tour", time: "10:00 AM" },
            { day: "Wed 5 Aug", event: "Module Registration Clinic", time: "2:00 PM" },
            { day: "Thu 6 Aug", event: "Industry Partner Networking", time: "6:00 PM" },
            { day: "Fri 7 Aug", event: "Team Building & Social", time: "3:00 PM" },
          ].map((s, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-app-hover">
              <Calendar size={16} className="text-brand-300" />
              <span className="text-sm text-app-muted w-24">{s.day}</span>
              <span className="text-sm text-app-primary flex-1">{s.event}</span>
              <span className="text-xs text-app-muted">{s.time}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
