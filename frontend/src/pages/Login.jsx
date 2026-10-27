import { useState } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import { LogIn, AlertCircle, Loader2, User, BookOpen, ShieldCheck } from "lucide-react";
import { login as apiLogin } from "../../api";
import { useRole } from "../../src/context/RoleContext";
import ThemeToggle from "../components/ThemeToggle";
import { cn } from "../utils/cn";
import nusLogo from "../assets/nus_logo.png";

const NUS_EMAIL_DOMAIN = "@u.nus.edu";

// ids match the backend's login portals (see
// backend/app/domains/auth/schemas.py::Role) — the tab the user picks is
// sent as part of the login request and checked against the account (see
// service.py::login_portal), so picking the wrong tab is rejected with a
// clear message rather than silently logging in anyway. Alumni share the
// "admin" tab with staff.
const tabs = [
  { id: "applicant", label: "Applicant", icon: User, hint: "Prospective & applying students" },
  { id: "enrolled_student", label: "Enrolled Student", icon: BookOpen, hint: "Email always ends in @u.nus.edu" },
  { id: "admin", label: "Alumni / Admin", icon: ShieldCheck, hint: "Alumni and programme staff" },
];

export default function Login() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("applicant");
  const [email, setEmail] = useState("");
  // Local part only (before "@u.nus.edu") for the enrolled_student tab —
  // kept separate from `email` so the fixed domain suffix can never be
  // edited, replacing the old "does email end with @u.nus.edu" check.
  const [nusLocalPart, setNusLocalPart] = useState("");
  const [password, setPassword] = useState("");
  const { login: setAuth, sessionExpired } = useRole();
  // Set by the password reset page on success.
  const notice = useLocation().state?.notice;
  const [error, setError] = useState(sessionExpired ? "Your session has expired. Log in again." : null);
  const [loading, setLoading] = useState(false);

  const emailValue = tab === "enrolled_student" ? `${nusLocalPart.trim()}${NUS_EMAIL_DOMAIN}` : email.trim();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (tab === "enrolled_student" && !nusLocalPart.trim()) {
      setError("Your NUS email (before @u.nus.edu) is required.");
      return;
    }

    setLoading(true);
    try {
      const response = await apiLogin({ email: emailValue, password, role: tab });
      const { access_token, user } = response;

      setAuth({ access_token, user, role: user.role });

      navigate(user.role === "admin" ? "/admin" : user.lifecycle_stage === "alumni" ? "/alumni-match" : "/app");

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
          <div className="flex h-10 w-[72px] shrink-0 items-center justify-center rounded-xl overflow-hidden">
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
          <div className="grid grid-cols-3 gap-2 mb-2" role="tablist" aria-label="Sign in as">
            {tabs.map((t) => {
              const TIcon = t.icon;
              return (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  onClick={() => setTab(t.id)}
                  className={cn(
                    "flex flex-col items-center gap-1.5 rounded-xl p-3 border transition-all",
                    tab === t.id
                      ? "bg-brand-500/15 border-brand-400/30 text-brand-300"
                      : "bg-app-hover border-app-soft text-app-secondary hover:border-brand-400/20",
                  )}
                >
                  <TIcon size={20} aria-hidden="true" />
                  <span className="text-xs font-medium">{t.label}</span>
                </button>
              );
            })}
          </div>

          <p className="text-center text-xs text-app-muted mb-6">{tabs.find((t) => t.id === tab).hint}</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {notice && !error && (
              <div role="status" className="rounded-lg p-3 bg-emerald2-500/10 border border-emerald2-400/20 text-sm text-emerald2-400">
                {notice}
              </div>
            )}
            {error && (
              <div className="flex items-center gap-2 rounded-lg p-3 bg-red-500/10 border border-red-400/20 text-sm text-red-400">
                <AlertCircle size={16} />
                {error}
              </div>
            )}
            <div>
              <label htmlFor="login-email" className="text-sm font-medium text-app-secondary mb-1.5 block">Email</label>
              {tab === "enrolled_student" ? (
                <div
                  className="w-full flex items-center gap-1 rounded-lg px-3.5 py-2.5 text-sm transition focus-within:ring-1 focus-within:ring-brand-500/40"
                  style={{ background: "var(--bg-input)", border: "1px solid var(--border-input)" }}
                >
                  <input
                    id="login-email"
                    type="text"
                    required
                    aria-describedby="login-email-domain"
                    className="min-w-0 flex-1 bg-transparent border-0 p-0 outline-none text-app-primary placeholder:text-[var(--text-faint)]"
                    placeholder="e0123456"
                    value={nusLocalPart}
                    onChange={(e) => setNusLocalPart(e.target.value.replace(/[^a-zA-Z0-9._+-]/g, ""))}
                  />
                  <span id="login-email-domain" className="text-app-muted whitespace-nowrap select-none">{NUS_EMAIL_DOMAIN}</span>
                </div>
              ) : (
                <input
                  id="login-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="input"
                />
              )}
            </div>
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label htmlFor="login-password" className="text-sm font-medium text-app-secondary">Password</label>
                <Link to="/forgot-password" className="text-xs text-brand-300 hover:underline">Forgot password?</Link>
              </div>
              <input
                id="login-password"
                type="password"
                autoComplete="current-password"
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
            {tab !== "admin" && (
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
