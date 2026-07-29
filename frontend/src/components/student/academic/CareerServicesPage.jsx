import { Briefcase, Star, TrendingUp, Network } from "lucide-react";
import { PageHeader } from "../PageParts";
import { Card } from "../../ui";

export function CareerServicesPage() {
  return (
    <div>
      <PageHeader icon={Briefcase} title="Career Services" subtitle="Alumni career support and resources" />
      <div className="grid sm:grid-cols-2 gap-4">
        {[
          { title: "Executive Coaching", desc: "1-on-1 sessions with career coaches", icon: Briefcase },
          { title: "Job Board (Alumni)", desc: "Senior FinTech roles from our network", icon: Star },
          { title: "Salary Benchmarking", desc: "Compare your compensation with peers", icon: TrendingUp },
          { title: "Startup Office Hours", desc: "Mentor sessions for alumni founders", icon: Network },
        ].map((s, i) => {
          const Icon = s.icon;
          return (
            <Card key={i}>
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300 flex-shrink-0">
                  <Icon size={18} />
                </div>
                <div>
                  <h3 className="font-medium text-app-primary text-sm">{s.title}</h3>
                  <p className="text-sm text-app-muted mt-1">{s.desc}</p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
