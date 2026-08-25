import { useState } from "react";
import {
  Users, Search,
  ArrowLeft,
} from "lucide-react";
import {
  studentsList,
} from "../../../data/mock";
import { Card, Badge, ProgressBar, EmptyState } from "../../ui";
import { PageHeader, InfoRow, StatusBadge } from "../../student/PageParts";

// ============ STUDENT MANAGEMENT WITH COMPREHENSIVE DETAILS ============

export function StudentsPage() {
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [sortBy, setSortBy] = useState("name");
  const [selectedStudent, setSelectedStudent] = useState(null);

  const filtered = studentsList
    .filter((s) => {
      const matchSearch = !search || s.name.toLowerCase().includes(search.toLowerCase()) || s.studentId.toLowerCase().includes(search.toLowerCase()) || s.email.toLowerCase().includes(search.toLowerCase());
      const matchRole = roleFilter === "all" || s.role === roleFilter;
      return matchSearch && matchRole;
    })
    .sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "progress") return b.progress - a.progress;
      if (sortBy === "lastLogin") return 0;
      return 0;
    });

  if (selectedStudent) {
    const s = studentsList.find((st) => st.id === selectedStudent.id) || selectedStudent;
    return (
      <div>
        <button onClick={() => setSelectedStudent(null)} className="btn-ghost mb-4 text-xs">
          <ArrowLeft size={14} /> Back to Students
        </button>
        <Card className="mb-4">
          <div className="flex items-center gap-4 mb-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand-500/15 text-brand-300 font-medium text-lg">
              {s.name.split(" ").map((n) => n[0]).join("")}
            </div>
            <div className="flex-1">
              <h2 className="font-display text-lg font-bold text-app-primary">{s.name}</h2>
              <p className="text-sm text-app-muted">{s.role} · {s.stage}</p>
            </div>
            <StatusBadge status={s.status} />
          </div>
        </Card>

        <div className="grid lg:grid-cols-2 gap-4">
          <Card>
            <h3 className="font-display text-base font-semibold text-app-primary mb-3">Basic Information</h3>
            <InfoRow label="Student Name" value={s.name} />
            <InfoRow label="Student ID" value={s.studentId} />
            <InfoRow label="Email" value={s.email} />
            <InfoRow label="Contact Number" value={s.contact} />
            <InfoRow label="Country" value={s.country} />
          </Card>
          <Card>
            <h3 className="font-display text-base font-semibold text-app-primary mb-3">Programme Information</h3>
            <InfoRow label="Role" value={s.role} />
            <InfoRow label="Lifecycle Stage" value={s.stage} />
            <InfoRow label="Programme" value={s.programme} />
            <InfoRow label="Intake" value={s.intake} />
          </Card>
          <Card>
            <h3 className="font-display text-base font-semibold text-app-primary mb-3">Academic Information</h3>
            <InfoRow label="Status" value={s.status} />
            <InfoRow label="Credits Completed" value={`${s.creditsCompleted} / ${s.creditsTotal}`} />
            <div className="py-2.5 border-b border-app-soft">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-app-muted">Graduation Progress</span>
                <span className="text-sm font-medium text-app-primary">{s.progress}%</span>
              </div>
              <ProgressBar value={s.progress} color="brand" />
            </div>
            {s.cap && <InfoRow label="CAP" value={`${s.cap} / 5.0`} />}
          </Card>
          <Card>
            <h3 className="font-display text-base font-semibold text-app-primary mb-3">Activity Information</h3>
            <InfoRow label="Last Login" value={s.lastLogin} />
            <InfoRow label="Chat Sessions" value={String(s.chatSessions)} />
            <InfoRow label="Escalations Generated" value={String(s.escalationsGenerated)} />
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader icon={Users} title="Students" subtitle="All users across the lifecycle" />

      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-[200px]">
            <Search size={16} className="text-app-faint" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by name, ID, or email..." className="flex-1 bg-transparent text-sm text-app-primary placeholder:text-app-faint focus:outline-none" />
          </div>
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className="input text-xs w-auto">
            <option value="all">All Roles</option>
            <option value="Prospective">Prospective</option>
            <option value="Applicant">Applicant</option>
            <option value="Admitted">Admitted</option>
            <option value="Enrolled">Enrolled</option>
            <option value="Graduating">Graduating</option>
            <option value="Alumni">Alumni</option>
          </select>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="input text-xs w-auto">
            <option value="name">Sort: Name</option>
            <option value="progress">Sort: Progress</option>
            <option value="lastLogin">Sort: Last Login</option>
          </select>
        </div>
      </Card>

      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-app-subtle">
              <th className="text-left py-3 px-3 text-app-muted font-medium">Student</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Student ID</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Role</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Programme</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Progress</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Chats</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Escalations</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Last Login</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <tr key={s.id} className="border-b border-app-soft hover:bg-app-hover transition cursor-pointer" onClick={() => setSelectedStudent(s)}>
                <td className="py-3 px-3">
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-500/15 text-brand-300 text-xs font-medium">
                      {s.name.split(" ").map((n) => n[0]).join("")}
                    </div>
                    <div>
                      <p className="text-app-primary">{s.name}</p>
                      <p className="text-[10px] text-app-faint">{s.email}</p>
                    </div>
                  </div>
                </td>
                <td className="py-3 px-3 font-mono text-xs text-brand-300">{s.studentId}</td>
                <td className="py-3 px-3 text-app-secondary text-xs">{s.role}</td>
                <td className="py-3 px-3 text-app-secondary text-xs">{s.programme}<p className="text-[10px] text-app-faint">{s.intake}</p></td>
                <td className="py-3 px-3 w-28"><ProgressBar value={s.progress} color="brand" /></td>
                <td className="py-3 px-3 text-app-secondary text-xs">{s.chatSessions}</td>
                <td className="py-3 px-3 text-xs">{s.escalationsGenerated > 0 ? <Badge color="amber">{s.escalationsGenerated}</Badge> : <span className="text-app-faint">0</span>}</td>
                <td className="py-3 px-3 text-xs text-app-faint">{s.lastLogin}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && <EmptyState icon={Users} title="No students found" subtitle="Try adjusting your search or filters" />}
      </Card>
    </div>
  );
}
