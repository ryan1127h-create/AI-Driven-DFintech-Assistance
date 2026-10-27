import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, FileText, FileUp, Loader2, ShieldCheck } from "lucide-react";
import { getConsents, getLatestCvImport, importCv, updateConsents } from "../../../../api";
import { cn } from "../../../utils/cn";
import { formatDateTime } from "../../../utils/format";

// The CV step of profile setup: ask for the CV-processing consent if it's
// missing, upload a PDF or DOCX, then show what was found before the
// questionnaire opens with it pre-filled. A recent import can be reused
// instead of uploading again. onReady(cvImport) continues to the questions.

const STATUS = {
  new: { label: "Pre-filled", className: "bg-brand-500/10 text-brand-300" },
  same: { label: "Already on your profile", className: "bg-app-hover text-app-muted" },
  different: { label: "Differs from your profile", className: "bg-amber-500/15 text-amber-300" },
};

const ACCEPT = ".pdf,.docx";

function ImportSummary({ cvImport, onReady, onReplace }) {
  const fields = cvImport.fields || [];
  const differing = fields.filter((f) => f.status === "different").length;
  return (
    <div className="animate-fadeIn">
      <div className="card p-6">
        <p className="text-sm font-medium text-app-primary">
          {fields.length ? `Found ${fields.length} ${fields.length === 1 ? "detail" : "details"} in your CV` : "Nothing we could use was found in your CV"}
        </p>
        <p className="mt-0.5 text-xs text-app-muted">
          Read {formatDateTime(cvImport.parsed_at || cvImport.uploaded_at)}.
          {differing > 0 && ` ${differing} ${differing === 1 ? "differs" : "differ"} from what you've told us; review ${differing === 1 ? "it" : "them"} on your profile page.`}
        </p>
        {fields.length > 0 && (
          <ul className="mt-5 divide-y divide-app-subtle">
            {fields.map((field) => (
              <li key={field.field_key} className="flex items-start justify-between gap-4 py-3">
                <div className="min-w-0">
                  <p className="text-xs text-app-muted">{field.label}</p>
                  <p className="mt-0.5 text-sm text-app-primary">{field.display}</p>
                  <p className="mt-1 truncate text-xs italic text-app-faint" title={field.quote}>&ldquo;{field.quote}&rdquo;</p>
                </div>
                <span className={cn("chip flex-shrink-0 whitespace-nowrap", STATUS[field.status].className)}>
                  {STATUS[field.status].label}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="mt-6 flex items-center justify-between gap-3">
        <button type="button" className="btn-ghost px-2" onClick={onReplace}>Upload a different file</button>
        <button type="button" className="btn-primary whitespace-nowrap" onClick={() => onReady(cvImport)}>
          Review the questions <ArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}

export default function CvImport({ onReady, onBack }) {
  const [consented, setConsented] = useState(null);
  const [latest, setLatest] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    Promise.all([getConsents(), getLatestCvImport()])
      .then(([consents, cvImport]) => {
        setConsented(consents.some((c) => c.key === "consent_cv_processing" && c.granted));
        if (cvImport?.parse_status === "parsed") setLatest(cvImport);
      })
      .catch((err) => setError(err.message || "Unable to load CV import."));
  }, []);

  const grant = async () => {
    try {
      await updateConsents({ consent_cv_processing: true });
      setConsented(true);
    } catch (err) {
      setError(err.message || "Unable to save your choice.");
    }
  };

  const upload = async (file) => {
    if (!file) return;
    setError("");
    setUploading(true);
    try {
      setLatest(await importCv(file));
    } catch (err) {
      setError(err.message || "Your CV couldn't be read.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  if (latest && !uploading) {
    return <ImportSummary cvImport={latest} onReady={onReady} onReplace={() => setLatest(null)} />;
  }

  return (
    <div className="animate-fadeIn">
      {consented === false && (
        <label className="mb-4 flex cursor-pointer items-start gap-3 rounded-xl border border-brand-400/20 bg-brand-500/5 p-4">
          <input type="checkbox" className="mt-0.5 accent-brand-500" onChange={(e) => e.target.checked && grant()} />
          <span>
            <span className="block text-sm font-medium text-app-primary">Allow us to read my CV</span>
            <span className="mt-0.5 block text-xs text-app-muted">
              Your file is read once to fill in your profile and isn&apos;t stored. Only the details you keep are saved.
            </span>
          </span>
        </label>
      )}

      <button
        type="button"
        disabled={!consented || uploading}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (consented) upload(e.dataTransfer.files?.[0]); }}
        className={cn(
          "flex w-full flex-col items-center justify-center rounded-xl border border-dashed px-6 py-12 text-center transition",
          dragging ? "border-brand-400 bg-brand-500/10" : "border-app-input hover:border-brand-400/40 hover:bg-brand-500/5",
          (!consented || uploading) && "cursor-not-allowed opacity-60 hover:border-app-input hover:bg-transparent",
        )}
      >
        {uploading ? (
          <>
            <Loader2 size={28} className="animate-spin text-brand-300" />
            <p className="mt-3 text-sm font-medium text-app-primary">Reading your CV…</p>
            <p className="mt-1 text-xs text-app-muted">This usually takes 10 to 20 seconds.</p>
          </>
        ) : (
          <>
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-500/10 text-brand-300">
              <FileUp size={22} />
            </div>
            <p className="mt-3 text-sm font-medium text-app-primary">Drop your CV here, or choose a file</p>
            <p className="mt-1 text-xs text-app-muted">PDF or DOCX, up to 5 MB</p>
          </>
        )}
      </button>
      <input ref={inputRef} type="file" accept={ACCEPT} className="hidden" onChange={(e) => upload(e.target.files?.[0])} />

      {error && <p className="mt-4 text-sm text-red-300">{error}</p>}

      <div className="mt-6 flex items-start gap-2 text-xs text-app-muted">
        <ShieldCheck size={14} className="mt-0.5 flex-shrink-0" />
        <span>
          Only details your CV states are filled in, each with the line it came from. Work experience in years and your
          skill levels are always asked directly.
        </span>
      </div>

      <div className="mt-8 flex items-center justify-between">
        <button type="button" className="btn-ghost px-2" onClick={onBack} disabled={uploading}>
          <ArrowLeft size={14} /> Back
        </button>
        <span className="flex items-center gap-1.5 text-xs text-app-faint">
          <FileText size={12} /> Your file isn&apos;t stored
        </span>
      </div>
    </div>
  );
}
