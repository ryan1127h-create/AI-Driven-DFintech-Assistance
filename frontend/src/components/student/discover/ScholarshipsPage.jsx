import { DollarSign } from "lucide-react";
import { PageHeader } from "../PageParts";
import { Card } from "../../ui";

export function ScholarshipsPage() {
  const scholarships = [
    { name: "NUS Graduate Scholarship", amount: "Full tuition + S$2,000/mo stipend", criteria: "Outstanding academic record, CAP 4.5+" },
    { name: "ASEAN Scholarship", amount: "Partial tuition subsidy", criteria: "ASEAN nationals, leadership potential" },
    { name: "FinTech Industry Scholarship", amount: "S$20,000 + internship", criteria: "FinTech career commitment, industry sponsor" },
    { name: "Women in Tech Scholarship", amount: "S$15,000", criteria: "Female students pursuing FinTech careers" },
  ];
  return (
    <div>
      <PageHeader icon={DollarSign} title="Scholarships & Financial Aid" subtitle="Available funding for MSc DFT students" />
      <div className="grid sm:grid-cols-2 gap-4">
        {scholarships.map((s, i) => (
          <Card key={i}>
            <h3 className="font-display text-base font-semibold text-app-primary mb-1">{s.name}</h3>
            <p className="text-sm text-emerald2-400 font-medium mb-2">{s.amount}</p>
            <p className="text-sm text-app-muted">{s.criteria}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
