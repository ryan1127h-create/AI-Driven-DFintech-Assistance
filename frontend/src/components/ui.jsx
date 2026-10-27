import { cn } from "../utils/cn";

export function Card({ className, children, ...props }) {
  return (
    <div className={cn("card p-5", className)} {...props}>
      {children}
    </div>
  );
}

export function Badge({ children, color = "ink", variant = "soft", className }) {
  const colors = {
    brand: "bg-brand-500/15 text-brand-300 border-brand-400/20",
    royal: "bg-royal-500/15 text-royal-300 border-royal-400/20",
    cyan2: "bg-cyan2-500/15 text-cyan2-400 border-cyan2-400/20",
    emerald2: "bg-emerald2-500/15 text-emerald2-400 border-emerald2-400/20",
    amber: "bg-amber-500/15 text-amber-300 border-amber-400/20",
    red: "bg-red-500/15 text-red-300 border-red-400/20",
    ink: "bg-app-hover text-app-secondary border-app-input",
  };
  return (
    <span
      className={cn(
        "chip border",
        colors[color],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ProgressBar({ value, max = 100, color = "brand", className }) {
  const pct = Math.min(100, (value / max) * 100);
  const colors = {
    brand: "bg-brand-500",
    royal: "bg-royal-500",
    cyan2: "bg-cyan2-500",
    emerald2: "bg-emerald2-500",
    amber: "bg-amber-500",
  };
  const adaptiveColor = pct <= 30
    ? "bg-gradient-to-r from-orange-500 to-red-500"
    : pct <= 70
      ? "bg-gradient-to-r from-amber-400 to-orange-500"
      : "bg-gradient-to-r from-emerald-400 to-cyan-400";
  return (
    <div className={cn("relative h-2 w-full overflow-hidden rounded-full bg-app-hover", className)}>
      <div
        className={cn("h-full rounded-full transition-all duration-700 ease-out", color === "adaptive" ? adaptiveColor : colors[color])}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function EmptyState({ icon: Icon, title, subtitle }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {Icon && (
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-app-hover text-app-muted mb-4">
          <Icon size={28} />
        </div>
      )}
      <h3 className="font-display text-base font-semibold text-app-primary">{title}</h3>
      {subtitle && <p className="text-sm text-app-muted mt-1 max-w-xs">{subtitle}</p>}
    </div>
  );
}

// An on/off control; `label` names it for screen readers.
export function Switch({ checked, onChange, disabled, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative h-5 w-9 flex-shrink-0 rounded-full transition",
        checked ? "bg-brand-500" : "border border-app-input bg-app-hover",
        disabled && "opacity-50",
      )}
    >
      <span className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all", checked ? "left-[18px]" : "left-0.5")} />
    </button>
  );
}

// One selectable option in a row of choices.
export function OptionChip({ active, onClick, disabled, children }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "rounded-lg border px-2.5 py-1 text-xs transition",
        active ? "border-brand-400/40 bg-brand-500/15 text-brand-300" : "border-app-subtle text-app-secondary hover:border-brand-400/30",
      )}
    >
      {children}
    </button>
  );
}
