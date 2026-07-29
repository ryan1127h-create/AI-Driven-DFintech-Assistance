import { Compass, CheckCircle, Calendar } from "lucide-react";
import { programme } from "../../../data/programme";
import { PageHeader, InfoRow } from "../PageParts";
import { Card } from "../../ui";

export function DiscoverOverview() {
  return (
    <div>
      <PageHeader icon={Compass} title="Programme Overview" subtitle="MSc in Digital Financial Technology · NUS School of Computing" />
      <div className="grid lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <h3 className="font-display text-lg font-semibold text-app-primary mb-3">About the Programme</h3>
          <p className="text-app-secondary leading-relaxed">{programme.overview}</p>
          <div className="mt-5 space-y-2">
            {programme.highlights.map((h, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <CheckCircle size={16} className="text-emerald2-400 flex-shrink-0 mt-0.5" />
                <span className="text-sm text-app-primary">{h}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-3">Key Facts</h3>
          <InfoRow label="Duration" value={programme.duration} />
          <InfoRow label="Intake" value={programme.intake} />
          <InfoRow label="Tuition" value={programme.tuition} />
          <InfoRow label="Min. Score" value={programme.minScore} />
          <InfoRow label="App. Fee" value={programme.applicationFee} />
          <div className="mt-4 p-3 rounded-lg bg-brand-500/10 border border-brand-400/20">
            <div className="flex items-center gap-2 mb-1">
              <Calendar size={14} className="text-brand-300" />
              <span className="text-xs font-medium text-brand-300">Application Deadline</span>
            </div>
            <p className="text-sm text-app-primary">{programme.deadlines.close}</p>
          </div>
        </Card>
      </div>
      <Card className="mt-4">
        <h3 className="font-display text-base font-semibold text-app-primary mb-3">Eligibility Requirements</h3>
        <div className="grid sm:grid-cols-2 gap-2">
          {programme.eligibility.map((e, i) => (
            <div key={i} className="flex items-start gap-2.5 p-3 rounded-lg bg-app-hover">
              <CheckCircle size={16} className="text-brand-300 flex-shrink-0 mt-0.5" />
              <span className="text-sm text-app-primary">{e}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
