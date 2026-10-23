import { Link } from "react-router-dom";
import { Check, UserPlus, Users } from "lucide-react";

// Under an alumni-match reply (backend tools/specialist/alumni_match_tool.py):
// one link per alumnus the reply names, opening their profile on Alumni
// Match, where the request is sent. The reply text already describes them.

const REQUEST_LABELS = { pending: "Request sent", accepted: "Connected" };

// The whole name: the first word isn't reliably the given name (Chen Yuxin).
function displayName(name) {
  return (name || "").trim();
}

export default function AlumniMatchesCard({ card }) {
  return (
    <div className="mt-4 rounded-xl border border-brand-400/20 bg-brand-500/5 p-4 animate-fadeIn">
      <p className="flex items-center gap-1.5 text-xs font-medium text-app-primary">
        <Users size={13} /> Open in Alumni Match
      </p>
      <div className="mt-2.5 flex flex-wrap gap-2">
        {card.items.map((person) => {
          const status = REQUEST_LABELS[person.request_status];
          return (
            <Link
              key={person.id}
              to={`/alumni-match?alumnus=${encodeURIComponent(person.id)}`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-app-subtle bg-app-elevated px-3 py-1.5 text-xs text-app-primary transition hover:border-brand-400/40"
            >
              {status ? <Check size={12} className="text-emerald2-400" /> : <UserPlus size={12} className="text-brand-300" />}
              {status ? `${displayName(person.name)} · ${status}` : `View ${displayName(person.name)}`}
            </Link>
          );
        })}
      </div>
      {!card.can_send_requests && (
        <p className="mt-2.5 text-xs text-app-muted">
          Turn on Alumni matching under Settings → Privacy to send a request.
        </p>
      )}
    </div>
  );
}
