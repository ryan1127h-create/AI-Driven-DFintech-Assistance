import { BookOpen, Network, FileText, Users } from "lucide-react";
import { PageHeader } from "../PageParts";
import { Card } from "../../ui";

export function LearningResourcesPage() {
  return (
    <div>
      <PageHeader icon={BookOpen} title="Learning Resources" subtitle="Study materials, labs, and support services" />
      <div className="grid sm:grid-cols-2 gap-4">
        {[
          { name: "NUS Libraries", desc: "Central Library, Science Library, and digital resources", icon: BookOpen },
          { name: "FinTech Lab", desc: "Hands-on lab with trading terminals and blockchain nodes", icon: Network },
          { name: "Writing Centre", desc: "Academic writing support for assignments and thesis", icon: FileText },
          { name: "Peer Tutoring", desc: "Senior students provide tutoring for core modules", icon: Users },
        ].map((r, i) => {
          const Icon = r.icon;
          return (
            <Card key={i}>
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300 flex-shrink-0">
                  <Icon size={18} />
                </div>
                <div>
                  <h3 className="font-medium text-app-primary text-sm">{r.name}</h3>
                  <p className="text-sm text-app-muted mt-1">{r.desc}</p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
