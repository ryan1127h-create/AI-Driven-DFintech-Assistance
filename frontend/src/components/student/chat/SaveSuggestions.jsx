import { useEffect, useState } from "react";
import { BookmarkPlus, Check, Loader2, X } from "lucide-react";
import { updateProfile } from "../../../../api";
import { cn } from "../../../utils/cn";
import { loadDictionary, loadProfileValues, profileChanges } from "./profileWrites";

// Facts the user stated in this turn that differ from their profile (see
// backend ToolAnswer.save_suggestions), offered for saving one at a time.
// Nothing is written until the user confirms.
export default function SaveSuggestions({ suggestions }) {
  const [state, setState] = useState({}); // field_key -> "saving" | "saved" | error message
  const [dismissed, setDismissed] = useState(false);
  const [labels, setLabels] = useState({});

  // Field names come from the dictionary; until it loads, the key stands in.
  useEffect(() => {
    let alive = true;
    loadDictionary()
      .then(({ definitions }) => alive && setLabels(
        Object.fromEntries(suggestions.map((s) => [s.field_key, definitions[s.field_key]?.label])),
      ))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [suggestions]);

  if (dismissed) return null;
  if (suggestions.every((s) => state[s.field_key] === "saved")) {
    return (
      <div className="mt-3 flex items-center gap-1.5 text-xs text-emerald2-400 animate-fadeIn">
        <Check size={13} /> Saved to your profile
      </div>
    );
  }

  const save = async (suggestion) => {
    setState((prev) => ({ ...prev, [suggestion.field_key]: "saving" }));
    try {
      const current = await loadProfileValues();
      await updateProfile(profileChanges({ [suggestion.field_key]: suggestion.value }, current));
      setState((prev) => ({ ...prev, [suggestion.field_key]: "saved" }));
    } catch (err) {
      setState((prev) => ({ ...prev, [suggestion.field_key]: err.message || "Unable to save." }));
    }
  };

  return (
    <div className="mt-4 rounded-xl glass-light px-3.5 py-3 animate-fadeIn">
      <div className="mb-2 flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-xs font-medium text-app-secondary">
          <BookmarkPlus size={13} className="text-brand-300" />
          Save to your profile?
        </p>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          title="Not now"
          className="flex h-5 w-5 items-center justify-center rounded-md text-app-faint transition hover:bg-app-hover hover:text-app-primary"
        >
          <X size={12} />
        </button>
      </div>
      <ul className="space-y-1.5">
        {suggestions.map((suggestion) => {
          const status = state[suggestion.field_key];
          const failed = status && status !== "saving" && status !== "saved";
          return (
            <li key={suggestion.field_key} className="flex items-center justify-between gap-3 text-sm">
              <span className="min-w-0 break-words">
                <span className="text-app-muted">{labels[suggestion.field_key] || suggestion.field_key}: </span>
                <span className="font-medium text-app-primary">{suggestion.label}</span>
                {failed && <span className="ml-2 text-xs text-red-300">{status}</span>}
              </span>
              <button
                type="button"
                onClick={() => save(suggestion)}
                disabled={status === "saving" || status === "saved"}
                className={cn(
                  "inline-flex flex-shrink-0 items-center gap-1 rounded-lg border px-2.5 py-1 text-xs transition",
                  status === "saved"
                    ? "border-emerald2-400/30 text-emerald2-400"
                    : "border-brand-400/30 text-brand-300 hover:bg-brand-500/10",
                )}
              >
                {status === "saving" && <Loader2 size={12} className="animate-spin" />}
                {status === "saved" ? <><Check size={12} /> Saved</> : "Save"}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
