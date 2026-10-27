import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertCircle, KeyRound, Loader2, Mail } from "lucide-react";
import { confirmPasswordReset, requestPasswordReset } from "../../api";
import ThemeToggle from "../components/ThemeToggle";
import nusLogo from "../assets/nus_logo.png";

// Password reset (backend POST /auth/password-reset/request and /confirm):
// a 6-digit code is emailed to the account's address, then the code and a
// new password set it. The first step answers the same whether or not the
// email is registered.

const MIN_PASSWORD = 8;

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async (action) => {
    setError("");
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const sendCode = (event) => {
    event.preventDefault();
    run(async () => {
      await requestPasswordReset(email.trim());
      setStep("code");
    });
  };

  const reset = (event) => {
    event.preventDefault();
    if (password.length < MIN_PASSWORD) return setError(`The password needs at least ${MIN_PASSWORD} characters.`);
    if (password !== confirm) return setError("The two passwords don't match.");
    run(async () => {
      await confirmPasswordReset({ email: email.trim(), code: code.trim(), password });
      navigate("/login", { state: { notice: "Your password has been reset. Sign in with the new one." } });
    });
  };

  return (
    <div className="aurora-bg min-h-screen flex flex-col">
      <header className="flex items-center justify-between px-6 lg:px-12 py-5">
        <Link to="/" className="flex items-center gap-3">
          <img src={nusLogo} alt="NUS Logo" className="h-10 w-auto rounded-xl" />
          <div>
            <p className="font-display font-bold text-app-primary leading-tight">NUS DFT</p>
            <p className="text-xs text-app-muted">AI Student Lifecycle Assistant</p>
          </div>
        </Link>
        <ThemeToggle />
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-8">
        <div className="max-w-md w-full">
          <div className="text-center mb-8">
            <h1 className="font-display text-2xl font-bold text-app-primary mb-2">Reset your password</h1>
            <p className="text-sm text-app-muted">
              {step === "email"
                ? "Enter the email you sign in with and we'll send you a code."
                : `If ${email.trim()} has an account, a 6-digit code is on its way. Enter it with your new password.`}
            </p>
          </div>

          {error && (
            <div role="alert" className="mb-4 flex items-center gap-2 rounded-lg p-3 bg-red-500/10 border border-red-400/20 text-sm text-red-400">
              <AlertCircle size={16} /> {error}
            </div>
          )}

          {step === "email" ? (
            <form onSubmit={sendCode} className="space-y-4">
              <div>
                <label htmlFor="reset-email" className="text-sm font-medium text-app-secondary mb-1.5 block">Email</label>
                <input id="reset-email" type="email" required autoComplete="email" className="input"
                  value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
              </div>
              <button type="submit" disabled={busy} className="btn-primary w-full justify-center">
                {busy ? <Loader2 size={16} className="animate-spin" /> : <Mail size={16} />} Send code
              </button>
            </form>
          ) : (
            <form onSubmit={reset} className="space-y-4">
              <div>
                <label htmlFor="reset-code" className="text-sm font-medium text-app-secondary mb-1.5 block">Code</label>
                <input id="reset-code" required inputMode="numeric" maxLength={6} pattern="\d{6}" autoComplete="one-time-code"
                  className="input tracking-widest" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
              </div>
              <div>
                <label htmlFor="reset-password" className="text-sm font-medium text-app-secondary mb-1.5 block">New password</label>
                <input id="reset-password" type="password" required minLength={MIN_PASSWORD} autoComplete="new-password"
                  className="input" value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              <div>
                <label htmlFor="reset-confirm" className="text-sm font-medium text-app-secondary mb-1.5 block">Confirm new password</label>
                <input id="reset-confirm" type="password" required minLength={MIN_PASSWORD} autoComplete="new-password"
                  className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
              </div>
              <button type="submit" disabled={busy} className="btn-primary w-full justify-center">
                {busy ? <Loader2 size={16} className="animate-spin" /> : <KeyRound size={16} />} Reset password
              </button>
              <button type="button" disabled={busy} className="w-full text-center text-sm text-brand-300 hover:underline"
                onClick={() => run(() => requestPasswordReset(email.trim()))}>
                Send a new code
              </button>
            </form>
          )}

          <div className="mt-6 text-center text-sm text-app-muted">
            <Link to="/login" className="text-app-faint hover:text-app-secondary">Back to sign in</Link>
          </div>
        </div>
      </main>
    </div>
  );
}
