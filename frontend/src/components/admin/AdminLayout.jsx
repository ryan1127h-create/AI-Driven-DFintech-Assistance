import { Outlet } from "react-router-dom";
import AdminSidebar from "./AdminSidebar";

export default function AdminLayout() {
  return (
    <div className="admin-platform-shell aurora-bg min-h-screen flex">
      <AdminSidebar />
      <div className="admin-main-column flex-1 min-w-0">
        <main className="min-w-0"><Outlet /></main>
      </div>
    </div>
  );
}
