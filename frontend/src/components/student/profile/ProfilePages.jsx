import { AlertTriangle, ChevronRight, FileText, FileUp, Lock, Pencil, Plus, Sparkles } from "lucide-react";
import { formatDate, formatDateTime } from "../../../utils/format";
import { isRecommended } from "../../../data/onboarding";
import { ProgressBar } from "../../ui";
import QuestionField from "../onboarding/QuestionField";
import { SourceBadge, formatFieldValue, isEmptyValue } from "./ProfileFields";

// The pages of the profile page (see pages/ProfilePage.jsx): one page of
// field cards with its own edit mode, and the overview.

export function filledCount(fields, profileFields) {
  return fields.filter((d) => !isEmptyValue(profileFields[d.field_key]?.value)).length;
}

function ValueView({ definition, value, roleTags }) {
  if (Array.isArray(value) && definition.field_key !== "admission_tests" && definition.field_key !== "application_record") {
    return (
      <div className="flex flex-wrap gap-1.5">
        {value.map((item, i) => (
          <span key={i} className="rounded-md border border-app-subtle bg-app-hover px-2 py-0.5 text-xs text-app-primary">
            {formatFieldValue(definition, [item], roleTags)}
          </span>
        ))}
      </div>
    );
  }
  return <span className="text-sm text-app-primary">{formatFieldValue(definition, value, roleTags)}</span>;
}

function ConflictInline({ conflict, definition, roleTags, onResolve, busy }) {
  return (
    <div className="mt-2 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs">
      <p className="flex items-start gap-1.5 text-amber-300">
        <AlertTriangle size={13} className="mt-px flex-shrink-0" />
        <span>
          Your {conflict.candidate_source === "CV" ? "CV" : "records"} say{" "}
          <span className="font-medium">{formatFieldValue(definition, conflict.candidate_value, roleTags)}</span>
        </span>
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <button type="button" className="btn-outline px-2.5 py-1 text-xs" disabled={busy}
          onClick={() => onResolve(conflict.id, "keep_current")}>Keep mine</button>
        <button type="button" className="btn-outline px-2.5 py-1 text-xs" disabled={busy}
          onClick={() => onResolve(conflict.id, "accept_candidate")}>
          Use {conflict.candidate_source === "CV" ? "CV" : "new value"}
        </button>
        <button type="button" className="btn-ghost px-2.5 py-1 text-xs" disabled={busy}
          onClick={() => onResolve(conflict.id, "dismiss")}>Dismiss</button>
      </div>
    </div>
  );
}

function FieldView({ definition, field, conflict, roleTags, onAdd, onResolve, busy, stageValues }) {
  const hasValue = field && !isEmptyValue(field.value);
  const locked = field ? !field.editable : !definition.editable;
  const lockedReason = field ? field.locked_reason : definition.locked_reason;
  return (
    <div className="group grid grid-cols-1 gap-2 border-b border-slate-200/80 py-5 last:border-b-0 dark:border-slate-700 sm:grid-cols-[minmax(0,220px)_minmax(0,1fr)] sm:gap-6">
      <div className="text-sm font-medium text-slate-500 transition group-hover:text-blue-600 dark:text-slate-400 dark:group-hover:text-blue-300">
        {definition.label}
        {isRecommended(definition, stageValues) && <span className="chip ml-1.5 bg-brand-500/10 text-[10px] text-brand-300">Key</span>}
      </div>
      <div className="min-w-0 rounded-xl bg-slate-50/70 px-3 py-2.5 dark:bg-slate-900/30">
        {hasValue ? (
          <>
            <ValueView definition={definition} value={field.value} roleTags={roleTags} />
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-app-faint">
              <SourceBadge source={field.source} />
              {field.updated_at && <span>Updated {formatDate(field.updated_at)}</span>}
              {locked && lockedReason && <span className="inline-flex items-center gap-1"><Lock size={10} /> {lockedReason}</span>}
            </div>
            {field.cv_quote && (
              <p className="mt-1 flex items-start gap-1 text-xs italic text-app-faint">
                <FileText size={11} className="mt-0.5 flex-shrink-0" /> &ldquo;{field.cv_quote}&rdquo;
              </p>
            )}
          </>
        ) : locked ? (
          <span className="inline-flex items-center gap-1.5 text-sm text-app-faint">
            Not on file {lockedReason && <span className="inline-flex items-center gap-1 text-[11px]"><Lock size={10} /> {lockedReason}</span>}
          </span>
        ) : (
          <button type="button" onClick={onAdd}
            className="inline-flex items-center gap-1 rounded-md border border-dashed border-app-input px-2 py-0.5 text-xs text-app-muted transition hover:border-brand-400/40 hover:text-brand-300">
            <Plus size={12} /> Add
          </button>
        )}
        {conflict && (
          <ConflictInline conflict={conflict} definition={definition} roleTags={roleTags} onResolve={onResolve} busy={busy} />
        )}
      </div>
    </div>
  );
}

export function SectionPage({
  page, profileFields, definitionsByKey, roleTags, conflicts, editing, draft, setDraft,
  onEdit, onCancel, onSave, onResolve, busy,
}) {
  const stageValues = Object.fromEntries(Object.entries(profileFields).map(([k, f]) => [k, f.value]));
  const conflictFor = (key) => conflicts.find((c) => c.field_key === key);
  const editable = (d) => (profileFields[d.field_key] ? profileFields[d.field_key].editable : d.editable);
  const Icon = page.icon;

  return (
    <div className="animate-fadeIn">
      <div className="relative mb-6 overflow-hidden rounded-[20px] border border-blue-200/70 bg-gradient-to-br from-blue-50 via-white to-indigo-50/70 p-5 shadow-[0_10px_30px_rgba(37,99,235,0.06)] dark:border-blue-500/20 dark:from-blue-950/50 dark:via-slate-800 dark:to-indigo-950/50 sm:p-6">
        <div className="pointer-events-none absolute -right-12 -top-16 h-40 w-40 rounded-full bg-blue-400/15 blur-3xl" />
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-600 dark:text-blue-300"><Icon size={21} /></div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-300">Profile section</p>
              <h2 className="mt-0.5 font-display text-xl font-bold tracking-tight text-slate-900 dark:text-slate-50">{page.label}</h2>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden w-28 sm:block"><ProgressBar value={filledCount(page.cards.flatMap((card) => card.fields), profileFields)} max={page.cards.flatMap((card) => card.fields).length || 1} color="adaptive" /></div>
            <span className="rounded-full bg-white/70 px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-sm dark:bg-slate-900/40 dark:text-slate-300">
              {filledCount(page.cards.flatMap((card) => card.fields), profileFields)}/{page.cards.flatMap((card) => card.fields).length} complete
            </span>
          </div>
        </div>
        <p className="relative mt-4 max-w-2xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">Keep this section current to get more relevant guidance from your lifecycle assistant.</p>
        {!editing && page.cards.some((c) => !c.readOnly && c.fields.some(editable)) && (
          <button type="button" className="btn-primary relative mt-4 rounded-xl px-4 py-2.5 text-sm shadow-lg shadow-blue-500/15" onClick={onEdit}><Pencil size={14} /> Edit {page.label}</button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-5">
        {page.cards.map((card) => (
          <div key={card.title} className="rounded-[20px] border border-slate-200/80 bg-white/90 px-5 pt-5 pb-2 shadow-[0_10px_30px_rgba(15,23,42,0.04)] transition duration-300 hover:-translate-y-0.5 dark:border-slate-700 dark:bg-slate-800/85 dark:shadow-[0_14px_35px_rgba(2,6,23,0.2)]">
            <p className="flex items-center gap-2 text-base font-bold text-slate-900 dark:text-slate-50">
              {card.title}
              {card.readOnly && <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-[10px] font-medium text-slate-500 dark:bg-slate-700 dark:text-slate-300"><Lock size={11} /> Read only</span>}
            </p>
            <div className="mt-2">
              {card.fields.map((definition) =>
                editing && !card.readOnly && editable(definition) ? (
                  <div key={definition.field_key} className="py-4">
                    <QuestionField
                      definition={definition}
                      definitions={definitionsByKey}
                      value={draft[definition.field_key]}
                      answers={draft}
                      roleTags={roleTags}
                      recommended={isRecommended(definition, draft)}
                      onChange={(value) => setDraft((prev) => ({ ...prev, [definition.field_key]: value }))}
                    />
                  </div>
                ) : (
                  <FieldView
                    key={definition.field_key}
                    definition={definition}
                    field={profileFields[definition.field_key]}
                    conflict={editing ? null : conflictFor(definition.field_key)}
                    roleTags={roleTags}
                    stageValues={stageValues}
                    onAdd={onEdit}
                    onResolve={onResolve}
                    busy={busy}
                  />
                ),
              )}
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <div className="sticky bottom-0 -mx-6 mt-6 flex items-center justify-end gap-2 border-t border-app-subtle px-6 py-4 glass lg:-mx-10 lg:px-10">
          <button type="button" className="btn-ghost" disabled={busy} onClick={onCancel}>Cancel</button>
          <button type="button" className="btn-primary" disabled={busy} onClick={onSave}>
            {busy ? "Saving..." : `Save ${page.label.toLowerCase()}`}
          </button>
        </div>
      )}
    </div>
  );
}

export function OverviewPage({ pages, profileFields, conflicts, cvImport, consents, onOpenPage, onOpenPrivacy, onUpdateFromCv }) {
  const contentPages = pages.filter((p) => p.cards?.length);
  const conflictPage = (key) => contentPages.find((p) => p.cards.some((c) => c.fields.some((d) => d.field_key === key)));
  const personalised = consents.some((c) => c.key === "consent_personalized_rec" && c.granted);
  const keptFromCv = (cvImport?.fields || []).filter((f) => profileFields[f.field_key]?.source === "CV").length;

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="rounded-[20px] border border-slate-200/80 bg-white/90 p-5 shadow-[0_10px_30px_rgba(15,23,42,0.05)] dark:border-slate-700 dark:bg-slate-800/85 dark:shadow-[0_14px_35px_rgba(2,6,23,0.22)] sm:p-6">
        <div className="mb-4 flex items-end justify-between gap-3">
          <div>
            <p className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-50">Your pages</p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Build a stronger profile one section at a time.</p>
          </div>
          <span className="hidden rounded-full bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-600 dark:text-blue-300 sm:inline-flex">{contentPages.length} sections</span>
        </div>
        <div className="divide-y divide-slate-200/80 dark:divide-slate-700">
          {contentPages.map((page) => {
            const fields = page.cards.flatMap((c) => c.fields);
            const filled = filledCount(fields, profileFields);
            const Icon = page.icon;
            const percentage = fields.length ? Math.round((filled / fields.length) * 100) : 0;
            return (
              <button key={page.key} type="button" onClick={() => onOpenPage(page.key)}
                className="group flex w-full items-center gap-3 rounded-xl px-2 py-4 text-left transition duration-200 hover:bg-slate-50 dark:hover:bg-slate-700/45">
                <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-blue-500/10 text-blue-600 transition group-hover:scale-105 dark:text-blue-300"><Icon size={16} /></span>
                <span className="min-w-0 flex-1"><span className="block text-sm font-semibold text-slate-800 dark:text-slate-100">{page.label}</span><span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">{percentage === 100 ? "Complete" : `${fields.length - filled} details remaining`}</span></span>
                <span className="hidden w-36 items-center gap-2 sm:flex"><ProgressBar value={filled} max={fields.length || 1} color="adaptive" /><span className="w-9 text-right text-xs font-semibold text-slate-500 dark:text-slate-400">{percentage}%</span></span>
                <span className="w-12 text-right text-xs font-semibold text-slate-500 dark:text-slate-400">{filled}/{fields.length}</span>
                <ChevronRight size={16} className="text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-blue-500" />
              </button>
            );
          })}
        </div>
      </div>

      {conflicts.length > 0 && (
        <div className="rounded-[20px] border border-amber-300/40 bg-amber-50/80 px-5 py-5 shadow-sm dark:border-amber-500/25 dark:bg-amber-950/20">
          <p className="flex items-center gap-2 text-sm font-semibold text-app-primary">
            <AlertTriangle size={15} className="text-amber-300" /> Needs your review
          </p>
          <div className="mt-2 divide-y divide-app-subtle">
            {conflicts.map((c) => (
              <div key={c.id} className="flex items-center justify-between gap-3 py-3 text-sm">
                <span className="text-app-secondary">
                  <span className="text-app-primary">{c.label || c.field_key}</span>: your {c.candidate_source === "CV" ? "CV" : "records"} differ from what you told us
                </span>
                <button type="button" className="btn-outline px-3 py-1 text-xs" onClick={() => onOpenPage(conflictPage(c.field_key)?.key)}>
                  Review
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-12">
        <div className="rounded-[20px] border border-slate-200/80 bg-white/90 px-5 py-5 shadow-[0_10px_30px_rgba(15,23,42,0.04)] transition duration-300 hover:-translate-y-0.5 dark:border-slate-700 dark:bg-slate-800/85 lg:col-span-5">
          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-300"><FileUp size={18} /></div>
          <p className="text-base font-bold text-slate-900 dark:text-slate-50">Latest CV import</p>
          {cvImport?.parse_status === "parsed" ? (
            <p className="mt-1.5 text-xs text-app-muted">
              {formatDateTime(cvImport.parsed_at || cvImport.uploaded_at)} · {cvImport.fields.length} details found
              {keptFromCv > 0 && `, ${keptFromCv} on your profile`}
            </p>
          ) : (
            <p className="mt-1.5 text-xs text-app-muted">No CV yet. Upload one to fill in your profile faster.</p>
          )}
          <button type="button" className="btn-ghost mt-2 -ml-3 text-xs" onClick={onUpdateFromCv}>
            <FileUp size={13} /> Update from CV
          </button>
        </div>
        <div className="rounded-[20px] border border-indigo-200/70 bg-gradient-to-br from-indigo-50/80 via-white to-blue-50/70 px-5 py-5 shadow-[0_10px_30px_rgba(79,70,229,0.08)] transition duration-300 hover:-translate-y-0.5 dark:border-indigo-500/20 dark:from-indigo-950/50 dark:via-slate-800 dark:to-blue-950/40 lg:col-span-7">
          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-300"><Sparkles size={18} /></div>
          <p className="text-base font-bold text-slate-900 dark:text-slate-50">What the assistant can use</p>
          <p className="mt-1.5 text-xs text-app-muted">
            {personalised
              ? "Your goals, background and skills shape course and career advice, because you allowed personalised recommendations."
              : "Only your lifecycle stage. Allow personalised recommendations to get advice based on your profile."}
          </p>
          <button type="button" className="btn-ghost mt-2 -ml-3 text-xs" onClick={onOpenPrivacy}>
            Privacy settings <ChevronRight size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}
