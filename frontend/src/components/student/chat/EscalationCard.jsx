import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, LifeBuoy, Loader2, UserRound } from "lucide-react";
import { acceptEscalationOffer } from "../../../../api";

// Under a reply that needs a person (see backend turn_service.ChatTurnResult
// .escalation): "opened" — the conversation was passed to the programme
// office, with support contacts for a sensitive one; "offer" — the user may
// choose to pass it on. Only the latest reply's offer can be taken up.

const OFFER_TEXT = {
  policy_exception: "Exceptions like this are decided by the programme office. Want me to pass your request to a staff member?",
  low_confidence: "I couldn't give you a reliable answer here. Want a staff member from the programme office to follow up?",
};

export default function EscalationCard({ escalation, sessionId, active }) {
  const [card, setCard] = useState(escalation);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  if (card.kind === "opened") {
    const { case: escalatedCase, resources } = card;
    return (
      <div className="mt-4 rounded-xl border border-emerald2-400/20 bg-emerald2-400/5 p-4 animate-fadeIn">
        <div className="flex items-start gap-2.5">
          <CheckCircle2 size={15} className="mt-0.5 flex-shrink-0 text-emerald2-400" />
          <div className="text-sm">
            <p className="font-medium text-app-primary">
              {escalatedCase.created ? "Passed to the programme office" : "Already with the programme office"}
              <span className="ml-1.5 text-xs font-normal text-app-muted">Case #{escalatedCase.short_id}</span>
            </p>
            <p className="mt-0.5 text-xs text-app-muted">
              A staff member will follow up by email.{" "}
              <Link to="/workspace/support" className="text-brand-300 hover:underline">See your requests</Link>
            </p>
          </div>
        </div>
        {resources?.length > 0 && (
          <div className="mt-3 border-t border-app-subtle pt-3">
            <p className="flex items-center gap-1.5 text-xs font-medium text-app-primary"><LifeBuoy size={13} /> If you need support right now</p>
            <ul className="mt-1.5 space-y-1 text-xs text-app-secondary">
              {resources.map((r) => <li key={r.label}><strong className="font-medium">{r.label}</strong> — {r.detail}</li>)}
            </ul>
          </div>
        )}
      </div>
    );
  }

  if (!active) return null;
  const accept = async () => {
    setSaving(true);
    setError("");
    try {
      setCard(await acceptEscalationOffer(sessionId));
    } catch (err) {
      setError(err.message || "Unable to pass this to staff. Please try again.");
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="mt-4 rounded-xl border border-brand-400/20 bg-brand-500/5 p-4 animate-fadeIn">
      <div className="flex items-start gap-2.5">
        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md bg-brand-500/15 text-brand-300"><UserRound size={13} /></div>
        <p className="text-sm text-app-primary">{OFFER_TEXT[card.category] || "Want a staff member from the programme office to follow up?"}</p>
      </div>
      {error && <p className="mt-3 text-xs text-red-300">{error}</p>}
      <div className="mt-3 flex justify-end border-t border-app-subtle pt-3">
        <button type="button" onClick={accept} disabled={saving} className="btn-primary px-3.5 py-1.5 text-xs">
          {saving && <Loader2 size={13} className="animate-spin" />}
          Pass to a staff member
        </button>
      </div>
    </div>
  );
}
