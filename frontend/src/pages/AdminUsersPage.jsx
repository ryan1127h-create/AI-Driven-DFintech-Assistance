import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getAdminUsers } from "../../api";
import AdminSearchBar from "../components/admin/AdminSearchBar";
import AdminSortableHeader from "../components/admin/AdminSortableHeader";

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState({ key: "full_name", direction: "asc" });
  const navigate = useNavigate();

  useEffect(() => {
    // Debounced, and a response that arrives after a newer search started is
    // dropped, so a slow early request can't overwrite the latest results.
    let active = true;
    setLoading(true); setError("");
    const timer = setTimeout(() => {
      getAdminUsers(search.trim()).then((data) => { if (active) setUsers(roleFilter === "all" ? data.items : data.items.filter((user) => user.role === roleFilter)); }).catch((err) => { if (active) setError(err.message); }).finally(() => { if (active) setLoading(false); });
    }, 300);
    return () => { active = false; clearTimeout(timer); };
  }, [search, roleFilter]);

  const sortedUsers = useMemo(() => [...users].sort((left, right) => {
    const leftValue = String(left[sort.key] ?? "").toLowerCase();
    const rightValue = String(right[sort.key] ?? "").toLowerCase();
    return (leftValue > rightValue ? 1 : leftValue < rightValue ? -1 : 0) * (sort.direction === "asc" ? 1 : -1);
  }), [users, sort]);
  const toggleSort = (key) => setSort((current) => ({ key, direction: current.key === key && current.direction === "asc" ? "desc" : "asc" }));
  const header = (label, key) => <AdminSortableHeader label={label} sortKey={key} sort={sort} onSort={toggleSort} />;

  return <main className="admin-overview-page"><header className="admin-shared-page-header"><h1>Users</h1><p>Manage registered accounts and access status.</p></header><div className="admin-users-toolbar"><AdminSearchBar placeholder="Search users" value={search} onChange={setSearch} /><div className="admin-filter-tabs" role="tablist" aria-label="Filter users by role">{[["all", "All users"], ["user", "Users"], ["admin", "Admins"]].map(([value, label]) => <button type="button" role="tab" aria-selected={roleFilter === value} className={roleFilter === value ? "selected" : ""} onClick={() => setRoleFilter(value)} key={value}>{label}</button>)}</div></div>{error && <p role="alert">{error}</p>}<section className="admin-card admin-table-wrap"><table><thead><tr><th>{header("Name", "full_name")}</th><th>{header("Email", "email")}</th><th>{header("Role", "role")}</th><th>{header("Status", "account_status")}</th><th>{header("Last login", "last_login_at")}</th><th>Actions</th></tr></thead><tbody>{loading ? <tr><td colSpan="6">Loading users…</td></tr> : sortedUsers.map((user) => <tr key={user.user_id}><td>{user.full_name || "—"}</td><td>{user.email}</td><td><span className={`admin-role-badge ${user.role}`}>{user.role}</span></td><td>{user.account_status}</td><td>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Never"}</td><td><button type="button" className="admin-table-action" onClick={() => navigate(`/admin/users/${user.user_id}`)}>View details</button></td></tr>)}</tbody></table></section></main>;
}

