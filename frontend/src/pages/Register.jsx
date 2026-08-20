import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";

// import { register } from "../services/authService";
import { register } from "../../api";
import ThemeToggle from "../components/ThemeToggle";
import nusLogo from "../assets/nus_logo.png";

export default function Register() {
  const navigate = useNavigate();

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const [form, setForm] = useState({
    email: "",
    password: "",
    confirmPassword: "",
  });

  // const handleSubmit = async (e) => {
  //   e.preventDefault();

  //   setError(null);

  //   if (!form.email.trim()) {
  //     setError("Email is required");
  //     return;
  //   }

  //   if (form.password.length < 6) {
  //     setError("Password must be at least 6 characters");
  //     return;
  //   }

  //   if (form.password !== form.confirmPassword) {
  //     setError("Passwords do not match");
  //     return;
  //   }

  //   setSaving(true);

  //   try {
  //     await register({
  //       email: form.email,
  //       password: form.password,
  //       full_name: form.full_name,
  //     });

  //     setSuccess(true);

  //     setTimeout(() => {
  //       navigate("/");
  //     }, 3000);
  //   } catch (err) {
  //     setError(
  //       err.message || "Registration failed."
  //     );
  //   } finally {
  //     setSaving(false);
  //   }
  // };
  const handleSubmit = async (e) => {
    e.preventDefault();

    setError(null);

    if (!form.email.trim()) {
      setError("Email is required");
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
        email: form.email,
        password: form.password,
        full_name: form.full_name,
      });

      setSuccess(true);

      setTimeout(() => {
        navigate("/");
      }, 3000);
    } catch (err) {
      setError(
        err.message || "Registration failed."
      );
    } finally {
      setSaving(false);
    }
  };

  if (success) {
    return (
      <div className="aurora-bg min-h-screen flex items-center justify-center px-6">
        <div className="max-w-md w-full text-center">
          <div className="flex h-16 w-16 mx-auto items-center justify-center rounded-2xl bg-emerald2-500/15 text-emerald2-400 mb-4">
            <CheckCircle2 size={32} />
          </div>

          <h2 className="font-display text-2xl font-bold text-app-primary mb-2">
            Registration Successful!
          </h2>

          <p className="text-app-secondary">
            Your account has been created.
          </p>

          <div className="flex items-center justify-center gap-1 mt-4 text-app-muted text-sm">
            <Loader2
              size={14}
              className="animate-spin"
            />
            Redirecting to login...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="aurora-bg min-h-screen flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 lg:px-12 py-5">
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-3"
        >
          <div className="flex h-10 w-18 items-center justify-center rounded-xl overflow-hidden">
             <img
                src={nusLogo}
                alt="NUS Logo"
                className="h-full w-full object-cover"
            />
          </div>

          <div>
            <p className="font-display font-bold text-app-primary leading-tight text-left">
              NUS DFT
            </p>
            <p className="text-xs text-app-muted">
              AI Student Lifecycle Assistant
            </p>
          </div>
        </button>

        <ThemeToggle />
      </header>

      {/* Form */}
      <main className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-md">
          <div className="rounded-2xl border border-app-soft bg-app-card p-8 shadow-xl">
            <h1 className="font-display text-2xl font-bold text-app-primary mb-2">
              Create Account
            </h1>

            <p className="text-app-muted mb-6">
              Register with your email and password.
            </p>

            {error && (
              <div className="mb-4 flex items-center gap-2 rounded-lg p-3 bg-red-500/10 border border-red-400/20 text-sm text-red-400">
                <AlertCircle size={16} />
                {error}
              </div>
            )}

            <form
              onSubmit={handleSubmit}
              className="space-y-4"
            >
              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">
                  Full Name
                </label>

                <input
                  type="text"
                  className="input"
                  placeholder="John Tan"
                  value={form.full_name}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      full_name: e.target.value,
                    })
                  }
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">
                  Email
                </label>

                <input
                  type="email"
                  className="input"
                  placeholder="you@example.com"
                  value={form.email}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      email: e.target.value,
                    })
                  }
                  required
                />
              </div>

              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">
                  Password
                </label>

                <input
                  type="password"
                  className="input"
                  placeholder="Minimum 6 characters"
                  value={form.password}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      password: e.target.value,
                    })
                  }
                  required
                />
              </div>

              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">
                  Confirm Password
                </label>

                <input
                  type="password"
                  className="input"
                  placeholder="Retype your password"
                  value={form.confirmPassword}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      confirmPassword: e.target.value,
                    })
                  }
                  required
                />
              </div>
              
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => navigate("/")}
                  className="btn-outline flex-1"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="btn-primary flex-1"
                >
                  {saving ? (
                    <>
                      <Loader2
                        size={16}
                        className="animate-spin"
                      />
                      Registering...
                    </>
                  ) : (
                    "Register"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}