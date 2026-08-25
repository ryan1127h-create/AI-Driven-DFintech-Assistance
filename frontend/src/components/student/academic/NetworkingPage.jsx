import { Network } from "lucide-react";
import { alumniDirectory } from "../../../data/mock";
import { PageHeader, StatusBadge } from "../PageParts";
import { Card, Badge } from "../../ui";

export function NetworkingPage() {
  return (
    <div>
      <PageHeader icon={Network} title="Networking" subtitle="Privacy-first alumni networking" />
      <Card className="mb-4 border-brand-400/15 bg-brand-500/5">
        <div className="flex items-start gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300 flex-shrink-0">
            <Network size={16} />
          </div>
          <div>
            <p className="text-sm font-medium text-app-primary">Privacy-First Networking</p>
            <p className="text-xs text-app-muted mt-0.5">All connections require consent-based matching. No direct messaging by default. Introduction requests only.</p>
          </div>
        </div>
      </Card>
      <div className="space-y-3">
        {alumniDirectory.map((a) => (
          <Card key={a.id}>
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-royal-500/15 text-royal-300 font-medium flex-shrink-0">{a.name.split(" ").map(n => n[0]).join("")}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-medium text-app-primary text-sm">{a.name}</p>
                  {a.verified && <Badge color="emerald2">Verified</Badge>}
                </div>
                <p className="text-xs text-app-muted">{a.role} · Class of {a.cohort}</p>
                <p className="text-xs text-app-secondary mt-1.5">{a.bio}</p>
                <div className="flex flex-wrap items-center gap-1.5 mt-2">
                  {a.expertise.map((e, i) => <Badge key={i} color="ink">{e}</Badge>)}
                </div>
              </div>
              <div className="flex flex-col items-end gap-2 flex-shrink-0">
                <StatusBadge status={a.connection} />
                {a.consent === "open" && <Badge color="emerald2">Consent: Open</Badge>}
                {a.consent === "introduction" && <Badge color="amber">Intro Only</Badge>}
                {a.consent === "closed" && <Badge color="red">Closed</Badge>}
              </div>
            </div>
            {a.consent !== "closed" && a.connection === "none" && (
              <button className="btn-outline w-full mt-3 text-xs">Request Introduction</button>
            )}
            {a.connection === "pending" && <button className="btn-outline w-full mt-3 text-xs" disabled>Request Pending</button>}
          </Card>
        ))}
      </div>
    </div>
  );
}
