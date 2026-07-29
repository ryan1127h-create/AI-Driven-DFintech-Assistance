import { Badge } from "../ui";
import { Loader2 } from "lucide-react";
import { cn } from "../../utils/cn";

export function LoadingState({ icon: Icon, title = "Loading", subtitle = "Fetching data from database…", variant = "spinner", rows = 3, className }) {
  if (variant === "skeleton") {
    return (
      <div className={cn("animate-in fade-in duration-300", className)}>
        <div className="flex items-center gap-3 mb-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/15 text-brand-300">
            {Icon && <Icon size={20} className="animate-pulse" />}
          </div>
          <div className="space-y-2">
            <div className="h-5 w-40 rounded-lg bg-app-hover animate-pulse" />
            <div className="h-3.5 w-56 rounded-lg bg-app-hover animate-pulse" />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: rows }).map((_, i) => (
            <div key={i} className="card p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="h-10 w-10 rounded-xl bg-app-hover animate-pulse" />
                <div className="h-5 w-16 rounded-full bg-app-hover animate-pulse" />
              </div>
              <div className="space-y-2.5">
                <div className="h-4 w-full rounded-lg bg-app-hover animate-pulse" />
                <div className="h-4 w-2/3 rounded-lg bg-app-hover animate-pulse" />
              </div>
              <div className="flex gap-2">
                <div className="h-6 w-20 rounded-full bg-app-hover animate-pulse" />
                <div className="h-6 w-14 rounded-full bg-app-hover animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col items-center justify-center py-20 text-center", className)}>
      <div className="relative mb-6">
        <div className="absolute inset-0 rounded-full bg-brand-500/20 blur-xl animate-pulse" />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-300">
          {Icon ? <Icon size={28} className="animate-pulse" /> : <Loader2 size={28} className="animate-spin" />}
        </div>
      </div>
      <h3 className="font-display text-lg font-semibold text-app-primary">{title}</h3>
      {subtitle && <p className="text-sm text-app-muted mt-1.5 max-w-xs">{subtitle}</p>}
      <div className="flex items-center gap-1.5 mt-5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 rounded-full bg-brand-400 animate-bounce"
            style={{ animationDelay: `${i * 150}ms`, animationDuration: "900ms" }}
          />
        ))}
      </div>
    </div>
  );
}

export function PageHeader({ icon: Icon, title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div className="flex items-center gap-3">
        {Icon && (
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/15 text-brand-300">
            <Icon size={20} />
          </div>
        )}
        <div>
          <h1 className="font-display text-xl font-bold text-app-primary">{title}</h1>
          {subtitle && <p className="text-sm text-app-muted mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

export function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-app-soft last:border-0">
      <span className="text-sm text-app-muted">{label}</span>
      <span className="text-sm font-medium text-app-primary">{value}</span>
    </div>
  );
}

export function StatusBadge({ status }) {
  const map = {
    verified: { color: "emerald2", label: "Verified" },
    missing: { color: "red", label: "Missing" },
    pending: { color: "amber", label: "Pending" },
    published: { color: "emerald2", label: "Published" },
    review: { color: "amber", label: "In Review" },
    draft: { color: "ink", label: "Draft" },
    met: { color: "emerald2", label: "Met" },
    inProgress: { color: "amber", label: "In Progress" },
    open: { color: "amber", label: "Open" },
    resolved: { color: "emerald2", label: "Resolved" },
    "in-progress": { color: "brand", label: "In Progress" },
    active: { color: "emerald2", label: "Active" },
    none: { color: "ink", label: "Not Connected" },
    connected: { color: "emerald2", label: "Connected" },
    accepted: { color: "emerald2", label: "Accepted" },
    assigned: { color: "brand", label: "Assigned" },
    waiting: { color: "amber", label: "Waiting User Response" },
    closed: { color: "ink", label: "Closed" },
    submitted: { color: "brand", label: "Submitted" },
    "under-review": { color: "amber", label: "Under Review" },
    interview: { color: "royal", label: "Interview" },
    offered: { color: "emerald2", label: "Offered" },
    rejected: { color: "red", label: "Rejected" },
    archived: { color: "ink", label: "Archived" },
  };
  const m = map[status] || { color: "ink", label: status };
  return <Badge color={m.color}>{m.label}</Badge>;
}
