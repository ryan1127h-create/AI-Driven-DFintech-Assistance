import { useEffect, useState } from "react";
import { LifeBuoy } from "lucide-react";
import { getMyEscalations } from "../../api";
import { formatDate } from "../utils/format";
import { LoadingState, PageHeader } from "../components/student/PageParts";
import { Badge, Card, EmptyState } from "../components/ui";

// The user's own requests to the programme office, raised from the chat:
// what kind, when, and whether staff have resolved it. Staff notes are
// internal and never shown here.

const CATEGORY_LABELS = {
  explicit_request: "Asked to speak to staff",
  complaint: "Complaint",
  policy_exception: "Exception request",
  sensitive: "Personal situation",
  low_confidence: "Question the assistant couldn't answer",
};

export default function SupportRequestsPage() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    getMyEscalations().then((data) => setItems(data.items || [])).catch((err) => setError(err.message || "Unable to load your requests."));
  }, []);

  return (
    <div className="animate-fadeIn">
      <PageHeader icon={LifeBuoy} title="Requests to Staff" subtitle="Conversations the assistant passed to the programme office, and where they stand." />
      {error && <p role="alert" className="mb-4 text-sm text-red-300">{error}</p>}
      {!items && !error && <LoadingState title="Loading your requests" subtitle="" />}
      {items && !items.length && (
        <EmptyState icon={LifeBuoy} title="No requests yet" subtitle="If you ask the assistant to involve a staff member, the request appears here." />
      )}
      {items && items.length > 0 && (
        <div className="space-y-3">
          {items.map((item) => (
            <Card key={item.id} className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-app-primary">{CATEGORY_LABELS[item.category] || "Request"}</p>
                <p className="mt-0.5 text-xs text-app-muted">
                  Case #{item.short_id} · Sent {formatDate(item.created_at)}
                  {item.resolved_at ? ` · Resolved ${formatDate(item.resolved_at)}` : ""}
                </p>
              </div>
              <Badge color={item.status === "resolved" ? "emerald2" : "amber"}>{item.status === "resolved" ? "Resolved" : "With staff"}</Badge>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
