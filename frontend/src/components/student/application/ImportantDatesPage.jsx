import { Calendar } from "lucide-react";
import { PageHeader, InfoRow } from "../PageParts";
import { Card } from "../../ui";

export function ImportantDatesPage() {
  return (
    <div>
      <PageHeader icon={Calendar} title="Important Dates" subtitle="Key dates for the academic year" />
      <Card>
        <div className="space-y-1">
          {[
            { date: "3 Aug 2026", event: "Orientation Week begins" },
            { date: "10 Aug 2026", event: "Semester 1 classes begin" },
            { date: "15 Sep 2026", event: "Module add/drop deadline" },
            { date: "28 Nov 2026", event: "Semester 1 exams" },
            { date: "10 Jan 2027", event: "Semester 2 classes begin" },
            { date: "15 May 2027", event: "Semester 2 exams end" },
          ].map((d, i) => (
            <InfoRow key={i} label={d.event} value={d.date} />
          ))}
        </div>
      </Card>
    </div>
  );
}
