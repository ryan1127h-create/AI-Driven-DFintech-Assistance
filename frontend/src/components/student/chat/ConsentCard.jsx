import { useState } from "react";
import { CheckCircle2, Loader2, ShieldCheck } from "lucide-react";
import { updateConsents } from "../../../../api";

// Asked when a reply needs the user's profile but the consent for that use
// is off (see backend ToolAnswer.card, kind "consent"): turning it on
// re-asks the user's question. Only the latest reply's card is live.
export default function ConsentCard({ card, active, onAnswered }) {
  const [status, setStatus] = useState("idle"); // idle | saving | done
  const [error, setError] = useState("");

  if (status === "done") {
    return (
      <div className="mt-4 flex items-center gap-2 rounded-xl border border-emerald2-400/20 bg-emerald2-400/5 px-3.5 py-2.5 text-xs text-app-secondary animate-fadeIn">
        <CheckCircle2 size={14} className="flex-shrink-0 text-emerald2-400" />
        Personalised recommendations are on — asking your question again.
      </div>
    );
  }
  if (!active) return null;

  const turnOn = async () => {
    setStatus("saving");
    setError("");
    try {
      await updateConsents({ [card.consent_key]: true });
      setStatus("done");
      onAnswered();
    } catch (err) {
      setStatus("idle");
      setError(err.message || "Unable to update this setting. Please try again.");
    }
  };

  return (
    <div className="mt-4 rounded-xl border border-brand-400/20 bg-brand-500/5 p-4 animate-fadeIn">
      <div className="flex items-start gap-2.5">
        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md bg-brand-500/15 text-brand-300">
          <ShieldCheck size={13} />
        </div>
        <div>
          <p className="text-sm font-medium text-app-primary">Turn on personalised recommendations</p>
          <p className="mt-0.5 text-xs text-app-muted">
            Lets the assistant use your profile — your goals, background and courses — to tailor its advice.
          </p>
        </div>
      </div>

      {error && <p className="mt-3 text-xs text-red-300">{error}</p>}

      <div className="mt-4 flex flex-col-reverse gap-2 border-t border-app-subtle pt-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <p className="text-[11px] text-app-faint">You can turn this off in Settings any time.</p>
        <button type="button" onClick={turnOn} disabled={status === "saving"} className="btn-primary self-end flex-shrink-0 px-3.5 py-1.5 text-xs sm:self-auto">
          {status === "saving" && <Loader2 size={13} className="animate-spin" />}
          Turn on &amp; continue
        </button>
      </div>
    </div>
  );
}
