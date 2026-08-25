import { FileText, Upload } from "lucide-react";
import { applicationStatus } from "../../../data/mock";
import { PageHeader, StatusBadge } from "../PageParts";
import { Card } from "../../ui";

export function DocumentsPage() {
  return (
    <div>
      <PageHeader icon={FileText} title="Documents" subtitle="Upload and manage your application documents" />
      <Card className="mb-4 border-dashed border-app-input">
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-300 mb-3">
            <Upload size={26} />
          </div>
          <p className="font-medium text-app-primary">Drag & drop files here</p>
          <p className="text-sm text-app-muted mt-1">PDF, JPG, PNG up to 10MB</p>
          <button className="btn-outline mt-4">Browse files</button>
        </div>
      </Card>
      <Card>
        <h3 className="font-display text-base font-semibold text-app-primary mb-3">Submitted Documents</h3>
        <div className="space-y-2">
          {applicationStatus.documents.map((d, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-app-hover">
              <FileText size={16} className="text-app-muted" />
              <span className="text-sm text-app-primary flex-1">{d.name}</span>
              <StatusBadge status={d.status} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
