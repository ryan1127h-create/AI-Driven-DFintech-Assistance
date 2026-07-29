import { useState } from "react";
import {
  FileText, Clock,
  Search, CheckCircle, XCircle,
  ArrowLeft, AlertCircle,
} from "lucide-react";
import {
  applicationsList, applicationStatuses,
} from "../../../data/mock";
import { Card, Badge, ProgressBar, EmptyState } from "../../ui";
import { PageHeader, StatusBadge } from "../../student/PageParts";

// ============ APPLICATIONS WITH ADVANCED FILTERING ============

export function ApplicationsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [intakeFilter, setIntakeFilter] = useState("all");
  const [sortBy, setSortBy] = useState("date");
  const [selectedApp, setSelectedApp] = useState(null);

  const filtered = applicationsList
    .filter((a) => {
      const matchSearch = !search || a.applicant.toLowerCase().includes(search.toLowerCase()) || a.id.toLowerCase().includes(search.toLowerCase()) || a.email.toLowerCase().includes(search.toLowerCase());
      const matchStatus = statusFilter === "all" || a.status === statusFilter;
      const matchIntake = intakeFilter === "all" || a.intake === intakeFilter;
      return matchSearch && matchStatus && matchIntake;
    })
    .sort((a, b) => {
      if (sortBy === "date") return new Date(b.submittedDate || 0) - new Date(a.submittedDate || 0);
      if (sortBy === "name") return a.applicant.localeCompare(b.applicant);
      if (sortBy === "progress") return b.progress - a.progress;
      return 0;
    });

  if (selectedApp) {
    const app = applicationsList.find((a) => a.id === selectedApp.id) || selectedApp;
    return (
      <div>
        <button onClick={() => setSelectedApp(null)} className="btn-ghost mb-4 text-xs">
          <ArrowLeft size={14} /> Back to Applications
        </button>
        <Card className="mb-4">
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="font-mono text-xs text-brand-300">{app.id}</p>
              <h2 className="font-display text-lg font-bold text-app-primary mt-1">{app.applicant}</h2>
              <p className="text-sm text-app-muted">{app.email} · {app.nationality}</p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={app.status} />
            </div>
          </div>
          <div className="grid sm:grid-cols-4 gap-3 pt-3 border-t border-app-subtle">
            <div><p className="text-xs text-app-faint">Intake</p><p className="text-sm text-app-primary">{app.intake}</p></div>
            <div><p className="text-xs text-app-faint">Submitted</p><p className="text-sm text-app-primary">{app.submittedDate || "Not submitted"}</p></div>
            <div><p className="text-xs text-app-faint">Last Updated</p><p className="text-sm text-app-primary">{app.lastUpdated}</p></div>
            <div><p className="text-xs text-app-faint">Progress</p><p className="text-sm text-app-primary">{app.progress}%</p></div>
          </div>
          <div className="mt-3"><ProgressBar value={app.progress} color="brand" /></div>
        </Card>
        <Card className="mb-4">
          <h3 className="font-display text-base font-semibold text-app-primary mb-3">Application Progress</h3>
          <div className="space-y-2">
            {app.documents.map((d, i) => (
              <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-app-hover">
                {d.status === "verified" ? <CheckCircle size={16} className="text-emerald2-400" /> : d.status === "missing" ? <AlertCircle size={16} className="text-red-400" /> : <Clock size={16} className="text-amber-400" />}
                <span className="text-sm text-app-primary flex-1">{d.name}</span>
                <StatusBadge status={d.status} />
              </div>
            ))}
          </div>
        </Card>
        {app.missingDocuments.length > 0 && (
          <Card className="border-red-400/20 bg-red-500/5">
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle size={16} className="text-red-400" />
              <h3 className="font-display text-base font-semibold text-app-primary">Missing Documents</h3>
            </div>
            <ul className="space-y-1">
              {app.missingDocuments.map((d, i) => (
                <li key={i} className="text-sm text-app-secondary flex items-center gap-2">
                  <XCircle size={12} className="text-red-400" /> {d}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    );
  }

  return (
    <div>
      <PageHeader icon={FileText} title="Applications" subtitle="Manage programme applications" />

      {/* Search + Filters */}
      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-[200px]">
            <Search size={16} className="text-app-faint" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by name, ID, or email..." className="flex-1 bg-transparent text-sm text-app-primary placeholder:text-app-faint focus:outline-none" />
          </div>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input text-xs w-auto">
            <option value="all">All Statuses</option>
            {applicationStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={intakeFilter} onChange={(e) => setIntakeFilter(e.target.value)} className="input text-xs w-auto">
            <option value="all">All Intakes</option>
            <option value="Aug 2026">Aug 2026</option>
            <option value="Aug 2025">Aug 2025</option>
          </select>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="input text-xs w-auto">
            <option value="date">Sort: Date</option>
            <option value="name">Sort: Name</option>
            <option value="progress">Sort: Progress</option>
          </select>
        </div>
      </Card>

      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-app-subtle">
              <th className="text-left py-3 px-3 text-app-muted font-medium">Application ID</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Applicant</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Intake</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Progress</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Missing Docs</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Status</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Last Updated</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((a) => (
              <tr key={a.id} className="border-b border-app-soft hover:bg-app-hover transition cursor-pointer" onClick={() => setSelectedApp(a)}>
                <td className="py-3 px-3 font-mono text-xs text-brand-300">{a.id}</td>
                <td className="py-3 px-3 text-app-primary">{a.applicant}<p className="text-[10px] text-app-faint">{a.nationality}</p></td>
                <td className="py-3 px-3 text-app-secondary text-xs">{a.intake}</td>
                <td className="py-3 px-3 w-32"><ProgressBar value={a.progress} color="brand" /></td>
                <td className="py-3 px-3 text-xs">{a.missingDocuments.length === 0 ? <Badge color="emerald2">Complete</Badge> : <Badge color="red">{a.missingDocuments.length} missing</Badge>}</td>
                <td className="py-3 px-3"><StatusBadge status={a.status} /></td>
                <td className="py-3 px-3 text-xs text-app-faint">{a.lastUpdated}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && <EmptyState icon={FileText} title="No applications found" subtitle="Try adjusting your search or filters" />}
      </Card>
    </div>
  );
}
