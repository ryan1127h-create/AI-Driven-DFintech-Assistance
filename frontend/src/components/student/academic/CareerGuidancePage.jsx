import { Briefcase } from "lucide-react";
import { PageHeader } from "../PageParts";
import { Card, Badge, ProgressBar } from "../../ui";

export function CareerGuidancePage() {
  return (
    <div>
      <PageHeader icon={Briefcase} title="Career Guidance" subtitle="AI-powered career path recommendations" />
      <Card className="mb-4">
        <h3 className="font-display text-base font-semibold text-app-primary mb-3">Recommended Paths</h3>
        <div className="space-y-3">
          {[
            { role: "FinTech Product Manager", match: 92, reason: "Your finance background + tech coursework align well" },
            { role: "Quantitative Analyst", match: 85, reason: "Strong quant modules and ML track" },
            { role: "Blockchain Engineer", match: 78, reason: "CS6204 completed, capstone in DeFi" },
          ].map((p, i) => (
            <div key={i} className="p-3 rounded-lg bg-app-hover">
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-app-primary text-sm">{p.role}</span>
                <Badge color="emerald2">{p.match}% match</Badge>
              </div>
              <p className="text-xs text-app-muted">{p.reason}</p>
              <ProgressBar value={p.match} color="emerald2" className="mt-2" />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
