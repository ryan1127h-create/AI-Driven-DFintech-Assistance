import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { GraduationCap, ShieldCheck, AlertCircle, Loader2, CheckCircle2, UserPlus } from "lucide-react";
import ThemeToggle from "../components/ThemeToggle";
import { cn } from "../utils/cn";
import nusLogo from "../assets/nus_logo.png";
import {
  getDepartments,
  getStaffRoles,
  registerStaff,
} from "../services/adminService";

export default function AdminRegister() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    employee_no: "",
    department_id: "",
    job_title: "",
    role_id: "",
  });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [departments, setDepartments] = useState([]);
  const [roles, setRoles] = useState([]);

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  useEffect(() => {
    const loadData = async () => {
      try {
        const [deptRes, roleRes] = await Promise.all([
          getDepartments(),
          getStaffRoles(),
        ]);

        setDepartments(deptRes.data);
        setRoles(roleRes.data);
      } catch (err) {
        console.error(err);
      }
    };

    loadData();
    }, []);
  // const handleSubmit = async (e) => {
  //   e.preventDefault();
  //   setError(null);
  //   setLoading(true);
  //   try {
  //     // const { data, error: signUpError } = await supabase.auth.signUp({
  //     //   email: form.email,
  //     //   password: form.password,
  //     // });
  //     if (signUpError) throw signUpError;
  //     const userId = data.user.id;
  //     // const { error: insertError } = await supabase.from("staff_profiles").insert({
  //     //   user_id: userId,
  //     //   full_name: form.full_name,
  //     //   email: form.email,
  //     //   department: form.department,
  //     //   role: "staff",
  //     // });
  //     if (insertError) throw insertError;
  //     setSuccess(true);
  //     setTimeout(() => navigate("/admin"), 1500);
  //   } catch (err) {
  //     setError(err.message || "Failed to register. Please try again.");
  //   } finally {
  //     setLoading(false);
  //   }
  // };
  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      await registerStaff(form);

      setSuccess(true);
      navigate("/admin");
    } catch (err) {
      setError(
        err.response?.data?.message ||
        "Failed to register staff"
      );
    }
  };

  if (success) {
    return (
      <div className="aurora-bg min-h-screen flex items-center justify-center px-6">
        <div className="max-w-md w-full text-center animate-fadeIn">
          <div className="flex h-16 w-16 mx-auto items-center justify-center rounded-2xl bg-emerald2-500/15 text-emerald2-400 mb-4">
            <CheckCircle2 size={32} />
          </div>
          <h2 className="font-display text-2xl font-bold text-app-primary mb-2">Staff Account Created!</h2>
          <p className="text-app-secondary">Redirecting to admin portal...</p>
          <div className="flex items-center justify-center gap-1 mt-4 text-app-muted text-sm">
            <Loader2 size={14} className="animate-spin" />
          </div>
        </div>
      </div>
    );
  }

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
            <p className="text-xs text-app-muted">Staff Registration</p>
          </div>
        </button>
        <ThemeToggle />
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-8">
        <div className="max-w-md w-full">
          <div className="text-center mb-8 animate-fadeIn">
            <div className="flex h-14 w-14 mx-auto items-center justify-center rounded-2xl bg-royal-500/15 text-royal-300 mb-3">
              <ShieldCheck size={28} />
            </div>
            <h1 className="font-display text-2xl font-bold text-app-primary mb-2">Staff Registration</h1>
            <p className="text-sm text-app-muted">Create a staff account for the admin portal</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 rounded-lg p-3 bg-red-500/10 border border-red-400/20 text-sm text-red-400">
                <AlertCircle size={16} />
                {error}
              </div>
            )}
            <div>
              <label className="text-sm font-medium text-app-secondary mb-1.5 block">Full Name *</label>
              <input
                required
                value={form.full_name}
                onChange={(e) => update("full_name", e.target.value)}
                placeholder="e.g. Dr. Lin Wei"
                className="input"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-app-secondary mb-1.5 block">Email *</label>
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                placeholder="you@nus.edu.sg"
                className="input"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-app-secondary mb-1.5 block">Password *</label>
              <input
                type="password"
                required
                minLength={6}
                value={form.password}
                onChange={(e) => update("password", e.target.value)}
                placeholder="At least 6 characters"
                className="input"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-app-secondary mb-1.5 block">
                Employee No *
              </label>
              <input
                required
                value={form.employee_no}
                onChange={(e) => update("employee_no", e.target.value)}
                placeholder="e.g. EMP001"
                className="input"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-app-secondary mb-1.5 block">
                Job Title *
              </label>
              <input
                required
                value={form.job_title}
                onChange={(e) => update("job_title", e.target.value)}
                placeholder="e.g. Career Advisor"
                className="input"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-app-secondary mb-1.5 block">
                Department *
              </label>

              <select
                required
                value={form.department_id}
                onChange={(e) => update("department_id", e.target.value)}
                className="input"
              >
                <option value="">Select Department</option>

                {departments.map((dept) => (
                  <option
                    key={dept.department_id}
                    value={dept.department_id}
                  >
                    {dept.department_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm font-medium text-app-secondary mb-2 block">
                Staff Roles *
              </label>

              <div className="grid grid-cols-2 gap-2">
                {roles.map((role) => (
                  <label
                    key={role.role_id}
                    className="flex items-center gap-2 rounded-lg border border-app-soft p-2"
                  >
                    <input
                      type="radio"
                      name="staff_role"
                      value={role.role_id}
                      checked={form.role_id === role.role_id}
                      onChange={(e) =>
                        update("role_id", e.target.value)
                      }
                    />

                    <span className="text-sm">
                      {role.role_name}
                    </span>
                  </label>
                ))}
              </div>
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
              {loading ? <><Loader2 size={16} className="animate-spin" /> Creating account...</> : <><UserPlus size={16} /> Create Staff Account</>}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-app-muted">
            Already have an account? <Link to="/login" className="text-brand-300 hover:underline">Sign in</Link>
          </div>
          <div className="mt-2 text-center text-sm text-app-muted">
            <Link to="/" className="text-app-faint hover:text-app-secondary">Back to home</Link>
          </div>
        </div>
      </main>
    </div>
  );
}
