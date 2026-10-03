import { useEffect, useRef, useState } from "react";
import { ChevronsUpDown, LogOut, Settings } from "lucide-react";
import { cn } from "../../utils/cn";

// The user's row at the bottom of the sidebar; opens a small menu with
// Settings and Log out. `compact` is the collapsed sidebar's avatar only.

function Avatar({ user, size = "h-8 w-8 text-xs" }) {
  return (
    <div className={cn("flex flex-shrink-0 items-center justify-center rounded-full bg-brand-500/20 font-medium text-brand-300", size)}>
      {user?.avatar}
    </div>
  );
}

export default function AccountMenu({ user, subtitle, onSettings, onLogout, compact }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const choose = (fn) => {
    setOpen(false);
    fn();
  };

  return (
    <div ref={ref} className="relative">
      {open && (
        <div
          role="menu"
          className={cn(
            "absolute bottom-full z-30 mb-2 min-w-[12rem] rounded-xl border border-app-subtle py-1.5 shadow-glass glass animate-fadeIn",
            compact ? "left-0" : "left-0 right-0",
          )}
        >
          <div className="border-b border-app-subtle px-3 pb-2 pt-1">
            <p className="truncate text-sm font-medium text-app-primary">{user?.name}</p>
            <p className="truncate text-[11px] text-app-muted">{user?.email}</p>
          </div>
          <button type="button" role="menuitem" onClick={() => choose(onSettings)}
            className="mt-1 flex w-full items-center gap-2.5 px-3 py-2 text-sm text-app-secondary transition hover:bg-app-hover hover:text-app-primary">
            <Settings size={14} /> Settings
          </button>
          <button type="button" role="menuitem" onClick={() => choose(onLogout)}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-app-secondary transition hover:bg-app-hover hover:text-red-400">
            <LogOut size={14} /> Log out
          </button>
        </div>
      )}

      {compact ? (
        <button type="button" onClick={() => setOpen(!open)} aria-label="Account menu" aria-expanded={open}
          className="rounded-full transition hover:ring-2 hover:ring-brand-400/30">
          <Avatar user={user} size="h-9 w-9 text-sm" />
        </button>
      ) : (
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
          className={cn("flex w-full items-center gap-2.5 rounded-lg p-2 text-left transition hover:bg-app-hover", open && "bg-app-hover")}>
          <Avatar user={user} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-app-primary">{user?.name}</p>
            <p className="truncate text-[10px] text-app-muted">{subtitle}</p>
          </div>
          <ChevronsUpDown size={14} className="flex-shrink-0 text-app-faint" />
        </button>
      )}
    </div>
  );
}
