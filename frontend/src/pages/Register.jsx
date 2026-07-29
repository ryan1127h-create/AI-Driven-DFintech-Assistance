import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  GraduationCap, ArrowRight, ArrowLeft, CheckCircle2, User,
  Briefcase, Globe, Cpu, DollarSign, Target, BookOpen, Sparkles,
  Loader2, AlertCircle, Plus, X,
} from "lucide-react";
// import { supabase } from "../lib/supabase";
import { useRole } from "../context/RoleContext";
import ThemeToggle from "../components/ThemeToggle";
import { cn } from "../utils/cn";

const steps = [
  { id: 0, label: "Personal", icon: User },
  { id: 1, label: "Academic", icon: GraduationCap },
  { id: 2, label: "Work", icon: Briefcase },
  { id: 3, label: "Location", icon: Globe },
  { id: 4, label: "Technical", icon: Cpu },
  { id: 5, label: "Finance", icon: DollarSign },
  { id: 6, label: "Goals", icon: Target },
  { id: 7, label: "Preferences", icon: BookOpen },
  { id: 8, label: "Review", icon: CheckCircle2 },
];

const proficiencyOptions = ["beginner", "intermediate", "advanced"];
const financeOptions = ["none", "basic", "intermediate", "advanced"];
const learningStyles = ["visual", "auditory", "reading", "kinesthetic", "mixed"];
const lifecycleStages = ["prospective", "applicant", "admitted", "enrolled", "graduating", "alumni"];
const commonTechSkills = ["Python", "R", "SQL", "Java", "JavaScript", "C++", "TensorFlow", "PyTorch", "AWS", "Docker", "Git", "Tableau", "Power BI", "Excel VBA", "Solidity", "React"];
const commonFinanceAreas = ["Banking", "Investments", "Risk Management", "Insurance", "Payments", "Blockchain/DeFi", "RegTech", "Trading", "Corporate Finance", "Personal Finance"];
const commonJobRoles = ["FinTech Product Manager", "Quantitative Analyst", "Blockchain Engineer", "Data Scientist (Finance)", "Risk Technology Lead", "Digital Banking Strategist", "RegTech Consultant", "Founder/Startup", "Further PhD Study"];

export default function Register() {
  const navigate = useNavigate();
  const { loginAs } = useRole();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const [form, setForm] = useState({
    full_name: "",
    email: "",
    academic_background: "",
    academic_institution: "",
    work_experience_years: 0,
    work_experience_summary: "",
    country_region: "",
    technical_proficiency: "beginner",
    technical_skills: [],
    finance_knowledge: "none",
    finance_areas: [],
    target_job_roles: [],
    preferred_learning_style: "mixed",
    lifecycle_stage: "prospective",
    application_progress: 0,
    additional_notes: "",
  });

  const [customSkill, setCustomSkill] = useState("");
  const [customFinance, setCustomFinance] = useState("");
  const [customRole, setCustomRole] = useState("");

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const toggleArrayItem = (key, item) => {
    setForm((prev) => {
      const arr = prev[key];
      return { ...prev, [key]: arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item] };
    });
  };

  const addCustomItem = (key, value, setter) => {
    if (!value.trim()) return;
    toggleArrayItem(key, value.trim());
    setter("");
  };

  const canProceed = () => {
    if (step === 0) return form.full_name.trim() && form.email.trim();
    return true;
  };

  // const handleSubmit = async () => {
  //   setSaving(true);
  //   setError(null);
  //   try {
  //     const { error: insertError } = await supabase.from("user_profiles").insert(form);
  //     if (insertError) throw insertError;
  //     setSuccess(true);
  //     setTimeout(() => {
  //       loginAs("prospective");
  //       navigate("/app");
  //     }, 1500);
  //   } catch (err) {
  //     setError(err.message || "Failed to save profile. Please try again.");
  //   } finally {
  //     setSaving(false);
  //   }
  // };

  if (success) {
    return (
      <div className="aurora-bg min-h-screen flex items-center justify-center px-6">
        <div className="max-w-md w-full text-center animate-fadeIn">
          <div className="flex h-16 w-16 mx-auto items-center justify-center rounded-2xl bg-emerald2-500/15 text-emerald2-400 mb-4">
            <CheckCircle2 size={32} />
          </div>
          <h2 className="font-display text-2xl font-bold text-app-primary mb-2">Profile Saved!</h2>
          <p className="text-app-secondary">Your profile has been registered. The AI assistant will use it to provide personalised guidance.</p>
          <div className="flex items-center justify-center gap-1 mt-4 text-app-muted text-sm">
            <Loader2 size={14} className="animate-spin" />
            Redirecting to your assistant...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="aurora-bg min-h-screen flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 lg:px-12 py-5">
        <button onClick={() => navigate("/")} className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-royal-600 text-app-primary shadow-glow">
            <GraduationCap size={22} />
          </div>
          <div>
            <p className="font-display font-bold text-app-primary leading-tight">NUS DFT</p>
            <p className="text-xs text-app-muted">Profile Registration</p>
          </div>
        </button>
        <ThemeToggle />
      </header>

      {/* Progress bar */}
      <div className="px-6 lg:px-12 pb-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-center gap-1.5">
            {steps.map((s, i) => {
              const SIcon = s.icon;
              return (
                <div key={s.id} className="flex items-center flex-1">
                  <div
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-lg text-xs font-medium transition-all flex-shrink-0",
                      i < step && "bg-emerald2-500 text-app-primary",
                      i === step && "bg-brand-500 text-app-primary ring-2 ring-brand-400/30",
                      i > step && "bg-app-hover text-app-faint",
                    )}
                  >
                    {i < step ? <CheckCircle2 size={14} /> : <SIcon size={14} />}
                  </div>
                  {i < steps.length - 1 && (
                    <div className={cn("flex-1 h-0.5 mx-1 rounded-full transition", i < step ? "bg-emerald2-500" : "bg-app-hover")} />
                  )}
                </div>
              );
            })}
          </div>
          <p className="text-center text-xs text-app-muted mt-2">
            Step {step + 1} of {steps.length} — {steps[step].label}
          </p>
        </div>
      </div>

      {/* Form */}
      <main className="flex-1 flex items-start justify-center px-6 lg:px-12 py-4 overflow-y-auto">
        <div className="max-w-2xl w-full">
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-lg p-3 bg-red-500/10 border border-red-400/20 text-sm text-red-400">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          {/* Step 0: Personal */}
          {step === 0 && (
            <div className="space-y-4 animate-fadeIn">
              <h2 className="font-display text-xl font-bold text-app-primary">Personal Information</h2>
              <p className="text-sm text-app-muted">Tell us about yourself so we can personalise your experience.</p>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">Full Name *</label>
                <input
                  value={form.full_name}
                  onChange={(e) => update("full_name", e.target.value)}
                  placeholder="e.g. Wei Jie Tan"
                  className="input"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">Email *</label>
                <input
                  type="email"
                  value={form.email}
                  onChange={(e) => update("email", e.target.value)}
                  placeholder="e.g. weijie.tan@example.com"
                  className="input"
                />
              </div>
            </div>
          )}

          {/* Step 1: Academic */}
          {step === 1 && (
            <div className="space-y-4 animate-fadeIn">
              <h2 className="font-display text-xl font-bold text-app-primary">Academic Background</h2>
              <p className="text-sm text-app-muted">Your highest qualification and field of study.</p>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">Highest Qualification & Field</label>
                <input
                  value={form.academic_background}
                  onChange={(e) => update("academic_background", e.target.value)}
                  placeholder="e.g. BSc in Finance, BEng in Computer Engineering"
                  className="input"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">Institution</label>
                <input
                  value={form.academic_institution}
                  onChange={(e) => update("academic_institution", e.target.value)}
                  placeholder="e.g. National University of Singapore"
                  className="input"
                />
              </div>
            </div>
          )}

          {/* Step 2: Work */}
          {step === 2 && (
            <div className="space-y-4 animate-fadeIn">
              <h2 className="font-display text-xl font-bold text-app-primary">Work Experience</h2>
              <p className="text-sm text-app-muted">Your professional background helps us assess programme fit.</p>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">Years of Experience: {form.work_experience_years} years</label>
                <input
                  type="range"
                  min="0"
                  max="30"
                  value={form.work_experience_years}
                  onChange={(e) => update("work_experience_years", parseInt(e.target.value))}
                  className="w-full accent-brand-500"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">Work Summary</label>
                <textarea
                  value={form.work_experience_summary}
                  onChange={(e) => update("work_experience_summary", e.target.value)}
                  placeholder="Briefly describe your roles, industry, and key achievements..."
                  rows={4}
                  className="input resize-none"
                />
              </div>
            </div>
          )}

          {/* Step 3: Location */}
          {step === 3 && (
            <div className="space-y-4 animate-fadeIn">
              <h2 className="font-display text-xl font-bold text-app-primary">Country / Region</h2>
              <p className="text-sm text-app-muted">Your location affects eligibility, scholarships, and housing options.</p>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">Country / Region</label>
                <select
                  value={form.country_region}
                  onChange={(e) => update("country_region", e.target.value)}
                  className="input"
                >
                  <option value="">Select your country / region</option>
                  {["Singapore", "Malaysia", "India", "China", "Indonesia", "Vietnam", "Thailand", "Japan", "South Korea", "United Kingdom", "United States", "Australia", "Germany", "France", "Other"].map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* Step 4: Technical */}
          {step === 4 && (
            <div className="space-y-4 animate-fadeIn">
              <h2 className="font-display text-xl font-bold text-app-primary">Technical Proficiency</h2>
              <p className="text-sm text-app-muted">Rate your programming and technology skills.</p>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-2 block">Overall Proficiency Level</label>
                <div className="grid grid-cols-3 gap-2">
                  {proficiencyOptions.map((p) => (
                    <button
                      key={p}
                      onClick={() => update("technical_proficiency", p)}
                      className={cn(
                        "rounded-lg p-3 text-sm font-medium capitalize transition border",
                        form.technical_proficiency === p
                          ? "bg-brand-500/15 text-brand-300 border-brand-400/30"
                          : "bg-app-hover text-app-secondary border-app-soft hover:border-brand-400/20",
                      )}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-2 block">Technical Skills</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {commonTechSkills.map((s) => (
                    <button
                      key={s}
                      onClick={() => toggleArrayItem("technical_skills", s)}
                      className={cn(
                        "chip border transition text-xs",
                        form.technical_skills.includes(s)
                          ? "border-brand-400/30 text-brand-300 bg-brand-500/10"
                          : "border-app-input text-app-secondary hover:border-brand-400/30",
                      )}
                    >
                      {form.technical_skills.includes(s) && <X size={11} className="inline mr-1" />}
                      {s}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    value={customSkill}
                    onChange={(e) => setCustomSkill(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomItem("technical_skills", customSkill, setCustomSkill))}
                    placeholder="Add custom skill..."
                    className="input flex-1 text-sm"
                  />
                  <button onClick={() => addCustomItem("technical_skills", customSkill, setCustomSkill)} className="btn-outline text-xs">
                    <Plus size={14} /> Add
                  </button>
                </div>
                {form.technical_skills.filter((s) => !commonTechSkills.includes(s)).length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {form.technical_skills.filter((s) => !commonTechSkills.includes(s)).map((s) => (
                      <span key={s} className="chip border border-brand-400/30 text-brand-300 bg-brand-500/10 text-xs">
                        {s} <X size={11} className="inline ml-1 cursor-pointer" onClick={() => toggleArrayItem("technical_skills", s)} />
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Step 5: Finance */}
          {step === 5 && (
            <div className="space-y-4 animate-fadeIn">
              <h2 className="font-display text-xl font-bold text-app-primary">Finance Knowledge</h2>
              <p className="text-sm text-app-muted">Your understanding of finance concepts and domains.</p>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-2 block">Finance Knowledge Level</label>
                <div className="grid grid-cols-4 gap-2">
                  {financeOptions.map((p) => (
                    <button
                      key={p}
                      onClick={() => update("finance_knowledge", p)}
                      className={cn(
                        "rounded-lg p-3 text-sm font-medium capitalize transition border",
                        form.finance_knowledge === p
                          ? "bg-brand-500/15 text-brand-300 border-brand-400/30"
                          : "bg-app-hover text-app-secondary border-app-soft hover:border-brand-400/20",
                      )}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-2 block">Finance Areas of Experience</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {commonFinanceAreas.map((s) => (
                    <button
                      key={s}
                      onClick={() => toggleArrayItem("finance_areas", s)}
                      className={cn(
                        "chip border transition text-xs",
                        form.finance_areas.includes(s)
                          ? "border-brand-400/30 text-brand-300 bg-brand-500/10"
                          : "border-app-input text-app-secondary hover:border-brand-400/30",
                      )}
                    >
                      {form.finance_areas.includes(s) && <X size={11} className="inline mr-1" />}
                      {s}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    value={customFinance}
                    onChange={(e) => setCustomFinance(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomItem("finance_areas", customFinance, setCustomFinance))}
                    placeholder="Add custom area..."
                    className="input flex-1 text-sm"
                  />
                  <button onClick={() => addCustomItem("finance_areas", customFinance, setCustomFinance)} className="btn-outline text-xs">
                    <Plus size={14} /> Add
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Step 6: Goals */}
          {step === 6 && (
            <div className="space-y-4 animate-fadeIn">
              <h2 className="font-display text-xl font-bold text-app-primary">Target Job Roles</h2>
              <p className="text-sm text-app-muted">What careers are you targeting after the programme?</p>
              <div>
                <div className="flex flex-wrap gap-2 mb-2">
                  {commonJobRoles.map((s) => (
                    <button
                      key={s}
                      onClick={() => toggleArrayItem("target_job_roles", s)}
                      className={cn(
                        "chip border transition text-xs",
                        form.target_job_roles.includes(s)
                          ? "border-brand-400/30 text-brand-300 bg-brand-500/10"
                          : "border-app-input text-app-secondary hover:border-brand-400/30",
                      )}
                    >
                      {form.target_job_roles.includes(s) && <X size={11} className="inline mr-1" />}
                      {s}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    value={customRole}
                    onChange={(e) => setCustomRole(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomItem("target_job_roles", customRole, setCustomRole))}
                    placeholder="Add custom role..."
                    className="input flex-1 text-sm"
                  />
                  <button onClick={() => addCustomItem("target_job_roles", customRole, setCustomRole)} className="btn-outline text-xs">
                    <Plus size={14} /> Add
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Step 7: Preferences */}
          {step === 7 && (
            <div className="space-y-4 animate-fadeIn">
              <h2 className="font-display text-xl font-bold text-app-primary">Learning Preferences & Journey</h2>
              <p className="text-sm text-app-muted">How you learn best and where you are in your journey.</p>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-2 block">Preferred Learning Style</label>
                <div className="grid grid-cols-5 gap-2">
                  {learningStyles.map((s) => (
                    <button
                      key={s}
                      onClick={() => update("preferred_learning_style", s)}
                      className={cn(
                        "rounded-lg p-3 text-xs font-medium capitalize transition border text-center",
                        form.preferred_learning_style === s
                          ? "bg-brand-500/15 text-brand-300 border-brand-400/30"
                          : "bg-app-hover text-app-secondary border-app-soft hover:border-brand-400/20",
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-2 block">Current Lifecycle Stage</label>
                <select
                  value={form.lifecycle_stage}
                  onChange={(e) => update("lifecycle_stage", e.target.value)}
                  className="input"
                >
                  {lifecycleStages.map((s) => (
                    <option key={s} value={s} className="capitalize">{s}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">Application / Academic Progress: {form.application_progress}%</label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={form.application_progress}
                  onChange={(e) => update("application_progress", parseInt(e.target.value))}
                  className="w-full accent-brand-500"
                />
                <div className="flex justify-between text-[10px] text-app-faint mt-1">
                  <span>Just exploring</span>
                  <span>Applied</span>
                  <span>Enrolled</span>
                  <span>Graduating</span>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-app-secondary mb-1.5 block">Additional Notes</label>
                <textarea
                  value={form.additional_notes}
                  onChange={(e) => update("additional_notes", e.target.value)}
                  placeholder="Anything else you'd like the AI assistant to know..."
                  rows={3}
                  className="input resize-none"
                />
              </div>
            </div>
          )}

          {/* Step 8: Review */}
          {step === 8 && (
            <div className="space-y-4 animate-fadeIn">
              <h2 className="font-display text-xl font-bold text-app-primary">Review Your Profile</h2>
              <p className="text-sm text-app-muted">Please review before submitting. The AI assistant will use this to personalise your experience.</p>

              <div className="space-y-3">
                <ReviewSection title="Personal" icon={User} items={[
                  ["Name", form.full_name],
                  ["Email", form.email],
                ]} />
                <ReviewSection title="Academic" icon={GraduationCap} items={[
                  ["Background", form.academic_background || "Not specified"],
                  ["Institution", form.academic_institution || "Not specified"],
                ]} />
                <ReviewSection title="Work" icon={Briefcase} items={[
                  ["Experience", `${form.work_experience_years} years`],
                  ["Summary", form.work_experience_summary || "Not specified"],
                ]} />
                <ReviewSection title="Location" icon={Globe} items={[
                  ["Country/Region", form.country_region || "Not specified"],
                ]} />
                <ReviewSection title="Technical" icon={Cpu} items={[
                  ["Proficiency", form.technical_proficiency],
                  ["Skills", form.technical_skills.length ? form.technical_skills.join(", ") : "None selected"],
                ]} />
                <ReviewSection title="Finance" icon={DollarSign} items={[
                  ["Knowledge Level", form.finance_knowledge],
                  ["Areas", form.finance_areas.length ? form.finance_areas.join(", ") : "None selected"],
                ]} />
                <ReviewSection title="Goals" icon={Target} items={[
                  ["Target Roles", form.target_job_roles.length ? form.target_job_roles.join(", ") : "None selected"],
                ]} />
                <ReviewSection title="Preferences" icon={BookOpen} items={[
                  ["Learning Style", form.preferred_learning_style],
                  ["Lifecycle Stage", form.lifecycle_stage],
                  ["Progress", `${form.application_progress}%`],
                  ["Notes", form.additional_notes || "None"],
                ]} />
              </div>

              <div className="rounded-lg p-4 bg-brand-500/5 border border-brand-400/10">
                <div className="flex items-center gap-2 mb-1">
                  <Sparkles size={14} className="text-brand-300" />
                  <p className="text-sm font-medium text-app-primary">AI Assessment Preview</p>
                </div>
                <p className="text-xs text-app-muted">
                  Based on your profile, the AI assistant will generate personalised insights about eligibility, track recommendations, and career path alignment.
                </p>
              </div>
            </div>
          )}

          {/* Navigation */}
          <div className="flex items-center justify-between mt-6 pb-8">
            <button
              onClick={() => step > 0 && setStep(step - 1)}
              disabled={step === 0}
              className={cn("btn-ghost text-sm", step === 0 && "opacity-0 pointer-events-none")}
            >
              <ArrowLeft size={16} /> Back
            </button>
            {step < steps.length - 1 ? (
              <button
                onClick={() => canProceed() && setStep(step + 1)}
                disabled={!canProceed()}
                className={cn("btn-primary text-sm", !canProceed() && "opacity-50 cursor-not-allowed")}
              >
                Continue <ArrowRight size={16} />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={saving}
                className="btn-primary text-sm"
              >
                {saving ? <><Loader2 size={16} className="animate-spin" /> Saving...</> : <>Submit Profile <CheckCircle2 size={16} /></>}
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function ReviewSection({ title, icon: Icon, items }) {
  return (
    <div className="rounded-lg p-4 bg-app-hover border border-app-soft">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-brand-300" />
        <p className="text-sm font-semibold text-app-primary">{title}</p>
      </div>
      <div className="space-y-1">
        {items.map(([label, value]) => (
          <div key={label} className="flex items-start gap-2 text-sm">
            <span className="text-app-faint w-28 flex-shrink-0">{label}:</span>
            <span className="text-app-secondary">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
