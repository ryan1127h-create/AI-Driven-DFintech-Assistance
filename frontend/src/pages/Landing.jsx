import { useNavigate } from "react-router-dom";
import {
  GraduationCap,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Compass,
  FileText,
  CheckCircle,
  BookOpen,
  Users,
  UserPlus,
} from "lucide-react";
import { ROLES, ROLE_META } from "../data/roles";
import { useRole } from "../context/RoleContext";
import ThemeToggle from "../components/ThemeToggle";

const studentRoles = [
  ROLES.PROSPECTIVE,
  ROLES.APPLICANT,
  ROLES.ADMITTED,
  ROLES.ENROLLED,
  ROLES.GRADUATING,
  ROLES.ALUMNI,
];

const iconMap = {
  Compass,
  FileText,
  CheckCircle,
  BookOpen,
  GraduationCap,
  Users,
  ShieldCheck,
};

const colorClasses = {
  brand: "bg-brand-500/15 text-brand-300",
  royal: "bg-royal-500/15 text-royal-300",
  cyan2: "bg-cyan2-500/15 text-cyan2-400",
  emerald2: "bg-emerald2-500/15 text-emerald2-400",
  ink: "bg-app-hover text-app-secondary",
};

export default function Landing() {
  const { loginAs } = useRole();
  const navigate = useNavigate();

  const handleSelect = (role) => {
    loginAs(role);
    navigate(role === ROLES.STAFF ? "/admin" : "/app");
  };

  return (
    <div className="aurora-bg min-h-screen flex flex-col">
      <header className="flex items-center justify-between px-6 lg:px-12 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-royal-600 text-app-primary shadow-glow">
            <GraduationCap size={22} />
          </div>
          <div>
            <p className="font-display font-bold text-app-primary leading-tight">NUS DFT</p>
            <p className="text-xs text-app-muted">AI Student Lifecycle Assistant</p>
          </div>
        </div>
        <div className="hidden sm:flex items-center gap-3">
          <button onClick={() => navigate("/register")} className="btn-outline text-xs">
            <UserPlus size={14} /> Register Profile
          </button>
          <div className="flex items-center gap-2 text-xs text-app-muted">
            <Sparkles size={14} className="text-brand-300" />
            AI-first · Conversation-first
          </div>
        </div>
        <div className="sm:hidden">
          <button onClick={() => navigate("/register")} className="btn-outline text-xs">
            <UserPlus size={14} /> Register
          </button>
        </div>
        <ThemeToggle />
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-6 lg:px-12 py-8">
        <div className="max-w-3xl w-full text-center mb-10 animate-fadeIn">
          <div className="inline-flex items-center gap-2 chip border border-brand-400/20 bg-brand-500/10 text-brand-300 mb-5">
            <Sparkles size={14} />
            Powered by Multi-Agent AI
          </div>
          <h1 className="font-display text-4xl lg:text-5xl font-bold text-app-primary leading-tight">
            Your entire student journey,
            <br />
            <span className="gradient-text">guided by AI.</span>
          </h1>
          <p className="mt-4 text-app-secondary text-lg max-w-xl mx-auto">
            From discovering the programme to becoming alumni — an intelligent
            assistant for every stage of the NUS MSc Digital Financial Technology
            lifecycle.
          </p>
        </div>

        <div className="w-full max-w-4xl">
          <p className="text-center text-sm font-medium text-app-muted mb-4 uppercase tracking-wider">
            Continue as
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {studentRoles.map((r) => {
              const meta = ROLE_META[r];
              const Icon = iconMap[meta.icon] || Compass;
              return (
                <button
                  key={r}
                  onClick={() => handleSelect(r)}
                  className="group card p-4 text-left hover:border-brand-400/40 hover:shadow-glow transition-all duration-300 hover:-translate-y-0.5"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${colorClasses[meta.color] || colorClasses.brand}`}>
                      <Icon size={18} />
                    </div>
                    <ArrowRight
                      size={16}
                      className="text-app-faint group-hover:text-brand-300 group-hover:translate-x-0.5 transition-all"
                    />
                  </div>
                  <p className="font-medium text-app-primary text-sm">{meta.label}</p>
                  <p className="text-xs text-app-muted mt-0.5">{meta.stage} stage</p>
                </button>
              );
            })}
            <button
              onClick={() => handleSelect(ROLES.STAFF)}
              className="group card p-4 text-left hover:border-royal-400/40 hover:shadow-glow transition-all duration-300 hover:-translate-y-0.5 col-span-2 md:col-span-1"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-royal-500/15 text-royal-300">
                  <ShieldCheck size={18} />
                </div>
                <ArrowRight
                  size={16}
                  className="text-app-faint group-hover:text-royal-300 group-hover:translate-x-0.5 transition-all"
                />
              </div>
              <p className="font-medium text-app-primary text-sm">Staff / Admin</p>
              <p className="text-xs text-app-muted mt-0.5">Management portal</p>
            </button>
          </div>

          <div className="mt-6 text-center">
            <p className="text-sm text-app-muted mb-3">New to MSc DFT? Register your profile for AI-powered assessment.</p>
            <button onClick={() => navigate("/register")} className="btn-primary">
              <UserPlus size={16} /> Register Your Profile
            </button>
          </div>
        </div>
      </main>

      <footer className="px-6 lg:px-12 py-5 text-center text-xs text-app-faint">
        NUS School of Computing · MSc in Digital Financial Technology
      </footer>
    </div>
  );
}
