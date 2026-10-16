export default function AdminSortableHeader({ label, sortKey, sort, onSort }) {
  const active = sort?.key === sortKey;
  return <button type="button" className="admin-sort-button" onClick={() => onSort(sortKey)} aria-label={`Sort by ${label}`}>{label} {active ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}</button>;
}
