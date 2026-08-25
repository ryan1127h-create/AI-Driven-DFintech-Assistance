import { Users } from "lucide-react";
import { alumniDirectory } from "../../../data/mock";
import { PageHeader } from "../PageParts";
import { Card, Badge } from "../../ui";

export function AlumniPreviewPage() {
  return (
    <div>
      <PageHeader icon={Users} title="Alumni Preview" subtitle="Get a glimpse of the alumni network you'll join" />
      <Card className="mb-4">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div><p className="font-display text-2xl font-bold text-app-primary">198</p><p className="text-xs text-app-muted">Alumni</p></div>
          <div><p className="font-display text-2xl font-bold text-app-primary">42</p><p className="text-xs text-app-muted">Companies</p></div>
          <div><p className="font-display text-2xl font-bold text-app-primary">12</p><p className="text-xs text-app-muted">Countries</p></div>
        </div>
      </Card>
      <div className="grid sm:grid-cols-2 gap-4">
        {alumniDirectory.slice(0, 4).map((a) => (
          <Card key={a.id}>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-royal-500/15 text-royal-300 font-medium text-sm">{a.name.split(" ").map(n => n[0]).join("")}</div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-app-primary text-sm truncate">{a.name}</p>
                <p className="text-xs text-app-muted truncate">{a.role}</p>
              </div>
              {a.verified && <Badge color="emerald2">Verified</Badge>}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
