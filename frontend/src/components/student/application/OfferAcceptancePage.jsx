import { CheckCircle } from "lucide-react";
import { PageHeader } from "../PageParts";
import { Card } from "../../ui";

export function OfferAcceptancePage() {
  return (
    <div>
      <PageHeader icon={CheckCircle} title="Offer Acceptance" subtitle="Accept your admission offer" />
      <Card className="border-emerald2-400/20 bg-emerald2-500/5 mb-4">
        <div className="flex items-center gap-3">
          <CheckCircle size={24} className="text-emerald2-400" />
          <div>
            <p className="font-display text-lg font-bold text-app-primary">Congratulations!</p>
            <p className="text-sm text-app-secondary">You have been offered admission to MSc DFT, August 2026 intake.</p>
          </div>
        </div>
      </Card>
      <Card>
        <h3 className="font-display text-base font-semibold text-app-primary mb-3">Next Steps</h3>
        <div className="space-y-2">
          {["Review offer letter", "Pay acceptance fee (S$500)", "Submit offer acceptance form", "Complete medical check-up", "Apply for student pass (international)"].map((s, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-app-hover">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-500/15 text-brand-300 text-xs font-medium">{i + 1}</span>
              <span className="text-sm text-app-primary">{s}</span>
            </div>
          ))}
        </div>
        <button className="btn-primary w-full mt-4">Accept Offer</button>
      </Card>
    </div>
  );
}
