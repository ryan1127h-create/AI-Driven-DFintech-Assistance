import { CalendarPlus } from "lucide-react";
import { PageHeader } from "../PageParts";
import { Card, Badge } from "../../ui";

export function RegistrationPage() {
  return (
    <div>
      <PageHeader icon={CalendarPlus} title="Module Registration" subtitle="Register for your first semester modules" />
      <Card>
        <h3 className="font-display text-base font-semibold text-app-primary mb-3">Recommended First Semester</h3>
        <div className="space-y-2">
          {[
            { code: "IS5452", name: "Digital Banking & Innovation", credits: 4, status: "Available" },
            { code: "IS5152", name: "FinTech Innovation & Smart Contracts", credits: 4, status: "Available" },
            { code: "CS5340", name: "Quantitative Reasoning for FinTech", credits: 4, status: "Available" },
          ].map((m) => (
            <div key={m.code} className="flex items-center gap-3 p-3 rounded-lg bg-app-hover">
              <span className="font-mono text-xs text-brand-300 w-16">{m.code}</span>
              <span className="text-sm text-app-primary flex-1">{m.name}</span>
              <Badge color="ink">{m.credits} cr</Badge>
              <Badge color="emerald2">{m.status}</Badge>
            </div>
          ))}
        </div>
        <button className="btn-primary w-full mt-4">Register Modules</button>
      </Card>
    </div>
  );
}
