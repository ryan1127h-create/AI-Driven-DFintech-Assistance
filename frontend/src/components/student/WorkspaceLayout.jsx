import { Outlet } from "react-router-dom";
import { useRole } from "../../context/RoleContext";
import { ROLE_META } from "../../data/roles";
import StudentSidebar from "./StudentSidebar";

export default function WorkspaceLayout() {
  const { user } = useRole();
  const meta = ROLE_META[user?.role];

  return (
    <div className="aurora-bg h-screen flex overflow-hidden">
      <StudentSidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 lg:px-10 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
