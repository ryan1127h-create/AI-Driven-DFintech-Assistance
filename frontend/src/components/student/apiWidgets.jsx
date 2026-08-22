import { useState, useCallback } from "react";
import { Loader2, AlertCircle, CheckCircle, RefreshCw } from "lucide-react";
import { cn } from "../../utils/cn";

// Hook: wraps an async API call with loading/error state
export function useApiCall() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const call = useCallback(async (fn) => {
    setLoading(true);
    setError(null);

    try {
      const result = await fn();

      // null is allowed
      if (result === null) {
        return null;
      }

      if (result?.ok === false) {
        const msg =
          result.body?.detail ||
          result.body?.error ||
          `Request failed (${result.status})`;

        setError(msg);
      }

      return result;
    } catch (err) {
      setError(err.message || "Network error");

      return {
        ok: false,
        status: 0,
        body: {
          error: err.message,
        },
      };
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, setError, call };
}

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

export function FormField({ label, children, hint, required }) {
  return (
    <div>
      <label className="text-sm font-medium text-app-secondary flex items-center gap-1 mb-1.5">
        {required && <span className="text-red-400">*</span>}
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-app-faint mt-1">{hint}</p>}
    </div>
  );
}

export function TextInput(props) {
  return <input {...props} className={cn("input", props.className)} />;
}

export function TextArea(props) {
  return <textarea {...props} className={cn("input resize-none", props.className)} />;
}

export function Select({ options, placeholder, ...props }) {
  return (
    <select {...props} className={cn("input", props.className)}>
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((o) => {
        const val = typeof o === "string" ? o : o.value;
        const label = typeof o === "string" ? o : o.label;
        return <option key={val} value={val}>{label}</option>;
      })}
    </select>
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

export function ApiBadge({ ok, label }) {
  return (
    <span className={cn(
      "chip text-[10px] font-medium px-2 py-0.5 rounded",
      ok ? "bg-emerald2-500/10 text-emerald2-400" : "bg-red-500/10 text-red-400",
    )}>
      {label}
    </span>
  );
}
