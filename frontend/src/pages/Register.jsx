import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Loader2,
  AlertCircle,
  Mail,
} from "lucide-react";

import { register, resendVerificationCode, verifyEmail } from "../../api";
import { useRole } from "../../src/context/RoleContext";
import ThemeToggle from "../components/ThemeToggle";
import { cn } from "../utils/cn";
import nusLogo from "../assets/nus_logo.png";

const ROLE_OPTIONS = [
  { value: "applicant", label: "Applicant", hint: "Prospective or currently applying — any email works" },
  { value: "enrolled_student", label: "Enrolled Student", hint: "Email always ends in @u.nus.edu" },
];

const NUS_EMAIL_DOMAIN = "@u.nus.edu";
const RESEND_COOLDOWN_SECONDS = 60;

export default function Register() {
  const navigate = useNavigate();
  const { login: setAuth } = useRole();

  // "form" (email/password/role) -> "code" (enter the emailed 6-digit code,
  // which on success logs the new account straight in — no separate /login
  // round trip, see backend/app/domains/auth/api.py::verify_email).
  const [step, setStep] = useState("form");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [resendCooldown, setResendCooldown] = useState(0);

  const [form, setForm] = useState({
    email: "",
    password: "",
    confirmPassword: "",
    full_name: "",
    role: "applicant",
  });
  // Local part only (before "@u.nus.edu") for the enrolled_student role —
  // kept separate from form.email so the fixed domain suffix can never be
  // edited, replacing the old "does form.email end with @u.nus.edu" check.
  const [nusLocalPart, setNusLocalPart] = useState("");
  const [code, setCode] = useState("");

  const emailValue =
    form.role === "enrolled_student"
      ? (nusLocalPart.trim() ? `${nusLocalPart.trim()}${NUS_EMAIL_DOMAIN}` : "")
      : form.email.trim();

  const startResendCooldown = () => {
    setResendCooldown(RESEND_COOLDOWN_SECONDS);
    const timer = setInterval(() => {
      setResendCooldown((s) => {
        if (s <= 1) {
          clearInterval(timer);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!form.full_name.trim()) {
      setError("Full name is required");
      return;
    }
    if (!emailValue) {
      setError(form.role === "enrolled_student" ? "Your NUS email (before @u.nus.edu) is required" : "Email is required");
      return;
    }
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setSaving(true);
    try {
      await register({
        email: emailValue,
        password: form.password,
        full_name: form.full_name,
        role: form.role,
      });
      setForm((f) => ({ ...f, email: emailValue }));
      setStep("code");
      startResendCooldown();
    } catch (err) {
      setError(err.message || "Registration failed.");
    } finally {
      setSaving(false);
    }
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const response = await verifyEmail({ email: form.email, code });
      setAuth({ access_token: response.access_token, user: response.user, role: response.user.role });
      navigate(response.user.role === "admin" ? "/admin" : "/app");
    } catch (err) {
      setError(err.message || "Verification failed.");
    } finally {
      setSaving(false);
    }
  };

  const handleResend = async () => {
    if (resendCooldown > 0) return;
    setError(null);
    try {
      await resendVerificationCode(form.email);
      startResendCooldown();
    } catch (err) {
      setError(err.message || "Failed to resend the code.");
    }
  };

  return (
    <div className="aurora-bg min-h-screen flex flex-col">
      <header className="flex items-center justify-between px-6 lg:px-12 py-5">
        <button onClick={() => navigate("/")} className="flex items-center gap-3">
          <div className="flex h-10 w-18 items-center justify-center rounded-xl overflow-hidden">
            <img src={nusLogo} alt="NUS Logo" className="h-full w-full object-cover" />
          </div>
          <div>
            <p className="font-display font-bold text-app-primary leading-tight text-left">NUS DFT</p>
            <p className="text-xs text-app-muted">AI Student Lifecycle Assistant</p>
          </div>
        </button>
        <ThemeToggle />
      </header>

      <main className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-md">
          <div className="rounded-2xl border border-app-soft bg-app-card p-8 shadow-xl">
            {step === "form" ? (
              <>
                <h1 className="font-display text-2xl font-bold text-app-primary mb-2">Create Account</h1>
                <p className="text-app-muted mb-6">Register with your email and password.</p>

                {error && (
                  <div className="mb-4 flex items-center gap-2 rounded-lg p-3 bg-red-500/10 border border-red-400/20 text-sm text-red-400">
                    <AlertCircle size={16} />
                    {error}
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="text-sm font-medium text-app-secondary mb-1.5 block">I am a...</label>
                    <div className="grid grid-cols-2 gap-2">
                      {ROLE_OPTIONS.map((opt) => (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => setForm({ ...form, role: opt.value })}
                          className={cn(
                            "flex flex-col items-start gap-0.5 rounded-xl p-3 border text-left transition-all",
                            form.role === opt.value
                              ? "bg-brand-500/15 border-brand-400/30 text-brand-300"
                              : "bg-app-hover border-app-soft text-app-secondary hover:border-brand-400/20",
                          )}
                        >
                          <span className="text-sm font-medium">{opt.label}</span>
                          <span className="text-xs text-app-muted">{opt.hint}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="text-sm font-medium text-app-secondary mb-1.5 block">Full Name</label>
                    <input
                      type="text"
                      className="input"
                      placeholder="John Tan"
                      value={form.full_name}
                      onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                      required
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium text-app-secondary mb-1.5 block">Email</label>
                    {form.role === "enrolled_student" ? (
                      <div
                        className="w-full flex items-center gap-1 rounded-lg px-3.5 py-2.5 text-sm transition focus-within:ring-1 focus-within:ring-brand-500/40"
                        style={{ background: "var(--bg-input)", border: "1px solid var(--border-input)" }}
                      >
                        <input
                          type="text"
                          className="min-w-0 flex-1 bg-transparent border-0 p-0 outline-none text-app-primary placeholder:text-[var(--text-faint)]"
                          placeholder="e0123456"
                          value={nusLocalPart}
                          onChange={(e) => setNusLocalPart(e.target.value.replace(/[^a-zA-Z0-9._+-]/g, ""))}
                          required
                        />
                        <span className="text-app-muted whitespace-nowrap select-none">{NUS_EMAIL_DOMAIN}</span>
                      </div>
                    ) : (
                      <input
                        type="email"
                        className="input"
                        placeholder="you@example.com"
                        value={form.email}
                        onChange={(e) => setForm({ ...form, email: e.target.value })}
                        required
                      />
                    )}
                  </div>

                  <div>
                    <label className="text-sm font-medium text-app-secondary mb-1.5 block">Password</label>
                    <input
                      type="password"
                      className="input"
                      placeholder="Minimum 8 characters"
                      value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      required
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium text-app-secondary mb-1.5 block">Confirm Password</label>
                    <input
                      type="password"
                      className="input"
                      placeholder="Retype your password"
                      value={form.confirmPassword}
                      onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })}
                      required
                    />
                  </div>

                  <div className="flex gap-3">
                    <button type="button" onClick={() => navigate("/")} className="btn-outline flex-1">
                      Cancel
                    </button>
                    <button type="submit" disabled={saving} className="btn-primary flex-1">
                      {saving ? (
                        <>
                          <Loader2 size={16} className="animate-spin" /> Registering...
                        </>
                      ) : (
                        "Register"
                      )}
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <>
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-300 mb-4">
                  <Mail size={22} />
                </div>
                <h1 className="font-display text-2xl font-bold text-app-primary mb-2">Check your email</h1>
                <p className="text-app-muted mb-6">
                  We sent a 6-digit code to <span className="text-app-secondary">{form.email}</span>. Enter it
                  below to finish creating your account.
                </p>

                {error && (
                  <div className="mb-4 flex items-center gap-2 rounded-lg p-3 bg-red-500/10 border border-red-400/20 text-sm text-red-400">
                    <AlertCircle size={16} />
                    {error}
                  </div>
                )}

                <form onSubmit={handleVerify} className="space-y-4">
                  <div>
                    <label className="text-sm font-medium text-app-secondary mb-1.5 block">Verification Code</label>
                    <input
                      type="text"
                      inputMode="numeric"
                      pattern="\d{6}"
                      maxLength={6}
                      className="input tracking-[0.3em] text-center text-lg"
                      placeholder="000000"
                      value={code}
                      onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                      required
                    />
                  </div>

                  <button type="submit" disabled={saving || code.length !== 6} className="btn-primary w-full justify-center">
                    {saving ? (
                      <>
                        <Loader2 size={16} className="animate-spin" /> Verifying...
                      </>
                    ) : (
                      "Verify & Continue"
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={resendCooldown > 0}
                    className="w-full text-center text-sm text-app-muted hover:text-app-secondary disabled:opacity-50"
                  >
                    {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : "Didn't get a code? Resend"}
                  </button>

                  <button
                    type="button"
                    onClick={() => setStep("form")}
                    className="w-full text-center text-xs text-app-faint hover:text-app-secondary"
                  >
                    Back to edit details
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
