import { TrendingUp as TrendUp, TrendingDown as TrendDown } from "lucide-react";
import { cn } from "../utils/cn";

export function Card({ className, children, ...props }) {
  return (
    <div className={cn("card p-5", className)} {...props}>
      {children}
    </div>
  );
}

export function SectionTitle({ icon: Icon, title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div className="flex items-center gap-3">
        {Icon && (
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300">
            <Icon className="h-4.5 w-4.5" size={18} />
          </div>
        )}
        <div>
          <h2 className="font-display text-lg font-semibold text-app-primary">{title}</h2>
          {subtitle && <p className="text-sm text-app-muted">{subtitle}</p>}
        </div>
      </div>
      {action}
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
  return (
    <div className={cn("h-2 w-full rounded-full bg-app-hover overflow-hidden", className)}>
      <div
        className={cn("h-full rounded-full transition-all duration-500", colors[color])}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function StatCard({ label, value, delta, trend, icon: Icon }) {
  const trendColor = trend === "up" ? "text-emerald2-400" : "text-red-400";
  const TrendIcon = trend === "up" ? TrendUp : TrendDown;
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/15 text-brand-300">
          {Icon && <Icon size={20} />}
        </div>
        <div className={cn("flex items-center gap-1 text-xs font-medium", trendColor)}>
          <TrendIcon size={14} />
          {delta}
        </div>
      </div>
      <p className="mt-3 text-2xl font-display font-bold text-app-primary">{value}</p>
      <p className="text-sm text-app-muted">{label}</p>
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
