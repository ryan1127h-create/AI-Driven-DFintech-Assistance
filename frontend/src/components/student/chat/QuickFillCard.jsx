import { useEffect, useState } from "react";
import { CheckCircle2, ClipboardList, Lightbulb, Loader2, RefreshCw, SkipForward, Sparkles, X } from "lucide-react";
import { updateProfile } from "../../../../api";
import { cn } from "../../../utils/cn";
import QuestionField from "../onboarding/QuestionField";
import { ROLE_TAGS_REF } from "../profile/ProfileFields";
import { loadDictionary, loadProfileValues, profileChanges } from "./profileWrites";

const isEmpty = (value) => value === null || value === undefined || (Array.isArray(value) && !value.length);

// How each level of card reads (see backend MissingInputField levels):
// required — the reply waits for it; optional — it waits, but can be
// skipped; supplementary — offered under an answer, never in the way.
const LEVELS = {
  required: {
    icon: ClipboardList,
    title: "Answer here to continue",
    action: "Save & continue",
  },
  optional: {
    icon: Sparkles,
    title: "Tailor this to you",
    action: "Save & continue",
  },
  supplementary: {
    icon: Lightbulb,
    title: "Tailor this further (optional)",
    action: "Save",
  },
};

// The profile fields a reply asked for (see backend ToolAnswer.card and
// .supplement_card), answered in place and saved to the profile.
// - required / optional: saving re-asks the user's question; skipping (an
//   optional card only) re-asks it without the fields, declined for the
//   rest of the conversation.
// - supplementary: saving offers to update the answer; dismissing declines
//   the fields for the rest of the conversation.
// Only the latest reply's card can be answered; once the conversation has
// moved on, a card that wasn't used disappears.
export default function QuickFillCard({ card, active, onAnswered, onSkip, onDismiss }) {
  const level = LEVELS[card.level] ? card.level : "required";
  const look = LEVELS[level];
  const fieldKeys = card.fields.map((f) => f.field_key);
  const [dictionary, setDictionary] = useState(null);
  const [current, setCurrent] = useState({});
  const [values, setValues] = useState({});
  const [status, setStatus] = useState("idle"); // idle | saving | saved | skipped | dismissed
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

  if (status === "dismissed") return null;
  if (status === "skipped") {
    return (
      <p className="mt-4 flex items-center gap-1.5 text-xs text-app-muted animate-fadeIn">
        <SkipForward size={13} /> Skipped — answering without it.
      </p>
    );
  }
  if (status === "saved") {
    return (
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald2-400/20 bg-emerald2-400/5 px-3.5 py-2.5 text-xs text-app-secondary animate-fadeIn">
        <span className="flex items-center gap-2">
          <CheckCircle2 size={14} className="flex-shrink-0 text-emerald2-400" />
          {level === "supplementary" ? "Saved to your profile." : "Saved to your profile — asking your question again."}
        </span>
        {level === "supplementary" && active && (
          <button type="button" onClick={onAnswered} className="inline-flex items-center gap-1 font-medium text-brand-300 hover:underline">
            <RefreshCw size={12} /> Update this answer
          </button>
        )}
      </div>
    );
  }
  if (!active) return null;

  const fields = dictionary ? card.fields.filter((f) => dictionary.definitions[f.field_key]) : [];
  const answered = fields.filter((f) => !isEmpty(values[f.field_key]));
  // A blocking card needs every field; supplementary details are each
  // optional, so any one answered can be saved.
  const ready = level === "supplementary" ? answered.length > 0 : fields.length > 0 && answered.length === fields.length;
  // Every role tag is a choice for the main target role here
  // (QuestionField otherwise offers only the roles already listed);
  // saving adds the chosen one to the list (see profileChanges).
  const answers = { ...current, ...values, target_role_families: Object.keys(dictionary?.refOptions?.[ROLE_TAGS_REF] || {}) };
  const Icon = look.icon;
  const subtle = level === "supplementary";

  const submit = async () => {
    setStatus("saving");
    setError("");
    try {
      // Only what was answered: an unanswered field must not be written as
      // a deletion.
      const answeredValues = Object.fromEntries(answered.map((f) => [f.field_key, values[f.field_key]]));
      await updateProfile(profileChanges(answeredValues, current));
      setStatus("saved");
      if (!subtle) onAnswered();
    } catch (err) {
      setStatus("idle");
      setError(err.message || "Unable to save. Please try again.");
    }
  };
  const skip = () => {
    setStatus("skipped");
    onSkip(fieldKeys);
  };
  const dismiss = () => {
    setStatus("dismissed");
    onDismiss(fieldKeys);
  };

  return (
    <div
      className={cn(
        "mt-4 rounded-xl p-4 animate-fadeIn",
        subtle ? "glass-light" : "border border-brand-400/20 bg-brand-500/5",
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md bg-brand-500/15 text-brand-300">
            <Icon size={13} />
          </div>
          <div>
            <p className="text-sm font-medium text-app-primary">{look.title}</p>
            {subtle && card.reason && <p className="text-xs text-app-muted">{card.reason}</p>}
          </div>
        </div>
        {subtle && (
          <button
            type="button"
            onClick={dismiss}
            title="Not now"
            className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md text-app-faint transition hover:bg-app-hover hover:text-app-primary"
          >
            <X size={13} />
          </button>
        )}
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
              refOptions={dictionary.refOptions}
              definitions={dictionary.definitions}
            />
          ))}
        </div>
      )}

      {error && <p className="mt-3 text-xs text-red-300">{error}</p>}

      <div className="mt-4 flex flex-col-reverse gap-2 border-t border-app-subtle pt-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <p className="text-[11px] text-app-faint">Saved to your profile — you can change it there any time.</p>
        <div className="flex flex-shrink-0 items-center gap-2 self-end sm:self-auto">
          {card.skippable && (
            <button type="button" onClick={skip} disabled={status === "saving"} className="btn-outline px-3.5 py-1.5 text-xs">
              Skip
            </button>
          )}
          <button type="button" onClick={submit} disabled={!ready || status === "saving"} className="btn-primary px-3.5 py-1.5 text-xs">
            {status === "saving" && <Loader2 size={13} className="animate-spin" />}
            {look.action}
          </button>
        </div>
      </div>
    </div>
  );
}
