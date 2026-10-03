import { Outlet } from "react-router-dom";
import StudentSidebar from "./StudentSidebar";

// The signed-in shell: one sidebar shared by the chat (/app) and the
// workspace pages (/workspace/*), so moving between them only swaps the
// main area and the sidebar keeps its state (conversation list, collapse).
export default function StudentLayout() {
  return (
    <div className="aurora-bg h-screen flex overflow-hidden">
      <StudentSidebar />
      <main className="flex-1 min-w-0 flex flex-col">
        <Outlet />
      </main>
    </div>
  );
}
