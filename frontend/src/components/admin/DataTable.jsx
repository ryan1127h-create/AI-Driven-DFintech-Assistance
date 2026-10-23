import { Search } from "lucide-react";

export function DataTable({ children, className = "", ...props }) {
  return <section className={`data-table ${className}`.trim()} {...props}>{children}</section>;
}

export function DataTableToolbar({ children, count, countLabel = "records", onReset, resetDisabled = false }) {
  return <div className="data-table-toolbar"><div className="data-table-toolbar-main">{children}</div><span className="data-table-results"><strong>{count}</strong> {countLabel}</span>{onReset && <button type="button" className="data-table-filter-reset" onClick={onReset} disabled={resetDisabled}>Reset</button>}</div>;
}

export function DataTableFilter({ children, label, ...props }) {
  return <label className="data-table-filter" {...props}>{label && <span>{label}</span>}{children}</label>;
}

export function DataTableSearch({ value, onChange, placeholder = "Search…" }) {
  return <label className="data-table-search"><Search size={15} aria-hidden="true" /><input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} aria-label={placeholder} /></label>;
}

export function DataTableEmptyState({ title = "No records found", description = "Data will appear here when available.", colSpan }) {
  const content = <div className="data-table-empty-state"><strong>{title}</strong><span>{description}</span></div>;
  return colSpan ? <tr><td colSpan={colSpan}>{content}</td></tr> : content;
}

export function DataTablePagination({ children, className = "" }) {
  return <div className={`data-table-pagination ${className}`.trim()}>{children}</div>;
}

