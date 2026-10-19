import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { AlertTriangle, BookOpen, ChevronLeft, ClipboardList, GraduationCap, LayoutDashboard, MessageSquare, Users } from "lucide-react";
import { cn } from "../../utils/cn";
import { useRole } from "../../context/RoleContext";
import { logout as apiLogout } from "../../../api";
import AccountMenu from "../settings/AccountMenu";
import nusLogo from "../../assets/nus_logo.png";


const navItems = [
  { to: "/admin", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/applications", label: "Applications", icon: ClipboardList },
  { to: "/admin/conversations", label: "Conversations", icon: MessageSquare },
  { to: "/admin/escalations", label: "Escalation Cases", icon: AlertTriangle },
  { to: "/admin/alumni", label: "Alumni", icon: GraduationCap },
  { to: "/admin/knowledge", label: "Knowledge Base", icon: BookOpen },
];

export default function AdminSidebar() {
  const { user, logout } = useRole();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch (error) {
      console.error("Unable to log out from the admin console:", error);
    }
    logout(navigate);
  };

  return (
    <div className={cn(
      "sticky top-0 h-screen flex-shrink-0 border-r border-app-subtle glass px-3 py-5 flex flex-col transition-[width] duration-200",
      collapsed ? "w-16 items-center" : "w-72",
    )}>
      <div className={cn("flex items-center mb-8", collapsed ? "justify-center" : "gap-2 px-3")}>
        <img src={nusLogo} alt="NUS logo" className={cn("object-contain", collapsed ? "h-9 w-10" : "h-10 w-18")} />
        {!collapsed && <div>
          <p className="font-display text-sm font-bold text-app-primary">DFT Admin</p>
          <p className="text-[10px] tracking-wider text-app-faint">Staff Console</p>
        </div>
        }
        {!collapsed && (
          <button type="button" onClick={() => setCollapsed(true)} className="ml-auto text-app-faint hover:text-app-primary transition" title="Collapse sidebar">
            <ChevronLeft size={16} />
          </button>
        )}
      </div>
      {collapsed && (
        <button type="button" onClick={() => setCollapsed(false)} className="sidebar-item mb-4 h-10 w-10 justify-center px-0" title="Expand sidebar">
          <ChevronLeft size={18} className="rotate-180" />
        </button>
      )}
      <nav className={cn("space-y-1", collapsed && "w-full")} aria-label="Admin navigation">
        {navItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            title={collapsed ? label : undefined}
            aria-label={collapsed ? label : undefined}
            className={({ isActive }) => cn("sidebar-item w-full", collapsed && "justify-center px-0", isActive && "sidebar-item-active")}
          >
            <Icon size={16} />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>
      <div className={cn("mt-auto py-3 border-t border-app-subtle", collapsed ? "w-full" : "w-full px-0")}>
        <AccountMenu
          user={user}
          subtitle="Administrator"
          onLogout={handleLogout}
          showSettings={false}
          showAppearance
          compact={collapsed}
        />
      </div>
    </div>
  );
}
