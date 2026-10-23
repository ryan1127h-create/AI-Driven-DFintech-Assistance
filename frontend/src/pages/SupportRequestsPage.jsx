import { useEffect, useMemo, useState } from "react";
import { Filter, LifeBuoy, Search } from "lucide-react";
import { getMyEscalations } from "../../api";
import { formatDate } from "../utils/format";
import { LoadingState, PageHeader } from "../components/student/PageParts";
import { Card, EmptyState } from "../components/ui";

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
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("latest");
  useEffect(() => {
    getMyEscalations().then((data) => setItems(data.items || [])).catch((err) => setError(err.message || "Unable to load your requests."));
  }, []);

  const visibleItems = useMemo(() => {
    if (!items) return [];
    const normalizedQuery = query.trim().toLowerCase();
    return items
      .filter((item) => {
        const label = CATEGORY_LABELS[item.category] || "Request";
        const matchesQuery = !normalizedQuery || [label, item.category, item.short_id].some((value) => String(value || "").toLowerCase().includes(normalizedQuery));
        const matchesStatus = status === "all" || (status === "resolved" ? item.status === "resolved" : item.status !== "resolved");
        return matchesQuery && matchesStatus;
      })
      .sort((a, b) => {
        const direction = sort === "latest" ? -1 : 1;
        return direction * (new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
      });
  }, [items, query, sort, status]);

  return (
    <div className="support-requests-page animate-fadeIn">
      <PageHeader icon={LifeBuoy} title="Requests to Staff" subtitle="Conversations the assistant passed to the programme office, and where they stand." />
      <div className="support-request-note" role="note"><LifeBuoy size={16} /><span>Staff replies will be sent to you through your registered email service.</span></div>
      {error && <p role="alert" className="support-error mb-4 text-sm">{error}</p>}
      {!items && !error && <LoadingState title="Loading your requests" subtitle="" />}
      {items && !items.length && (
        <EmptyState icon={LifeBuoy} title="No requests yet" subtitle="If you ask the assistant to involve a staff member, the request appears here." />
      )}
      {items && items.length > 0 && (
        <>
          <div className="support-request-toolbar" role="search">
            <label className="support-request-search"><Search size={16} /><input aria-label="Search requests" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search requests" /></label>
            <label className="support-request-select"><Filter size={15} /><select aria-label="Filter requests by status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option><option value="open">With staff</option><option value="resolved">Resolved</option></select></label>
            <label className="support-request-select"><select aria-label="Sort requests" value={sort} onChange={(event) => setSort(event.target.value)}><option value="latest">Latest first</option><option value="oldest">Oldest first</option></select></label>
            <button type="button" className="support-request-reset" onClick={() => { setQuery(""); setStatus("all"); setSort("latest"); }} disabled={!query && status === "all" && sort === "latest"}>Reset</button>
          </div>
          <div className="support-request-list space-y-3">
          {visibleItems.map((item) => (
            <Card key={item.id} className="support-request-card">
              <div className="support-request-main">
                <div className="support-request-copy">
                  <div className="support-request-eyebrow"><span>STAFF REQUEST</span><span className="support-request-id">#{item.short_id}</span></div>
                  <p className="support-request-title">{CATEGORY_LABELS[item.category] || "Request"}</p>
                  <p className="support-request-meta">
                  Case #{item.short_id} · Sent {formatDate(item.created_at)}
                  {item.resolved_at ? ` · Resolved ${formatDate(item.resolved_at)}` : ""}
                  </p>
                </div>
                <div className={`support-request-status ${item.status === "resolved" ? "is-resolved" : "is-open"}`}><span aria-hidden="true" />{item.status === "resolved" ? "Resolved" : "With staff"}</div>
              </div>
              <ol className="support-request-timeline" aria-label="Request progress">
                <li className="is-complete"><span className="timeline-dot" />Submitted</li>
                <li className={item.status === "resolved" ? "is-complete" : "is-current"}><span className="timeline-dot" />With staff</li>
                <li className={item.status === "resolved" ? "is-complete" : "is-upcoming"}><span className="timeline-dot" />Resolved</li>
              </ol>
            </Card>
          ))}
          {!visibleItems.length && <div className="support-request-no-results">No requests match your search or filters.</div>}
          </div>
        </>
      )}
    </div>
  );
}
