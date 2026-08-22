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
  LogIn,
} from "lucide-react";
import { ROLES, ROLE_META } from "../data/roles";
import ThemeToggle from "../components/ThemeToggle";
import nusLogo from "../assets/nus_logo.png";

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
  const navigate = useNavigate();

  return (
    <div className="aurora-bg min-h-screen flex flex-col">
      <header className="flex items-center justify-between px-6 lg:px-12 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-18 items-center justify-center rounded-xl overflow-hidden">
            <img
                src={nusLogo}
                alt="NUS Logo"
                className="h-full w-full object-cover"
            />
          </div>
          <div>
            <p className="font-display font-bold text-app-primary leading-tight">NUS DFT</p>
            <p className="text-xs text-app-muted">AI Student Lifecycle Assistant</p>
          </div>
        </div>
        
        <div className="sm:hidden flex items-center gap-2">
          <button onClick={() => navigate("/register")} className="btn-outline text-xs">
            <UserPlus size={14} />
          </button>
          <button onClick={() => navigate("/login")} className="btn-primary text-xs">
            <LogIn size={14} />
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
            <span>guided by AI.</span>
          </h1>
          <p className="mt-4 text-app-secondary text-lg max-w-xl mx-auto">
            From discovering the programme to becoming alumni — an intelligent
            assistant for every stage of the NUS MSc Digital Financial Technology
            lifecycle.
          </p>
        </div>

        <div className="mt-10 flex flex-col md:flex-row justify-center gap-4">

          {/* Login Card */}
          <button
            onClick={() => navigate("/login")}
            className="group w-full md:w-80 rounded-3xl border border-app-subtle bg-app-glass p-6 text-left transition-all duration-300 hover:scale-[1.02] hover:border-brand-500"
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500 text-white">
              <LogIn size={20} />
            </div>

            <h3 className="text-xl font-semibold text-app-primary">
              Log In
            </h3>

            <p className="mt-2 text-sm text-app-secondary">
              Access your personalized dashboard, AI assistant and academic journey.
            </p>

            <div className="mt-4 text-sm font-medium text-brand-500">
              Welcome back →
            </div>
          </button>

          {/* Register Card */}
          <button
            onClick={() => navigate("/register")}
            className="group w-full md:w-80 rounded-3xl border border-app-subtle bg-app-glass p-6 text-left transition-all duration-300 hover:scale-[1.02] hover:border-[#EF7C00]"
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#EF7C00] text-white">
              <UserPlus size={20} />
            </div>

            <h3 className="text-xl font-semibold text-app-primary">
              Register Profile
            </h3>

            <p className="mt-2 text-sm text-app-secondary">
              Create your account and begin your NUS MSc Digital Financial Technology journey.
            </p>

            <div className="mt-4 text-sm font-medium text-[#EF7C00]">
              Get started →
            </div>
          </button>

        </div>
        
      </main>

      <footer className="px-6 lg:px-12 py-5 text-center text-xs text-app-faint">
        NUS School of Computing · MSc in Digital Financial Technology
      </footer>
    </div>
  );
}
