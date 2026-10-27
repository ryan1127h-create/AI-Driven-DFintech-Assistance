import { Outlet } from "react-router-dom";

// The scrolling, centred content area of the workspace pages (profile,
// checklist, lifecycle), inside StudentLayout.
export default function WorkspaceLayout() {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 lg:px-10 py-8">
        <Outlet />
      </div>
    </div>
  );
}
