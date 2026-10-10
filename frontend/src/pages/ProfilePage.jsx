import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { FileUp, Sparkles } from "lucide-react";
import {
  getConsents,
  getLatestCvImport,
  getProfile,
  getProfileConflicts,
  getProfileDefinitions,
  resolveProfileConflict,
  updateProfile,
} from "../../api";
import { useRole } from "../context/RoleContext";
import { STAGE_LABELS } from "../data/stages";
import { isRecommended } from "../data/onboarding";
import { profilePages } from "../data/profileSections";
import { cn } from "../utils/cn";
import { ErrorBanner, LoadingSpinner, SuccessBanner } from "../components/student/apiWidgets";
import { ProgressBar } from "../components/ui";
import { changedFields, formatFieldValue } from "../components/student/profile/ProfileFields";
import { OverviewPage, SectionPage, filledCount } from "../components/student/profile/ProfilePages";

// The profile, split into pages (data/profileSections.js) under a summary
// card: an overview and one page per topic with its own edit mode. Account,
// preferences and privacy are in the settings dialog. The open page is kept
// in the URL (?page=skills).

function ProfileHeader({ user, stage, subStage, keyDone, keyTotal, onUpdateFromCv }) {
  const completion = keyTotal ? Math.round((keyDone / keyTotal) * 100) : 0;
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  return (
    <section className="group relative mb-6 overflow-hidden rounded-[22px] border border-brand-400/15 bg-gradient-to-br from-white via-white to-brand-50/70 p-5 shadow-[0_14px_40px_rgba(37,99,235,0.08)] transition duration-300 hover:-translate-y-0.5 dark:from-slate-800 dark:via-slate-800 dark:to-indigo-950/60 dark:shadow-[0_16px_45px_rgba(37,99,235,0.16)] sm:p-7">
      <div className="pointer-events-none absolute -right-20 -top-24 h-56 w-56 rounded-full bg-indigo-400/15 blur-3xl transition duration-500 group-hover:bg-indigo-400/25" />
      <div className="pointer-events-none absolute -bottom-28 left-1/3 h-48 w-48 rounded-full bg-blue-400/10 blur-3xl" />
      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center">
        <div className="relative flex h-[76px] w-[76px] flex-shrink-0 items-center justify-center">
          <svg className="absolute inset-0 h-full w-full -rotate-90" viewBox="0 0 76 76" aria-hidden="true">
            <circle cx="38" cy="38" r={radius} fill="none" stroke="currentColor" strokeWidth="4" className="text-slate-200 dark:text-slate-700" />
            <circle cx="38" cy="38" r={radius} fill="none" stroke="url(#profile-ring)" strokeWidth="4" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={circumference - (completion / 100) * circumference} className="transition-all duration-700" />
            <defs><linearGradient id="profile-ring" x1="0" x2="1"><stop stopColor="#2563EB" /><stop offset="1" stopColor="#818CF8" /></linearGradient></defs>
          </svg>
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 font-display text-xl font-bold text-blue-600 dark:text-blue-300">
            {user?.avatar}
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-300">Your profile</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-300"><Sparkles size={11} /> Personalised</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50">Welcome back, {user?.name}</h1>
            {stage && <span className="rounded-full bg-blue-500/10 px-2.5 py-1 text-xs font-semibold text-blue-600 dark:text-blue-300">{STAGE_LABELS[stage] || stage}</span>}
            {subStage && <span className="rounded-full bg-slate-500/10 px-2.5 py-1 text-xs text-slate-600 dark:text-slate-300">{subStage}</span>}
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-300">{user?.email}</p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <div className="h-2 w-44 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700"><div className="h-full rounded-full bg-gradient-to-r from-blue-600 to-indigo-500 transition-all duration-700" style={{ width: `${completion}%` }} /></div>
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">{completion}% complete</span>
            <span className="text-xs text-slate-500 dark:text-slate-400">{keyDone} of {keyTotal} key details</span>
          </div>
        </div>
        <button type="button" className="btn-outline self-start rounded-xl border-slate-300 bg-white/70 px-4 py-2.5 text-sm shadow-sm transition hover:-translate-y-0.5 dark:border-slate-600 dark:bg-slate-800/60" onClick={onUpdateFromCv}>
          <FileUp size={15} /> Update from CV
        </button>
      </div>
    </section>
  );
}

function PageTabs({ pages, current, counts, flagged, onSelect }) {
  return (
    <div className="mb-7 flex max-w-full flex-wrap gap-1.5 rounded-2xl border border-slate-200/80 bg-slate-100/70 p-1.5 dark:border-slate-700 dark:bg-slate-800/70">
      {pages.map((page) => {
        const Icon = page.icon;
        const active = page.key === current;
        return (
          <button
            key={page.key}
            type="button"
            onClick={() => onSelect(page.key)}
            className={cn(
              "inline-flex items-center gap-1.5 whitespace-nowrap rounded-xl border px-3.5 py-2 text-sm font-medium transition duration-200 hover:-translate-y-0.5",
              active
                ? "border-blue-400/30 bg-gradient-to-r from-blue-600 to-indigo-500 text-white shadow-md shadow-blue-500/20"
                : "border-transparent text-slate-600 hover:border-slate-300 hover:bg-white hover:text-slate-900 dark:text-slate-300 dark:hover:border-slate-600 dark:hover:bg-slate-700 dark:hover:text-white",
            )}
          >
            <Icon size={14} />
            {page.label}
            {counts[page.key] && <span className={cn("text-xs", active ? "text-brand-300/80" : "text-app-faint")}>{counts[page.key]}</span>}
            {flagged.has(page.key) && <span className="h-1.5 w-1.5 rounded-full bg-amber-400" aria-label="Needs review" />}
          </button>
        );
      })}
    </div>
  );
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const { user } = useRole();
  const [searchParams, setSearchParams] = useSearchParams();
  const [definitions, setDefinitions] = useState([]);
  const [roleTags, setRoleTags] = useState({});
  const [profile, setProfile] = useState(null);
  const [consents, setConsents] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [cvImport, setCvImport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    Promise.all([getProfileDefinitions(), getProfile(), getConsents(), getProfileConflicts(), getLatestCvImport()])
      .then(([defs, prof, cons, confl, cv]) => {
        setDefinitions(defs.fields);
        setRoleTags(defs.role_tags || {});
        setProfile(prof);
        setConsents(cons);
        setConflicts(confl);
        setCvImport(cv);
      })
      .catch((err) => setError(err.message || "Unable to load your profile."))
      .finally(() => setLoading(false));
  }, []);

  const fields = useMemo(() => profile?.fields || {}, [profile]);
  const stage = fields.lifecycle_stage?.value;
  const definitionsByKey = useMemo(() => Object.fromEntries(definitions.map((d) => [d.field_key, d])), [definitions]);
  const pages = useMemo(() => profilePages(stage, definitions, fields), [stage, definitions, fields]);

  const requested = searchParams.get("page");
  const current = pages.find((p) => p.key === requested) || pages[0];

  const values = Object.fromEntries(Object.entries(fields).map(([k, f]) => [k, f.value]));
  const keyFields = pages.flatMap((p) => (p.cards || []).flatMap((c) => c.fields)).filter((d) => isRecommended(d, values));
  const counts = Object.fromEntries(
    pages.filter((p) => p.cards?.length).map((p) => {
      const pageFields = p.cards.flatMap((c) => c.fields);
      return [p.key, `${filledCount(pageFields, fields)}/${pageFields.length}`];
    }),
  );
  const flagged = new Set(
    pages.filter((p) => p.cards?.some((c) => c.fields.some((d) => conflicts.some((x) => x.field_key === d.field_key)))).map((p) => p.key),
  );

  const flash = (message) => {
    setNotice(message);
    setTimeout(() => setNotice(null), 3000);
  };

  const run = async (fn, successMessage) => {
    setSaving(true);
    setError(null);
    try {
      await fn();
      if (successMessage) flash(successMessage);
    } catch (err) {
      setError(err.message || "Request failed.");
    } finally {
      setSaving(false);
    }
  };

  const openPage = (key) => {
    if (!key || key === current?.key) return;
    if (editing && !window.confirm("Discard your unsaved changes on this page?")) return;
    setEditing(false);
    setSearchParams(key === "overview" ? {} : { page: key });
  };

  const startEdit = () => {
    setDraft(values);
    setEditing(true);
    setError(null);
  };

  const save = () => {
    const pageKeys = new Set(current.cards.filter((c) => !c.readOnly).flatMap((c) => c.fields.map((d) => d.field_key)));
    const changes = Object.fromEntries(Object.entries(changedFields(fields, draft)).filter(([k]) => pageKeys.has(k)));
    if (!Object.keys(changes).length) {
      setEditing(false);
      return;
    }
    run(async () => {
      setProfile(await updateProfile(changes));
      setConflicts(await getProfileConflicts());
      setEditing(false);
    }, `${current.label} saved.`);
  };

  const resolve = (id, action) =>
    run(async () => {
      setProfile(await resolveProfileConflict(id, action));
      setConflicts(await getProfileConflicts());
    }, "Updated.");

  const updateFromCv = () => navigate("/app", { state: { openCvImport: true } });

  if (loading) return <LoadingSpinner label="Loading profile..." />;

  const subStageDefinition = definitionsByKey.sub_stage;
  const subStage = fields.sub_stage?.value && subStageDefinition
    ? formatFieldValue(subStageDefinition, fields.sub_stage.value, roleTags)
    : null;

  return (
    <div className="mx-auto max-w-7xl animate-fadeIn px-1 pb-8">
      <ProfileHeader user={user} stage={stage} subStage={subStage}
        keyDone={filledCount(keyFields, fields)} keyTotal={keyFields.length} onUpdateFromCv={updateFromCv} />

      <PageTabs pages={pages} current={current?.key} counts={counts} flagged={flagged} onSelect={openPage} />

      <ErrorBanner error={error} />
      {notice && <SuccessBanner>{notice}</SuccessBanner>}

      {current?.key === "overview" && (
        <OverviewPage pages={pages} profileFields={fields} conflicts={conflicts} cvImport={cvImport}
          consents={consents} onOpenPage={openPage} onUpdateFromCv={updateFromCv}
          onOpenPrivacy={() => setSearchParams((params) => {
            const next = new URLSearchParams(params);
            next.set("settings", "privacy");
            return next;
          })} />
      )}
      {current?.cards?.length > 0 && (
        <SectionPage
          page={current}
          profileFields={fields}
          definitionsByKey={definitionsByKey}
          roleTags={roleTags}
          conflicts={conflicts}
          editing={editing}
          draft={draft}
          setDraft={setDraft}
          onEdit={startEdit}
          onCancel={() => setEditing(false)}
          onSave={save}
          onResolve={resolve}
          busy={saving}
        />
      )}
    </div>
  );
}
