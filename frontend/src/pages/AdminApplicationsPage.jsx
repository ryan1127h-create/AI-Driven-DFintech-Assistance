import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getAdminApplications } from "../../api";
import AdminLoadingState from "../components/admin/AdminLoadingState";
import AdminSearchBar from "../components/admin/AdminSearchBar";
import AdminSortableHeader from "../components/admin/AdminSortableHeader";

export default function AdminApplicationsPage() {
  const [items, setItems] = useState(null); const [search, setSearch] = useState(""); const [statusFilter, setStatusFilter] = useState("all"); const [error, setError] = useState(""); const navigate = useNavigate();
  const [sort, setSort] = useState({ key: "application_no", direction: "asc" });
  useEffect(() => { getAdminApplications().then((data) => setItems(data.items)).catch((err) => setError(err.message)); }, []);
  const statuses = useMemo(() => [...new Set((items || []).map((item) => item.status).filter(Boolean))].sort(), [items]);
  const sortedItems = useMemo(() => [...(items || [])].filter((item) => { const query = search.trim().toLowerCase(); const searchable = `${item.application_no || ""} ${item.application_id || ""} ${item.user_name || ""} ${item.applicant_email || ""} ${item.admission_term || ""}`.toLowerCase(); return (statusFilter === "all" || item.status === statusFilter) && (!query || searchable.includes(query)); }).sort((left, right) => { const leftValue = String(left[sort.key] ?? "").toLowerCase(); const rightValue = String(right[sort.key] ?? "").toLowerCase(); return (leftValue > rightValue ? 1 : leftValue < rightValue ? -1 : 0) * (sort.direction === "asc" ? 1 : -1); }), [items, search, sort, statusFilter]);
  const toggleSort = (key) => setSort((current) => ({ key, direction: current.key === key && current.direction === "asc" ? "desc" : "asc" }));
  const header = (label, key) => <AdminSortableHeader label={label} sortKey={key} sort={sort} onSort={toggleSort} />;
  if (error) return <main className="admin-overview-page"><p role="alert">{error}</p></main>;
  if (!items) return <AdminLoadingState label="Loading applications…" />;
  return <main className="admin-overview-page"><header className="admin-shared-page-header"><h1>Applications</h1><p>Review applications and checklist completion.</p></header><section className="admin-card admin-conversation-filter"><AdminSearchBar placeholder="Search applications" value={search} onChange={setSearch} /><label htmlFor="application-status-filter">Status</label><select id="application-status-filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option>{statuses.map((status) => <option value={status} key={status}>{status}</option>)}</select></section><section className="admin-card admin-table-wrap"><table><thead><tr><th>{header("Application", "application_no")}</th><th>{header("Applicant", "user_name")}</th><th>{header("Term", "admission_term")}</th><th>{header("Status", "status")}</th><th>{header("Checklist", "checklist_submitted")}</th><th>Actions</th></tr></thead><tbody>{sortedItems.map((item) => <tr key={item.application_id}><td>{item.application_no || item.application_id}</td><td>{item.user_id ? <Link className="admin-related-link" to={`/admin/users/${item.user_id}`}>{item.user_name || "View profile"}</Link> : item.applicant_email || "—"}</td><td>{item.admission_term || "—"}</td><td>{item.status || "—"}</td><td>{item.checklist_submitted}/{item.checklist_total}</td><td><button className="admin-table-action" type="button" onClick={() => navigate(`/admin/applications/${item.application_id}`)}>View details</button></td></tr>)}</tbody></table></section></main>;
}
