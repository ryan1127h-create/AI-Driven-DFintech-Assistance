import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getAdminUsers } from "../../api";
import AdminSearchBar from "../components/admin/AdminSearchBar";
import AdminSortableHeader from "../components/admin/AdminSortableHeader";
import { STAGE_LABELS } from "../data/stages";

// Where each user is in the programme lifecycle, e.g. "Applicant · Documents
// required"; staff are shown as such.
const STAGE_FILTERS = [["prospect", "Prospective students"], ["applicant", "Applicants"], ["admitted", "Admitted"],
  ["current", "Current students"], ["graduating", "Graduating"], ["alumni", "Alumni"], ["staff", "Staff"]];
const SUB_STAGE_LABELS = {
  browsing: "Browsing", comparing: "Comparing", decided_to_apply: "Decided to apply", DRAFT: "Draft",
  SUBMITTED: "Submitted", UNDER_REVIEW: "Under review", DOCS_REQUIRED: "Documents required", WAITLIST: "Waitlisted",
  REJECTED: "Rejected", OFFER: "Offer", ACCEPTED: "Accepted", sem1: "Semester 1", sem2: "Semester 2", "sem3+": "Semester 3+",
};

function stageText(user) {
  if (user.role === "admin") return "Staff";
  const stage = STAGE_LABELS[user.lifecycle_stage] || "—";
  const sub = SUB_STAGE_LABELS[user.sub_stage];
  return sub ? `${stage} · ${sub}` : stage;
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all"); const [stageFilter, setStageFilter] = useState(""); const [statusFilter, setStatusFilter] = useState("all"); const [page, setPage] = useState(1); const pageSize = 10;
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
      getAdminUsers(search.trim(), stageFilter).then((data) => { if (active) setUsers(roleFilter === "all" ? data.items : data.items.filter((user) => user.role === roleFilter)); }).catch((err) => { if (active) setError(err.message); }).finally(() => { if (active) setLoading(false); });
    }, 300);
    return () => { active = false; clearTimeout(timer); };
    // setLoading(true); getAdminUsers(search).then((data) => setUsers(data.items)).catch((err) => setError(err.message)).finally(() => setLoading(false));
  }, [search, roleFilter, stageFilter]);

  const sortedUsers = useMemo(() => users.filter((user) => (roleFilter === "all" || user.role === roleFilter) && (statusFilter === "all" || user.account_status === statusFilter)).sort((left, right) => {
    const leftValue = String(left[sort.key] ?? "").toLowerCase();
    const rightValue = String(right[sort.key] ?? "").toLowerCase();
    return (leftValue > rightValue ? 1 : leftValue < rightValue ? -1 : 0) * (sort.direction === "asc" ? 1 : -1);
  }), [users, sort, roleFilter, statusFilter]);
  const pageCount = Math.max(1, Math.ceil(sortedUsers.length / pageSize)); const paginatedUsers = sortedUsers.slice((page - 1) * pageSize, page * pageSize);
  const toggleSort = (key) => setSort((current) => ({ key, direction: current.key === key && current.direction === "asc" ? "desc" : "asc" }));
  const header = (label, key) => <AdminSortableHeader label={label} sortKey={key} sort={sort} onSort={toggleSort} />;

  return <main className="admin-overview-page"><header className="admin-shared-page-header"><h1>Users</h1><p>Manage registered accounts and access status.</p></header><section className="data-table admin-users-table-card"><div className="data-table-toolbar admin-users-toolbar"><AdminSearchBar placeholder="Search users" value={search} onChange={(value) => { setSearch(value); setPage(1); }} /><span className="data-table-results"><strong>{sortedUsers.length}</strong> visible users</span></div><div className="data-table-filters admin-users-filter-row"><span className="admin-filter-mark">☷</span><select aria-label="Filter users by role" value={roleFilter} onChange={(event) => { setRoleFilter(event.target.value); setPage(1); }}><option value="all">All roles</option><option value="user">Users</option><option value="admin">Admins</option></select><select aria-label="Filter users by stage" value={stageFilter} onChange={(event) => { setStageFilter(event.target.value); setPage(1); }}><option value="">All stages</option>{STAGE_FILTERS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><select aria-label="Filter users by status" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }}><option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option><option value="suspended">Suspended</option></select><button type="button" className="data-table-filter-reset" onClick={() => { setSearch(""); setRoleFilter("all"); setStageFilter(""); setStatusFilter("all"); setPage(1); }}>Reset</button></div>{error && <p role="alert">{error}</p>}<div className="admin-table-wrap"><table><thead><tr><th>{header("NAME", "full_name")}</th><th>{header("EMAIL", "email")}</th><th>{header("ROLE", "role")}</th><th>{header("STAGE", "lifecycle_stage")}</th><th>COURSES</th><th>{header("STATUS", "account_status")}</th><th>{header("LAST LOGIN", "last_login_at")}</th><th>ACTIONS</th></tr></thead><tbody>{loading ? <tr><td colSpan="8">Loading users…</td></tr> : paginatedUsers.map((user) => <tr key={user.user_id}><td>{user.role === "user" ? <Link className="admin-related-link" to={`/admin/users/${user.user_id}`}>{user.full_name || "Unnamed user"}</Link> : user.full_name || "—"}</td><td>{user.email}</td><td>{user.role === "user" ? <Link className={`role-badge ${user.role}`} to={`/admin/users/${user.user_id}`}>{user.role}</Link> : <span className={`role-badge ${user.role}`}>{user.role}</span>}</td><td className="admin-user-stage">{stageText(user)}</td><td>{(user.course_enrollments || []).map((enrollment) => enrollment.course_code).filter(Boolean).join(", ") || "—"}</td><td><span className={`status-badge ${user.account_status}`}>{user.account_status}</span></td><td>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Never"}</td><td><button type="button" className="table-action" onClick={() => navigate(`/admin/users/${user.user_id}`)}>View details</button></td></tr>)}</tbody></table>{!loading && !paginatedUsers.length && <div className="data-table-empty-state"><strong>No users match the selected filters.</strong><span>Try adjusting the search or filters.</span></div>}</div><div className="data-table-pagination admin-application-pagination"><span>Showing <strong>{sortedUsers.length ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, sortedUsers.length)}</strong> of <strong>{sortedUsers.length}</strong> users</span><div className="admin-application-page-buttons"><button type="button" disabled={page === 1} onClick={() => setPage((value) => value - 1)}>‹ Previous</button>{Array.from({ length: pageCount }, (_, index) => index + 1).slice(0, 7).map((number) => <button type="button" className={number === page ? "active" : ""} key={number} onClick={() => setPage(number)}>{number}</button>)}<button type="button" disabled={page === pageCount} onClick={() => setPage((value) => value + 1)}>Next ›</button></div></div></section></main>;
}

