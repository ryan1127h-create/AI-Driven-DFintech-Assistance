import { useNavigate } from "react-router-dom";
import { LogOut, ShieldCheck } from "lucide-react";
import { logout as apiLogout } from "../../api";
import { useRole } from "../context/RoleContext";
import ThemeToggle from "../components/ThemeToggle";
import { EmptyState } from "../components/ui";

// Placeholder until the staff console is built.
export default function AdminPage() {
  const { user, logout } = useRole();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch (err) {
      console.error(err);
    }
    logout(navigate);
  };

  return (
    <div className="aurora-bg min-h-screen">
      <div className="max-w-3xl mx-auto px-6 py-6">
        <div className="flex items-center justify-between">
          <p className="font-display text-sm font-bold text-app-primary">DFT Admin · {user?.name}</p>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <button onClick={handleLogout} className="btn-outline text-xs">
              <LogOut size={14} /> Log out
            </button>
          </div>
        </div>
        <div className="mt-24">
          <EmptyState icon={ShieldCheck} title="Staff console" subtitle="The admin console is not available yet." />
        </div>
      </div>
    </div>
  );
}
