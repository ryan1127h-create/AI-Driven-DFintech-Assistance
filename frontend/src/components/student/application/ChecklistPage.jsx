import { useEffect, useMemo, useRef, useState } from "react";
import { ListChecks, CheckCircle, Upload, AlertCircle, FileText } from "lucide-react";
import { getChecklist, uploadChecklistItemFile } from "../../../../api";
import { LoadingState, PageHeader } from "../PageParts";
import { Badge, Card, EmptyState, ProgressBar } from "../../ui";

const COMPLETE_STATES = new Set(["completed", "not_applicable"]);

function requirementBadge(requirement) {
  if (requirement === "required") return { color: "red", label: "Required" };
  if (requirement === "conditional") return { color: "amber", label: "Conditional" };
  if (requirement === "recommended") return { color: "brand", label: "Recommended" };
  return { color: "ink", label: "Optional" };
}

function statusBadge(status) {
  if (status === "completed") return { color: "emerald2", label: "Uploaded" };
  if (status === "in_progress") return { color: "amber", label: "In progress" };
  if (status === "not_applicable") return { color: "ink", label: "Not applicable" };
  if (status === "not_started") return { color: "ink", label: "Not uploaded" };
  return { color: "ink", label: "Unknown" };
}

function formatBytes(size) {
  if (!Number.isFinite(size) || size <= 0) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function ChecklistPage() {
  const [checklist, setChecklist] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploadingId, setUploadingId] = useState("");
  const fileInputRefs = useRef({});

  const loadChecklist = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getChecklist();
      setChecklist(response);
    } catch (err) {
      setError(err.message || "Unable to load checklist.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadChecklist();
  }, []);

  const items = checklist?.items || [];
  const completedCount = useMemo(
    () => items.filter((item) => COMPLETE_STATES.has(item.status)).length,
    [items],
  );

  const onUploadClick = (itemId) => {
    fileInputRefs.current[itemId]?.click();
  };

  const onSelectFile = async (item, event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setUploadingId(item.id);
    setError("");
    try {
      const updated = await uploadChecklistItemFile(item.id, file);
      setChecklist(updated);
    } catch (err) {
      setError(err.message || `Unable to upload file for ${item.title}.`);
    } finally {
      setUploadingId("");
    }
  };

  if (loading) {
    return (
      <LoadingState
        icon={ListChecks}
        title="Loading checklist"
        subtitle="Checking your uploaded documents and missing items..."
      />
    );
  }

  if (!items.length) {
    return (
      <div>
        <PageHeader icon={ListChecks} title="Checklist" subtitle="Upload required files for your application" />
        <Card>
          <EmptyState
            icon={AlertCircle}
            title="No checklist items available"
            subtitle="Checklist items are not available for your account yet."
          />
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        icon={ListChecks}
        title="Checklist"
        subtitle={`${completedCount} of ${items.length} items uploaded`}
      />

      {error && (
        <Card className="mb-4 border border-red-400/30 bg-red-500/10">
          <p className="text-sm text-red-300">{error}</p>
        </Card>
      )}

      <Card className="mb-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-app-secondary">Upload progress</span>
            <span className="text-app-primary font-medium">{completedCount}/{items.length}</span>
          </div>
          <ProgressBar value={completedCount} max={items.length} color="brand" />
          {typeof checklist?.outstanding_required_count === "number" && (
            <p className="text-xs text-app-muted">
              Outstanding required items: <span className="text-app-primary font-medium">{checklist.outstanding_required_count}</span>
            </p>
          )}
        </div>
      </Card>

      <div className="space-y-2">
        {items.map((item) => {
          const req = requirementBadge(item.requirement);
          const status = statusBadge(item.status);
          const isDone = COMPLETE_STATES.has(item.status);
          const isUploading = uploadingId === item.id;

          return (
            <Card key={item.id} className="flex flex-col gap-3">
              <div className="flex items-start gap-3">
                <div className={`mt-0.5 flex h-6 w-6 items-center justify-center rounded-md ${isDone ? "bg-emerald2-500" : "bg-app-hover"}`}>
                  {isDone ? <CheckCircle size={14} className="text-app-primary" /> : <FileText size={14} className="text-app-faint" />}
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-app-primary">{item.title}</p>
                  {item.description && <p className="text-xs text-app-muted mt-1">{item.description}</p>}
                  <div className="flex flex-wrap items-center gap-2 mt-2">
                    <Badge color={req.color}>{req.label}</Badge>
                    <Badge color={status.color}>{status.label}</Badge>
                    {item.file_name && <Badge color="ink">{item.file_name}</Badge>}
                    {item.file_size ? <Badge color="ink">{formatBytes(item.file_size)}</Badge> : null}
                  </div>
                </div>

                <div className="flex-shrink-0">
                  <input
                    ref={(el) => {
                      fileInputRefs.current[item.id] = el;
                    }}
                    type="file"
                    className="hidden"
                    onChange={(event) => onSelectFile(item, event)}
                    accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
                  />
                  <button
                    type="button"
                    onClick={() => onUploadClick(item.id)}
                    disabled={isUploading}
                    className="btn-outline"
                  >
                    <Upload size={14} />
                    {isUploading ? "Uploading..." : isDone ? "Replace file" : "Upload"}
                  </button>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      
    </div>
  );
}
