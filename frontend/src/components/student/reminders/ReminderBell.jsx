import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, Bell, Clock, X } from "lucide-react";
import { cn } from "../../../utils/cn";
import useReminders, { reminderTarget } from "./useReminders";

// The bell in the student sidebar: how many reminders are open, and the list.
export default function ReminderBell({ compact = false }) {
  const { items, dismiss } = useReminders();
  const [open, setOpen] = useState(false);
  const [panelPosition, setPanelPosition] = useState({});
  const panel = useRef(null);
  const trigger = useRef(null);

  useEffect(() => {
    if (!open || !trigger.current) return undefined;
    const position = () => {
      const rect = trigger.current.getBoundingClientRect();
      const width = Math.min(320, window.innerWidth - 24);
      const left = Math.min(rect.right + 10, window.innerWidth - width - 12);
      setPanelPosition({ left: Math.max(12, left), top: compact ? rect.top : rect.bottom + 10, width });
    };
    position();
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => { window.removeEventListener("resize", position); window.removeEventListener("scroll", position, true); };
  }, [open, compact]);

  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => { if (panel.current && !panel.current.contains(event.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const urgent = items.some((r) => r.urgent);
  return (
    <div className="relative" ref={panel}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        ref={trigger}
        className="reminder-trigger relative flex h-9 w-9 items-center justify-center rounded-lg text-app-faint transition hover:bg-app-hover hover:text-app-primary"
        aria-label={items.length ? `Reminders, ${items.length} open` : "Reminders"}
        aria-expanded={open}
        title="Reminders"
      >
        <Bell size={18} />
        {items.length > 0 && (
          <span className={cn(
            "absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-semibold text-white",
            urgent ? "bg-red-500" : "bg-brand-500",
          )}>
            {items.length}
          </span>
        )}
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Reminders"
          className={cn(
            "reminder-panel absolute z-50 mt-2 w-80 max-w-[85vw] rounded-xl border border-app-subtle glass p-3 shadow-2xl",
            compact ? "reminder-panel-compact left-full top-0 ml-2 mt-0" : "reminder-panel-expanded right-0",
          )}
          style={panelPosition}
        >
          <p className="mb-2 px-1 text-xs font-semibold text-app-primary">Reminders</p>
          {items.length === 0 ? (
            <p className="px-1 py-3 text-xs text-app-muted">You&apos;re all caught up.</p>
          ) : (
            <ul className="space-y-2">
              {items.map((r) => <ReminderItem key={r.key} reminder={r} onDismiss={dismiss} onFollow={() => setOpen(false)} />)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export function ReminderItem({ reminder, onDismiss, onFollow }) {
  const Icon = reminder.urgent ? AlertCircle : Clock;
  const target = reminderTarget(reminder.action);
  return (
    <li className={cn(
      "rounded-lg border p-3 text-xs",
      reminder.urgent ? "border-red-400/30 bg-red-500/5" : "border-app-subtle bg-app-elevated",
    )}>
      <div className="flex items-start gap-2">
        <Icon size={14} className={cn("mt-0.5 flex-shrink-0", reminder.urgent ? "text-red-400" : "text-brand-300")} />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-app-primary">{reminder.title}</p>
          <p className="mt-0.5 text-app-muted">{reminder.body}</p>
          {target && (
            <Link to={target} onClick={onFollow} className="mt-1.5 inline-block font-medium text-brand-300 hover:underline">
              {reminder.action.label}
            </Link>
          )}
        </div>
        <button
          type="button"
          onClick={() => onDismiss(reminder.key)}
          className="flex-shrink-0 rounded p-0.5 text-app-faint hover:text-app-primary"
          aria-label={`Dismiss: ${reminder.title}`}
          title="Dismiss"
        >
          <X size={13} />
        </button>
      </div>
    </li>
  );
}
