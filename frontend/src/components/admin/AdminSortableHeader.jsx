export default function AdminSortableHeader({ label, sortKey, sort, onSort }) {
  const active = sort?.key === sortKey;
  const title = label;
  return <button type="button" className="admin-sort-button" onClick={() => onSort(sortKey)} aria-label={`Sort by ${title}`}>{title} {active ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}</button>;
}
