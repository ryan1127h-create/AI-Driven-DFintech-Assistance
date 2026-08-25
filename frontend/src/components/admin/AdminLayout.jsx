import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, MessageSquare, AlertTriangle, FileText, Users,
  BookOpen, BarChart3, ScrollText, Settings, GraduationCap, LogOut,
  ChevronLeft, Search, UserPlus,
} from "lucide-react";
import { useRole } from "../../context/RoleContext";
import { cn } from "../../utils/cn";
import ThemeToggle from "../ThemeToggle";
import nusLogo from "../../assets/nus_logo.png";



export default function AdminLayout() {
  const { user, role, logout } = useRole();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const isSystemAdmin = role === "System Admin";
  console.log(isSystemAdmin)

  const navItems = [
    { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/admin/inquiries", label: "Inquiries", icon: MessageSquare },
    { to: "/admin/escalations", label: "Escalations", icon: AlertTriangle },
    { to: "/admin/applications", label: "Applications", icon: FileText },
    { to: "/admin/students", label: "Students", icon: Users },
    { to: "/admin/knowledge", label: "Knowledge Base", icon: BookOpen },
    { to: "/admin/analytics", label: "Analytics", icon: BarChart3 },
    { to: "/admin/logs", label: "Activity Logs", icon: ScrollText },
    ...(isSystemAdmin
      ? [
          {
            to: "/admin/register",
            label: "Staff Registration",
            icon: UserPlus,
          },
        ]
      : []),
    { to: "/admin/settings", label: "Settings", icon: Settings },
  ];

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <div className="aurora-bg h-screen flex overflow-hidden">
      <aside className={cn("flex-shrink-0 flex flex-col border-r border-app-subtle glass transition-all", collapsed ? "w-16" : "w-60")}>
        <div className="flex items-center justify-between px-4 py-4">
          {!collapsed && (
            <button onClick={() => navigate("/admin")} className="flex items-center gap-2.5">
              <div className="flex h-10 w-18 items-center justify-center rounded-xl overflow-hidden">
                <img
                    src={nusLogo}
                    alt="NUS Logo"
                    className="h-full w-full object-cover"
                />
              </div>
              <div className="text-left">
                <p className="font-display text-sm font-bold text-app-primary leading-tight">DFT Admin</p>
                <p className="text-[10px] text-app-muted">Staff Portal</p>
              </div>
            </button>
          )}
          <button onClick={() => setCollapsed(!collapsed)} className="text-app-faint hover:text-app-primary transition">
            <ChevronLeft size={16} className={cn("transition-transform", collapsed && "rotate-180")} />
          </button>
        </div>

        <nav className="flex-1 px-2 py-2 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn("sidebar-item", isActive && "sidebar-item-active", collapsed && "justify-center")
                }
                title={collapsed ? item.label : undefined}
              >
                <Icon size={16} className="flex-shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        <div className="px-2 py-3 border-t border-app-subtle">
          <div
            className={cn("flex items-center gap-2.5 rounded-lg p-2 hover:bg-app-hover transition cursor-pointer", collapsed && "justify-center")}
            onClick={handleLogout}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-royal-500/20 text-royal-300 text-xs font-medium flex-shrink-0">
              {user?.avatar}
            </div>
            {!collapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-app-primary truncate">{user?.name}</p>
                <p className="text-[10px] text-app-muted truncate">Administrator</p>
              </div>
            )}
            {!collapsed && <LogOut size={14} className="text-app-faint hover:text-red-400 transition" />}
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="flex items-center justify-end px-6 lg:px-10 pt-6">
          <ThemeToggle />
        </div>
        <div className="max-w-6xl mx-auto px-6 lg:px-10 py-2">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
