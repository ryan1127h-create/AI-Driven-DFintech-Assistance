import { Fragment, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Briefcase,
  CalendarClock,
  Check,
  ChevronRight,
  ClipboardList,
  Code2,
  FileUp,
  GraduationCap,
  ListChecks,
  Lock,
  Minus,
  Rocket,
  School,
  SkipForward,
  Sparkles,
  Target,
  UserRound,
} from "lucide-react";
import {
  getConsents,
  getLifecycle,
  getProfile,
  getProfileDefinitions,
  setOnboardingStatus,
  updateConsents,
  updateProfile,
} from "../../../../api";
import { useRole } from "../../../context/RoleContext";
import { isFieldShown, isRecommended, onboardingSteps } from "../../../data/onboarding";
import { cn } from "../../../utils/cn";
import { changedFields, isEmptyValue } from "../profile/ProfileFields";
import { LoadingSpinner } from "../apiWidgets";
import CvImport from "./CvImport";
import QuestionField from "./QuestionField";

// The profile welcome questionnaire shown after the first login: pick how to
// start (CV, questions, or skip), then a few short steps for the user's
// lifecycle stage (see data/onboarding.js). Each step is saved on its own,
// so leaving halfway keeps what was answered. Starting from a CV pre-fills
// the empty fields it covers; saving sends the import's id so unchanged CV
// values are stored as coming from the CV. onDone() is called once the
// user is back to chatting, after onboarding_status has been recorded.
// initialPhase "cv" opens straight on the CV step (the profile page's
// "Update from CV").

const STEP_ICONS = {
  goals: Target,
  goalsStudy: Target,
  education: GraduationCap,
  work: Briefcase,
  background: Briefcase,
  skills: Code2,
  skillsStudy: Code2,
  applying: ClipboardList,
  starting: Rocket,
  record: School,
  studyPlan: CalendarClock,
};

function IconTile({ icon: Icon, className }) {
  return (
    <div className={cn("flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-brand-500/15 text-brand-300", className)}>
      <Icon size={20} />
    </div>
  );
}

function EntryOption({ icon, title, subtitle, badge, highlighted, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group flex w-full items-center gap-4 rounded-xl p-4 text-left transition-all glass-light",
        "hover:border-brand-400/30 hover:bg-brand-500/5",
        highlighted && "border-brand-400/30",
      )}
    >
      <IconTile icon={icon} className="bg-brand-500/10" />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-medium text-app-primary">
          {title}
          {badge && <span className="chip whitespace-nowrap bg-app-hover text-app-muted">{badge}</span>}
        </p>
        <p className="mt-0.5 text-xs text-app-muted">{subtitle}</p>
      </div>
      <ChevronRight size={16} className="flex-shrink-0 text-app-faint transition group-hover:translate-x-0.5 group-hover:text-brand-300" />
    </button>
  );
}

// outcomes[i] is "done" (answered) or "skipped" for steps already left;
// a skipped step gets a dashed outline and a dash instead of a tick.
function Stepper({ steps, index, outcomes }) {
  return (
    <div className="flex items-center">
      {steps.map((step, i) => {
        const current = i === index;
        const done = !current && outcomes[i] === "done";
        const skipped = !current && outcomes[i] === "skipped";
        return (
          <Fragment key={step.key}>
            {i > 0 && <div className={cn("mx-2 h-px flex-1", i <= index ? "bg-brand-400/50" : "bg-app-hover")} />}
            <div className="flex items-center gap-2">
              <span
                title={done ? "Answered" : skipped ? "Skipped" : undefined}
                className={cn(
                  "flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-[11px] font-medium transition",
                  done && "bg-brand-500 text-white",
                  skipped && "border border-dashed border-app-input text-app-muted",
                  current && "bg-brand-500/15 text-brand-300 ring-1 ring-brand-400/50",
                  !done && !skipped && !current && "bg-app-hover text-app-faint",
                )}
              >
                {done ? <Check size={12} /> : skipped ? <Minus size={12} /> : i + 1}
              </span>
              <span className={cn("hidden text-xs lg:inline", current ? "font-medium text-app-primary" : "text-app-muted")}>
                {step.title}
              </span>
            </div>
          </Fragment>
        );
      })}
    </div>
  );
}

function RecordStep() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getLifecycle().then(setData).catch((err) => setError(err.message || "Unable to load your school record."));
  }, []);

  if (error) return <p className="text-sm text-red-300">{error}</p>;
  if (!data) return <LoadingSpinner label="Loading your school record..." />;

  const courses = data.courses || [];
  const count = (status) => courses.filter((c) => c.status === status).length;
  const rows = [
    ["Study mode", data.record?.study_mode],
    ["Specialisation", data.record?.track],
    ["Expected graduation", data.record?.expected_grad_term],
    ["Courses", `${count("current")} in progress · ${count("completed")} completed`],
    ["Units", `${data.progress.total_units_done} / ${data.progress.total_units_target}`],
    ["GPA band", data.record?.gpa_band],
  ].filter(([, value]) => value);

  return (
    <div className="card p-6">
      <p className="text-xs text-app-muted">Programme</p>
      <p className="mt-0.5 font-display text-lg font-semibold text-app-primary">{data.programme?.name || data.programme?.code}</p>
      <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-app-muted">{label}</dt>
            <dd className="mt-0.5 text-sm text-app-primary">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-6 flex items-center gap-1.5 border-t border-app-subtle pt-4 text-xs text-app-muted">
        <Lock size={12} /> From the school&apos;s records. If something is wrong, contact the programme office.
      </p>
    </div>
  );
}

function ConsentCard({ onGrant, saving }) {
  return (
    <label className="mb-4 flex cursor-pointer items-start gap-3 rounded-xl border border-brand-400/20 bg-brand-500/5 p-4">
      <input type="checkbox" className="mt-0.5 accent-brand-500" disabled={saving}
        onChange={(e) => e.target.checked && onGrant()} />
      <span>
        <span className="block text-sm font-medium text-app-primary">Use my answers for personalised recommendations</span>
        <span className="mt-0.5 block text-xs text-app-muted">
          Without this, your answers are saved but not used for course and career advice.
        </span>
      </span>
    </label>
  );
}

function sameValue(a, b) {
  const canonical = (v) => (Array.isArray(v) ? v.map((i) => JSON.stringify(i)).sort() : v);
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
}

export default function OnboardingFlow({ onDone, initialPhase = "entry" }) {
  const { lifecycleStage, user, setCurrentUser } = useRole();
  const steps = useMemo(() => onboardingSteps(lifecycleStage), [lifecycleStage]);
  const [phase, setPhase] = useState(initialPhase);
  const [cvImport, setCvImport] = useState(null);
  const [index, setIndex] = useState(0);
  const [definitions, setDefinitions] = useState(null);
  const [roleTags, setRoleTags] = useState({});
  const [profileFields, setProfileFields] = useState({});
  const [answers, setAnswers] = useState({});
  const [consented, setConsented] = useState(true);
  const [savedCount, setSavedCount] = useState(0);
  const [outcomes, setOutcomes] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getProfileDefinitions(), getProfile(), getConsents()])
      .then(([defs, profile, consents]) => {
        setDefinitions(Object.fromEntries(defs.fields.map((d) => [d.field_key, d])));
        setRoleTags(defs.role_tags || {});
        setProfileFields(profile.fields || {});
        setAnswers(Object.fromEntries(Object.entries(profile.fields || {}).map(([k, f]) => [k, f.value])));
        setConsented(consents.some((c) => c.key === "consent_personalized_rec" && c.granted));
      })
      .catch((err) => setError(err.message || "Unable to load the questionnaire."));
  }, []);

  const step = steps[index];
  // A step's fields that this user may answer: known to the dictionary,
  // editable (not from school records), and shown given earlier answers.
  const visibleFields = (current) =>
    (current.fields || []).filter((key) => {
      const definition = definitions?.[key];
      const field = profileFields[key];
      return definition && (field ? field.editable : definition.editable) && isFieldShown(key, lifecycleStage, answers);
    });

  const finish = async (status) => {
    setSaving(true);
    try {
      if (user?.onboardingStatus !== "completed" || status === "completed") {
        setCurrentUser(await setOnboardingStatus(status));
      }
      if (status === "completed") setPhase("done");
      else onDone();
    } catch (err) {
      setError(err.message || "Unable to save your progress.");
    } finally {
      setSaving(false);
    }
  };

  const goTo = (next) => {
    setIndex(next);
    document.getElementById("onboarding-scroll")?.scrollTo({ top: 0 });
  };

  const advance = async (save) => {
    setError("");
    if (save && !step.record) {
      const keys = new Set(visibleFields(step));
      const changes = Object.fromEntries(
        Object.entries(changedFields(profileFields, answers)).filter(([key]) => keys.has(key)),
      );
      if (Object.keys(changes).length) {
        setSaving(true);
        try {
          const profile = await updateProfile(changes, cvImport?.document_id);
          setProfileFields(profile.fields || {});
          setSavedCount((n) => n + Object.values(changes).filter((v) => !isEmptyValue(v)).length);
        } catch (err) {
          setError(err.message || "Unable to save this step.");
          setSaving(false);
          return;
        }
        setSaving(false);
      }
    }
    // A step left via "Save and continue" with nothing answered counts as
    // skipped too; the school-record step counts as done once confirmed.
    const answered = step.record || visibleFields(step).some((key) => !isEmptyValue(answers[key]));
    setOutcomes((prev) => ({ ...prev, [index]: save && answered ? "done" : "skipped" }));
    if (index < steps.length - 1) goTo(index + 1);
    else finish("completed");
  };

  const grantConsent = async () => {
    setSaving(true);
    try {
      await updateConsents({ consent_personalized_rec: true });
      setConsented(true);
    } catch (err) {
      setError(err.message || "Unable to save your choice.");
    } finally {
      setSaving(false);
    }
  };

  // Continue to the questions with the CV's details filled into the fields
  // that are still empty.
  const startWithCv = (result) => {
    setCvImport(result);
    setAnswers((prev) => ({
      ...prev,
      ...Object.fromEntries((result.fields || []).filter((f) => f.status === "new").map((f) => [f.field_key, f.value])),
    }));
    setPhase("steps");
    goTo(0);
  };
  const cvFields = Object.fromEntries((cvImport?.fields || []).map((f) => [f.field_key, f]));

  const isLast = index === steps.length - 1;
  const fields = step && !step.record ? visibleFields(step) : [];

  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-app-subtle px-5 py-3">
        <div className="flex items-center gap-2">
          <UserRound size={16} className="text-brand-300" />
          <span className="font-display text-sm font-semibold text-app-primary">Profile setup</span>
        </div>
        <div className="flex items-center gap-3">
          {phase === "steps" && (
            <button type="button" onClick={() => finish("skipped")} disabled={saving}
              className="text-xs text-app-muted transition hover:text-app-primary">
              Finish later
            </button>
          )}
        </div>
      </div>

      {!definitions && !error ? (
        <LoadingSpinner label="Loading..." />
      ) : (
        <div id="onboarding-scroll" className="flex-1 overflow-y-auto">
          {phase === "entry" && (
            <div className="mx-auto max-w-2xl px-6 py-12 animate-fadeIn">
              <div className="mb-10 text-center">
                <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-2xl border border-brand-400/20 bg-gradient-to-br from-brand-500/20 to-royal-600/20">
                  <Sparkles size={28} className="text-brand-300" />
                </div>
                <h1 className="font-display text-2xl font-bold text-app-primary lg:text-3xl">
                  Welcome, {user?.name?.split(" ")[0]}
                </h1>
                <p className="mx-auto mt-2 max-w-md text-sm text-app-muted">
                  A few minutes on your profile makes every answer more specific to you. You can change anything later.
                </p>
              </div>
              <div className="space-y-2.5">
                <EntryOption icon={FileUp} title="Fill it from my CV"
                  subtitle="We read your CV and pre-fill the questions for you to check" onClick={() => setPhase("cv")} />
                <EntryOption icon={ListChecks} title="Answer the questions" highlighted
                  subtitle={`${steps.length} short steps, skip any you like`} onClick={() => setPhase("steps")} />
                <EntryOption icon={SkipForward} title="Skip for now"
                  subtitle="You can come back to it from the chat page" onClick={() => finish("skipped")} />
              </div>
              {error && <p className="mt-4 text-center text-sm text-red-300">{error}</p>}
            </div>
          )}

          {phase === "cv" && (
            <div className="mx-auto max-w-2xl px-6 py-10 animate-fadeIn">
              <div className="mb-6 flex items-center gap-3">
                <IconTile icon={FileUp} />
                <div>
                  <h1 className="font-display text-xl font-bold text-app-primary">Fill in from your CV</h1>
                  <p className="mt-0.5 text-sm text-app-muted">You&apos;ll check every detail before it&apos;s saved</p>
                </div>
              </div>
              <CvImport onReady={startWithCv} onBack={() => (initialPhase === "cv" ? onDone() : setPhase("entry"))} />
            </div>
          )}

          {phase === "steps" && step && (
            <div className="mx-auto max-w-3xl px-6 pt-8 animate-fadeIn">
              <Stepper steps={steps} index={index} outcomes={outcomes} />

              <div className="mb-6 mt-8 flex items-center gap-3">
                <IconTile icon={STEP_ICONS[step.key] || Target} />
                <div>
                  <h1 className="font-display text-xl font-bold text-app-primary">{step.title}</h1>
                  <p className="mt-0.5 text-sm text-app-muted">{step.subtitle}</p>
                </div>
              </div>

              {!step.record && !consented && <ConsentCard onGrant={grantConsent} saving={saving} />}

              {step.record ? (
                <RecordStep />
              ) : (
                <div className="card divide-y divide-app-subtle px-6">
                  {fields.map((key) => (
                    <div key={key} className="py-6">
                      <QuestionField
                        definition={definitions[key]}
                        value={answers[key]}
                        answers={answers}
                        roleTags={roleTags}
                        recommended={isRecommended(definitions[key], answers)}
                        cvQuote={cvFields[key] && sameValue(answers[key], cvFields[key].value) ? cvFields[key].quote : null}
                        onChange={(value) => setAnswers((prev) => ({ ...prev, [key]: value }))}
                      />
                    </div>
                  ))}
                </div>
              )}

              {error && <p className="mt-4 text-sm text-red-300">{error}</p>}

              <div className="sticky bottom-0 -mx-6 mt-6 flex items-center justify-between gap-3 border-t border-app-subtle px-6 py-4 glass">
                <button type="button" className="btn-ghost whitespace-nowrap px-2" disabled={saving}
                  onClick={() => (index === 0 ? setPhase("entry") : goTo(index - 1))}>
                  <ArrowLeft size={14} /> Back
                </button>
                <div className="flex items-center gap-2">
                  <span className="mr-2 hidden whitespace-nowrap text-xs text-app-faint lg:inline">Step {index + 1} of {steps.length}</span>
                  {!step.record && (
                    <button type="button" className="btn-ghost whitespace-nowrap" disabled={saving} onClick={() => advance(false)}>
                      <span className="lg:hidden">Skip</span>
                      <span className="hidden lg:inline">Skip this step</span>
                    </button>
                  )}
                  <button type="button" className="btn-primary whitespace-nowrap" disabled={saving} onClick={() => advance(true)}>
                    {saving ? "Saving..." : step.record ? "Looks right" : isLast ? "Finish" : (
                      <>
                        <span className="lg:hidden">Continue</span>
                        <span className="hidden lg:inline">Save and continue</span>
                      </>
                    )}
                    {!saving && !isLast && <ArrowRight size={14} />}
                  </button>
                </div>
              </div>
            </div>
          )}

          {phase === "done" && (
            <div className="mx-auto max-w-md px-6 py-16 text-center animate-fadeIn">
              <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-2xl border border-emerald2-400/20 bg-emerald2-500/15">
                <Check size={28} className="text-emerald2-400" />
              </div>
              <h1 className="font-display text-2xl font-bold text-app-primary">Your profile is set up</h1>
              <p className="mt-2 text-sm text-app-muted">
                {savedCount} {savedCount === 1 ? "answer" : "answers"} saved. You can change any of them on your profile page.
              </p>
              <button type="button" className="btn-primary mx-auto mt-8" onClick={onDone}>
                Start chatting <ArrowRight size={14} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
