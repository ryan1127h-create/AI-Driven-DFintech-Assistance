/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { AlertCircle, Check, Info, Link2, ListChecks, Minus, X } from "lucide-react";
import { bindApplication, getChecklist } from "../../api";
import { useRole } from "../context/RoleContext";
import { APPLICATION_STATUS_LABELS } from "../data/stages";
import { formatDate } from "../utils/format";
import { LoadingState, PageHeader } from "../components/student/PageParts";
import { Badge, Card, EmptyState, ProgressBar } from "../components/ui";

// The checklist is the school's record of the user's admission application:
// before an application is linked, the page only offers linking it (by
// application number); afterwards it shows the application overview and,
// per admissions document, whether the school has received it. Read-only —
// documents are submitted through the university's application system.

function BindApplicationCard({ onBound }) {
  const [applicationNo, setApplicationNo] = useState("");
  const [binding, setBinding] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    if (!applicationNo.trim()) return;
    setBinding(true);
    setError("");
    try {
      onBound(await bindApplication(applicationNo.trim()));
    } catch (err) {
      setError(err.message || "Unable to link this application.");
    } finally {
      setBinding(false);
    }
  };

  return (
    <Card>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300">
          <Link2 size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-app-primary">Link your application</p>
          <p className="text-xs text-app-muted mt-1">
            Enter your application number to see your application status and document checklist. The
            application must have been submitted with the same email you log in with.
          </p>
          <form onSubmit={submit} className="mt-4 flex flex-wrap items-center gap-2">
            <input
              className="input max-w-xs"
              placeholder="Application number"
              value={applicationNo}
              maxLength={64}
              onChange={(e) => setApplicationNo(e.target.value)}
            />
            <button type="submit" className="btn-primary" disabled={binding || !applicationNo.trim()}>
              {binding ? "Linking..." : "Link application"}
            </button>
          </form>
          {error && <p className="text-xs text-red-300 mt-2">{error}</p>}
        </div>
      </div>
    </Card>
  );
}

// Each document's state comes from the backend (app/domains/sis/documents.py):
// only "missing" is something the user still has to send.
const DOCUMENT_GROUPS = [
  { state: "missing", title: "Still missing", hint: "The school is waiting for these.", label: "Missing", color: "red", icon: X },
  { state: "received", title: "Received", hint: null, label: "Received", color: "emerald2", icon: Check },
  { state: "optional", title: "Only if they apply to you", hint: "Not required from everyone; the note says whether you need it.", label: "If applicable", color: "ink", icon: Info },
  { state: "exempt", title: "Not required for you", hint: "Your degree was taught in English, so you don't need an English test.", label: "Exempt", color: "ink", icon: Check },
  { state: "not_needed", title: "No longer needed", hint: "Your application has been decided, so the school isn't waiting for these.", label: "Not needed", color: "ink", icon: Minus },
];

function ApplicationOverview({ application }) {
  const documents = application.documents || [];
  // Progress counts what everyone must send; optional documents don't hold it back.
  const required = documents.filter((doc) => doc.state === "missing" || (doc.required && doc.state === "received"));
  const received = required.filter((doc) => doc.state === "received").length;
  const missing = documents.filter((doc) => doc.state === "missing").length;
  const percent = required.length ? Math.round((received / required.length) * 100) : 0;
  const details = [
    ["Application number", application.application_no],
    ["Admission term", application.admission_term],
    ["Submitted on", formatDate(application.submission_date)],
  ].filter(([, value]) => value);

  return (
    <Card className="mb-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs text-app-muted">Application status</p>
          <p className="font-display text-lg font-semibold text-app-primary mt-0.5">
            {application.status_label || application.status || "Unknown"}
          </p>
        </div>
        {application.status && <Badge color="brand">{APPLICATION_STATUS_LABELS[application.status] || application.status}</Badge>}
      </div>

      {details.length > 0 && (
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
          {details.map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs text-app-muted">{label}</dt>
              <dd className="text-sm text-app-primary">{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {application.next_step && (
        <p className="text-xs text-app-secondary mt-4">Next step: {application.next_step}</p>
      )}

      {required.length > 0 && (
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-app-secondary">Required documents received</span>
            <span className="text-app-primary font-medium">
              {received}/{required.length} · {percent}%
            </span>
          </div>
          <ProgressBar value={received} max={required.length} color={missing ? "brand" : "emerald2"} />
          <p className={`text-xs ${missing ? "text-red-300" : "text-app-muted"}`}>
            {missing ? `${missing} document${missing === 1 ? "" : "s"} still missing` : "Nothing is missing"}
          </p>
        </div>
      )}
    </Card>
  );
}

function DocumentCard({ doc, group }) {
  const Icon = group.icon;
  return (
    <Card className="flex items-start gap-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-app-primary">{doc.label || doc.item_key}</p>
        {doc.description && <p className="text-xs text-app-muted mt-1">{doc.description}</p>}
      </div>
      <Badge color={group.color} className="flex-shrink-0 inline-flex items-center gap-1">
        <Icon size={12} aria-hidden="true" />
        {group.label}
      </Badge>
    </Card>
  );
}

function DocumentGroups({ documents }) {
  return DOCUMENT_GROUPS.map((group) => {
    const docs = documents.filter((doc) => doc.state === group.state);
    if (!docs.length) return null;
    return (
      <section key={group.state} className="mt-5" aria-label={group.title}>
        <h2 className="text-sm font-semibold text-app-primary">
          {group.title} <span className="font-normal text-app-muted">({docs.length})</span>
        </h2>
        {group.hint && <p className="text-xs text-app-muted mt-0.5">{group.hint}</p>}
        <div className="mt-2 space-y-2">
          {docs.map((doc) => <DocumentCard key={doc.item_key} doc={doc} group={group} />)}
        </div>
      </section>
    );
  });
}

export default function ChecklistPage() {
  const { refreshUser } = useRole();
  const [checklist, setChecklist] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getChecklist()
      .then(setChecklist)
      .catch((err) => setError(err.message || "Unable to load checklist."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <LoadingState icon={ListChecks} title="Loading checklist" subtitle="Checking your application..." />;
  }

  const application = checklist?.application;
  const stage = checklist?.lifecycle_stage;

  return (
    <div>
      <PageHeader
        icon={ListChecks}
        title="Checklist"
        subtitle={application ? "Your application and the documents the school has received" : "Link your application"}
      />

      {error && (
        <Card className="mb-4 border border-red-400/30 bg-red-500/10">
          <p className="text-sm text-red-300">{error}</p>
        </Card>
      )}

      {application ? (
        <>
          <ApplicationOverview application={application} />
          <DocumentGroups documents={application.documents || []} />
        </>
      ) : !stage || stage === "prospect" ? (
        <BindApplicationCard
          onBound={(bound) => {
            setChecklist(bound);
            refreshUser();
          }}
        />
      ) : (
        !error && (
          <Card>
            <EmptyState
              icon={AlertCircle}
              title="No application linked"
              subtitle="There is no admission application on file for your account."
            />
          </Card>
        )
      )}
    </div>
  );
}
