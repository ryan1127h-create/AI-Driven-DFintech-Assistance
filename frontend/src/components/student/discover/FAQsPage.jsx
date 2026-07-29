import { HelpCircle } from "lucide-react";
import { faqs } from "../../../data/programme";
import { PageHeader } from "../PageParts";
import { Card } from "../../ui";

export function FAQsPage() {
  return (
    <div>
      <PageHeader icon={HelpCircle} title="Frequently Asked Questions" subtitle="Common questions about the MSc DFT programme" />
      <div className="space-y-3">
        {faqs.map((f, i) => (
          <Card key={i}>
            <details className="group">
              <summary className="flex items-center justify-between cursor-pointer list-none">
                <span className="font-medium text-app-primary text-sm">{f.q}</span>
                <span className="text-app-muted group-open:rotate-180 transition-transform">⌄</span>
              </summary>
              <p className="mt-3 text-sm text-app-secondary leading-relaxed">{f.a}</p>
            </details>
          </Card>
        ))}
      </div>
    </div>
  );
}
