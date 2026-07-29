import { useState } from "react";
import { Outlet } from "react-router-dom";
import StudentSidebar from "./StudentSidebar";
import ContextPanel from "./ContextPanel";
import { useRole } from "../../context/RoleContext";

export default function StudentLayout() {
  const { user } = useRole();
  const [contextOpen, setContextOpen] = useState(true);

  return (
    <div className="aurora-bg h-screen flex overflow-hidden">
      <StudentSidebar />
      <div className="flex-1 flex min-w-0">
        <main className="flex-1 min-w-0 flex flex-col">
          <Outlet />
        </main>
        {contextOpen && (
          <aside className="hidden xl:flex w-80 flex-shrink-0 border-l border-app-subtle">
            <ContextPanel />
          </aside>
        )}
      </div>
    </div>
  );
}
