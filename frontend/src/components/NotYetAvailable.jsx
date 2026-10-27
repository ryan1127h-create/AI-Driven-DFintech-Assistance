import { Link } from "react-router-dom";
import { Users } from "lucide-react";
import { Card } from "./ui";

// Shown in place of Alumni Match to a user who can't use it yet (not
// enrolled): what it is, when it opens, and where to go meanwhile.
export default function NotYetAvailable() {
  return (
    <div className="mx-auto max-w-xl px-4 py-16">
      <Card className="text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-300">
          <Users size={22} aria-hidden="true" />
        </div>
        <h1 className="font-display text-xl font-semibold text-app-primary">Alumni Match opens once you&apos;re enrolled</h1>
        <p className="mt-2 text-sm text-app-secondary">
          Connecting with MSc DFT alumni is for current students. Until then, you can read alumni stories on the
          programme page or ask the assistant about career paths.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Link to="/programme#alumni" className="btn-outline">Read alumni stories</Link>
          <Link to="/app" className="btn-primary">Back to the assistant</Link>
        </div>
      </Card>
    </div>
  );
}
