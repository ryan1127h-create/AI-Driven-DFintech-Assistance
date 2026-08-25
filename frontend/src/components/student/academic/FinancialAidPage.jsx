import { DollarSign } from "lucide-react";
import { PageHeader } from "../PageParts";
import { Card } from "../../ui";

export function FinancialAidPage() {
  return (
    <div>
      <PageHeader icon={DollarSign} title="Financial Aid" subtitle="Loans, bursaries, and financial support" />
      <div className="grid sm:grid-cols-2 gap-4">
        {[
          { name: "NUS Study Loan", amount: "Up to S$5,000/yr", rate: "0% interest (study period)" },
          { name: "Tuition Fee Loan (DBS/OCBC)", amount: "Up to 90% tuition", rate: "Prime - 0.5%" },
          { name: "Mendaki Tertiary Tuition Fee", amount: "Up to S$2,000/yr", rate: "Subsidised" },
          { name: "Bursary (Need-based)", amount: "S$3,500-6,500/yr", rate: "Grant" },
        ].map((a, i) => (
          <Card key={i}>
            <h3 className="font-display text-base font-semibold text-app-primary">{a.name}</h3>
            <p className="text-sm text-emerald2-400 font-medium mt-1">{a.amount}</p>
            <p className="text-sm text-app-muted mt-1">{a.rate}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
