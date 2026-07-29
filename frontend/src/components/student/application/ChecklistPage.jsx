import { ListChecks, CheckCircle } from "lucide-react";
import { PageHeader } from "../PageParts";
import { Card, Badge, ProgressBar } from "../../ui";

export function ChecklistPage() {
  const items = [
    { text: "Personal particulars form", done: true },
    { text: "Resume / CV", done: true },
    { text: "Statement of purpose", done: true },
    { text: "Official academic transcript (sealed)", done: false, urgent: true },
    { text: "Academic reference letter", done: false },
    { text: "English proficiency proof (if applicable)", done: false },
    { text: "Application fee payment (S$50)", done: true },
  ];
  const completed = items.filter((i) => i.done).length;
  return (
    <div>
      <PageHeader icon={ListChecks} title="Application Checklist" subtitle={`${completed} of ${items.length} items completed`} />
      <Card className="mb-4">
        <ProgressBar value={completed} max={items.length} color="brand" />
      </Card>
      <div className="space-y-2">
        {items.map((item, i) => (
          <Card key={i} className="flex items-center gap-3">
            <div className={`flex h-6 w-6 items-center justify-center rounded-md ${item.done ? "bg-emerald2-500" : "bg-app-hover"}`}>
              {item.done && <CheckCircle size={14} className="text-app-primary" />}
            </div>
            <span className={`text-sm flex-1 ${item.done ? "text-app-muted line-through" : "text-app-primary"}`}>{item.text}</span>
            {item.urgent && <Badge color="red">Urgent</Badge>}
          </Card>
        ))}
      </div>
    </div>
  );
}
