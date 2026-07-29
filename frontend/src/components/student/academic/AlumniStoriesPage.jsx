import { Star } from "lucide-react";
import { alumniDirectory } from "../../../data/mock";
import { PageHeader } from "../PageParts";
import { Card, Badge } from "../../ui";

export function AlumniStoriesPage() {
  return (
    <div>
      <PageHeader icon={Star} title="Alumni Stories" subtitle="Success stories from the DFT community" />
      <div className="space-y-4">
        {alumniDirectory.slice(0, 3).map((a) => (
          <Card key={a.id}>
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-royal-500/15 text-royal-300 font-medium flex-shrink-0">{a.name.split(" ").map(n => n[0]).join("")}</div>
              <div>
                <p className="font-medium text-app-primary">{a.name}</p>
                <p className="text-sm text-brand-300">{a.role}</p>
                <p className="text-sm text-app-secondary mt-2 leading-relaxed">{a.bio}</p>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {a.expertise.map((e, i) => <Badge key={i} color="ink">{e}</Badge>)}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
