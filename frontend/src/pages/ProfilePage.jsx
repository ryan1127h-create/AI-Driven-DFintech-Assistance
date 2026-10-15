import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { FileUp } from "lucide-react";
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
  return (
    <div className="card mb-5 flex flex-wrap items-center gap-5 p-6">
      <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl border border-brand-400/20 bg-gradient-to-br from-brand-500/20 to-royal-600/20 font-display text-xl font-bold text-brand-300">
        {user?.avatar}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-display text-xl font-bold text-app-primary">{user?.name}</h1>
          {stage && <span className="chip bg-brand-500/10 text-brand-300">{STAGE_LABELS[stage] || stage}</span>}
          {subStage && <span className="chip bg-app-hover text-app-muted">{subStage}</span>}
        </div>
        <p className="mt-0.5 truncate text-xs text-app-muted">{user?.email}</p>
        {keyTotal > 0 && (
          <div className="mt-3 flex items-center gap-3">
            <ProgressBar value={keyDone} max={keyTotal} className="w-32 sm:w-44" />
            <span className="whitespace-nowrap text-xs text-app-secondary">{keyDone} of {keyTotal} key details</span>
          </div>
        )}
      </div>
      <button type="button" className="btn-outline" onClick={onUpdateFromCv}>
        <FileUp size={15} /> Update from CV
      </button>
    </div>
  );
}

function PageTabs({ pages, current, counts, flagged, onSelect }) {
  return (
    <div className="mb-6 flex flex-wrap gap-2">
      {pages.map((page) => {
        const Icon = page.icon;
        const active = page.key === current;
        return (
          <button
            key={page.key}
            type="button"
            onClick={() => onSelect(page.key)}
            className={cn(
              "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-3.5 py-1.5 text-sm transition",
              active
                ? "border-brand-400/40 bg-brand-500/15 text-brand-300"
                : "border-app-subtle text-app-secondary hover:border-brand-400/30 hover:text-app-primary",
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
  const [refOptions, setRefOptions] = useState({});
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
        setRefOptions(defs.ref_options || {});
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
    ? formatFieldValue(subStageDefinition, fields.sub_stage.value, refOptions)
    : null;

  return (
    <div className="mx-auto max-w-4xl animate-fadeIn">
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
          refOptions={refOptions}
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
