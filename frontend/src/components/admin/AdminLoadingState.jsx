import { Loader2 } from "lucide-react";

export default function AdminLoadingState({ label = "Loading…" }) {
  return <main className="admin-loading-screen" role="status" aria-live="polite"><Loader2 className="admin-loading-spinner" size={24} /><strong>{label}</strong><span>Please wait while we load the latest information.</span></main>;
}
