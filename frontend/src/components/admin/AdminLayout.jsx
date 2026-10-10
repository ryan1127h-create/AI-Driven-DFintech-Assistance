import { Outlet } from "react-router-dom";
import AdminSidebar from "./AdminSidebar";

export default function AdminLayout() {
  return (
    <div className="aurora-bg min-h-screen flex">
      <AdminSidebar />
      <main className="flex-1 min-w-0">
        <Outlet />
      </main>
    </div>
  );
}
