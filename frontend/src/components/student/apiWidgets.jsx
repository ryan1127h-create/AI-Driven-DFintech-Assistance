import { Loader2, AlertCircle, CheckCircle, RefreshCw } from "lucide-react";
import { cn } from "../../utils/cn";

export function LoadingSpinner({ label = "Loading..." }) {
  return (
    <div className="flex items-center justify-center py-12 text-app-muted">
      <Loader2 size={20} className="animate-spin mr-2" />
      {label}
    </div>
  );
}

export function ErrorBanner({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="flex items-center gap-2 rounded-lg p-3 bg-red-500/10 border border-red-400/20 text-sm text-red-400 mb-4">
      <AlertCircle size={16} className="flex-shrink-0" />
      <span className="flex-1">{error}</span>
      {onRetry && (
        <button onClick={onRetry} className="text-red-400 hover:text-red-300">
          <RefreshCw size={14} />
        </button>
      )}
    </div>
  );
}

export function SuccessBanner({ children }) {
  return (
    <div className="flex items-center gap-2 rounded-lg p-3 bg-emerald2-500/10 border border-emerald2-400/20 text-sm text-emerald2-400 mb-4">
      <CheckCircle size={16} className="flex-shrink-0" />
      {children}
    </div>
  );
}

export function PageHeader({ icon: Icon, title, subtitle }) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-3 mb-2">
        {Icon && (
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/15 text-brand-300">
            <Icon size={20} />
          </div>
        )}
        <div>
          <h1 className="font-display text-xl font-bold text-app-primary">{title}</h1>
          {subtitle && <p className="text-sm text-app-muted mt-0.5">{subtitle}</p>}
        </div>
      </div>
    </div>
  );
}

export function SubmitButton({ loading, children, disabled, ...props }) {
  return (
    <button
      {...props}
      disabled={loading || disabled}
      className={cn("btn-primary", props.className)}
    >
      {loading ? <><Loader2 size={16} className="animate-spin" /> Loading...</> : children}
    </button>
  );
}
