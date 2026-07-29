import { Briefcase, FileText, Users, Star } from "lucide-react";
import { PageHeader } from "../PageParts";
import { Card } from "../../ui";

export function CareerPrepPage() {
  return (
    <div>
      <PageHeader icon={Briefcase} title="Career Preparation" subtitle="Get ready for your job search" />
      <div className="grid sm:grid-cols-2 gap-4">
        {[
          { title: "Resume Review", desc: "AI-powered resume feedback tailored to FinTech roles", icon: FileText },
          { title: "Mock Interviews", desc: "Practice with AI interviewer for quant and product roles", icon: Users },
          { title: "Portfolio Builder", desc: "Showcase capstone and coursework projects", icon: Star },
          { title: "Job Board", desc: "Curated FinTech roles from industry partners", icon: Briefcase },
        ].map((c, i) => {
          const Icon = c.icon;
          return (
            <Card key={i}>
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300 flex-shrink-0">
                  <Icon size={18} />
                </div>
                <div>
                  <h3 className="font-medium text-app-primary text-sm">{c.title}</h3>
                  <p className="text-sm text-app-muted mt-1">{c.desc}</p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
