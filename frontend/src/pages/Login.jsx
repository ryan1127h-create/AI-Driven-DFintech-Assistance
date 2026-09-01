import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { GraduationCap, LogIn, AlertCircle, Loader2, User, BookOpen, ShieldCheck } from "lucide-react";
import { login as apiLogin } from "../../api";
import { useRole } from "../../src/context/RoleContext";
import ThemeToggle from "../components/ThemeToggle";
import { cn } from "../utils/cn";
import nusLogo from "../assets/nus_logo.png";

const tabs = [
  { id: "applicant", label: "Applicant", icon: User, hint: "Prospective & applying students" },
  { id: "student", label: "Current Student", icon: BookOpen, hint: "Enrolled, graduating & alumni" },
  { id: "admin", label: "Staff / Admin", icon: ShieldCheck, hint: "Management portal" },
];
const adminRoles = [
  "System Admin",
  "Admissions Staff",
  "Career Advisor",
  "Program Office",
  "Faculty Support",
];

export default function Login() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("applicant");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const { login: setAuth } = useRole();

  // const handleSubmit = async (e) => {
  //   e.preventDefault();

  //   setError(null);
  //   setLoading(true);

  //   try {
  //     const response =
  //       await login({
  //         email,
  //         password
  //       });

  //     const { session, user, roles } = response.data;

  //     const role = roles?.[0]?.roles?.role_name || null;
 
  //     setAuth({
  //       session,
  //       user,
  //       role,
  //     });

  //     const roleNames =
  //       roles.map(
  //         role => role.roles.role_name
  //       );

  //     if (adminRoles.some(role => roleNames.includes(role))) {
  //       navigate("/admin");
  //     } else {
  //       navigate("/app");
  //     }

  //   } catch (err) {

  //     setError(
  //       err.message ||
  //       "Failed to sign in."
  //     );

  //   } finally {
  //     setLoading(false);
  //   }
  // };
   const handleSubmit = async (e) => {
    e.preventDefault();

    setError(null);
    setLoading(true);

    try {
      const response =
        await apiLogin({
          email,
          password
        });
      const { access_token, token_type, expires_in } = response;

      setAuth({
        access_token,
        user: {
          email,
        },
        role: "Prospective Student",
      });

      navigate("/app");

    } catch (err) {
      console.error("LOGIN ERROR:", err);
      setError(
        err.message ||
        "Failed to sign in."
      );

    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="aurora-bg min-h-screen flex flex-col">
      <header className="flex items-center justify-between px-6 lg:px-12 py-5">
        <button onClick={() => navigate("/")} className="flex items-center gap-3">
          <div className="flex h-10 w-18 items-center justify-center rounded-xl overflow-hidden">
            <img
                src={nusLogo}
                alt="NUS Logo"
                className="h-full w-full object-cover"
            />
          </div>
          <div>
            <p className="font-display font-bold text-app-primary leading-tight text-left">NUS DFT</p>
            <p className="text-xs text-app-muted">AI Student Lifecycle Assistant</p>
          </div>
        </button>
        <ThemeToggle />
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-8">
        <div className="max-w-md w-full">
          <div className="text-center mb-8 animate-fadeIn">
            <h1 className="font-display text-2xl font-bold text-app-primary mb-2">Welcome Back</h1>
            <p className="text-sm text-app-muted">Sign in to continue your journey</p>
          </div>

          {/* Role tabs */}
          {/* <div className="grid grid-cols-3 gap-2 mb-6">
            {tabs.map((t) => {
              const TIcon = t.icon;
              return (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={cn(
                    "flex flex-col items-center gap-1.5 rounded-xl p-3 border transition-all",
                    tab === t.id
                      ? "bg-brand-500/15 border-brand-400/30 text-brand-300"
                      : "bg-app-hover border-app-soft text-app-secondary hover:border-brand-400/20",
                  )}
                >
                  <TIcon size={20} />
                  <span className="text-xs font-medium">{t.label}</span>
                </button>
              );
            })}
          </div> */}

          {/* <p className="text-center text-xs text-app-muted mb-6">{tabs.find((t) => t.id === tab).hint}</p> */}

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 rounded-lg p-3 bg-red-500/10 border border-red-400/20 text-sm text-red-400">
                <AlertCircle size={16} />
                {error}
              </div>
            )}
            <div>
              <label className="text-sm font-medium text-app-secondary mb-1.5 block">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="input"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-app-secondary mb-1.5 block">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="input"
              />
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
              {loading ? <><Loader2 size={16} className="animate-spin" /> Signing in...</> : <><LogIn size={16} /> Sign In</>}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-app-muted">
            {tab === "applicant" && (
              <p>New to MSc DFT? <Link to="/register" className="text-brand-300 hover:underline">Register your profile</Link></p>
            )}
          </div>
          <div className="mt-2 text-center text-sm text-app-muted">
            <Link to="/" className="text-app-faint hover:text-app-secondary">Back to home</Link>
          </div>
        </div>
      </main>
    </div>
  );
}
