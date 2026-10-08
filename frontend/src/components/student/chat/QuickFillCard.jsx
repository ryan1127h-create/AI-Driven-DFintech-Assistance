import { useEffect, useState } from "react";
import { CheckCircle2, ClipboardList, Loader2 } from "lucide-react";
import { updateProfile } from "../../../../api";
import QuestionField from "../onboarding/QuestionField";
import { loadDictionary, loadProfileValues, profileChanges } from "./profileWrites";

const isEmpty = (value) => value === null || value === undefined || (Array.isArray(value) && !value.length);

// The fields a reply asked for (see backend ToolAnswer.card), answered in
// place: saved to the profile, then the user's question is asked again.
// Only the latest reply's card can be answered; once the conversation has
// moved on, a card that wasn't used disappears.
export default function QuickFillCard({ card, active, onAnswered }) {
  const [dictionary, setDictionary] = useState(null);
  const [current, setCurrent] = useState({});
  const [values, setValues] = useState({});
  const [status, setStatus] = useState("idle"); // idle | saving | saved
  const [error, setError] = useState("");

  useEffect(() => {
    if (!active) return undefined;
    let alive = true;
    Promise.all([loadDictionary(), loadProfileValues()])
      .then(([dict, profile]) => {
        if (!alive) return;
        setDictionary(dict);
        setCurrent(profile);
        setValues(Object.fromEntries(card.fields.map((f) => [f.field_key, profile[f.field_key] ?? null])));
      })
      .catch((err) => alive && setError(err.message || "Unable to load these questions."));
    return () => {
      alive = false;
    };
  }, [active, card]);

  if (status === "saved") {
    return (
      <div className="mt-4 flex items-center gap-2 rounded-xl border border-emerald2-400/20 bg-emerald2-400/5 px-3.5 py-2.5 text-xs text-app-secondary animate-fadeIn">
        <CheckCircle2 size={14} className="flex-shrink-0 text-emerald2-400" />
        Saved to your profile — asking your question again.
      </div>
    );
  }
  if (!active) return null;

  const fields = dictionary ? card.fields.filter((f) => dictionary.definitions[f.field_key]) : [];
  const ready = fields.length > 0 && fields.every((f) => !isEmpty(values[f.field_key]));
  // Every role tag is a choice for the main target role here
  // (QuestionField otherwise offers only the roles already listed);
  // saving adds the chosen one to the list (see profileChanges).
  const answers = { ...current, ...values, target_role_families: Object.keys(dictionary?.roleTags || {}) };

  const submit = async () => {
    setStatus("saving");
    setError("");
    try {
      await updateProfile(profileChanges(values, current));
      setStatus("saved");
      onAnswered();
    } catch (err) {
      setStatus("idle");
      setError(err.message || "Unable to save. Please try again.");
    }
  };

  return (
    <div className="mt-4 rounded-xl border border-brand-400/20 bg-brand-500/5 p-4 animate-fadeIn">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-brand-500/15 text-brand-300">
          <ClipboardList size={13} />
        </div>
        <p className="text-sm font-medium text-app-primary">Answer here to continue</p>
      </div>

      {!dictionary && !error && (
        <div className="flex items-center gap-2 py-2 text-xs text-app-muted">
          <Loader2 size={13} className="animate-spin" /> Loading…
        </div>
      )}

      {dictionary && (
        <div className="space-y-4">
          {fields.map((field) => (
            <QuestionField
              key={field.field_key}
              definition={dictionary.definitions[field.field_key]}
              value={values[field.field_key]}
              onChange={(value) => setValues((prev) => ({ ...prev, [field.field_key]: value }))}
              answers={answers}
              roleTags={dictionary.roleTags}
              definitions={dictionary.definitions}
            />
          ))}
        </div>
      )}

      {error && <p className="mt-3 text-xs text-red-300">{error}</p>}

      <div className="mt-4 flex flex-col-reverse gap-2 border-t border-app-subtle pt-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <p className="text-[11px] text-app-faint">Saved to your profile — you can change it there any time.</p>
        <button type="button" onClick={submit} disabled={!ready || status === "saving"} className="btn-primary self-end flex-shrink-0 px-3.5 py-1.5 text-xs sm:self-auto">
          {status === "saving" && <Loader2 size={13} className="animate-spin" />}
          Save &amp; continue
        </button>
      </div>
    </div>
  );
}
