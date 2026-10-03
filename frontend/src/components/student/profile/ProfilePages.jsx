import { AlertTriangle, ChevronRight, FileText, FileUp, Lock, Pencil, Plus } from "lucide-react";
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
    <div className="grid grid-cols-1 gap-1.5 py-3.5 sm:grid-cols-[minmax(0,200px)_minmax(0,1fr)] sm:gap-4">
      <div className="text-sm text-app-secondary">
        {definition.label}
        {isRecommended(definition, stageValues) && <span className="chip ml-1.5 bg-brand-500/10 text-[10px] text-brand-300">Key</span>}
      </div>
      <div className="min-w-0">
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
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Icon size={18} className="text-brand-300" />
          <h2 className="font-display text-lg font-semibold text-app-primary">{page.label}</h2>
        </div>
        {!editing && page.cards.some((c) => !c.readOnly && c.fields.some(editable)) && (
          <button type="button" className="btn-outline" onClick={onEdit}><Pencil size={14} /> Edit</button>
        )}
      </div>

      <div className="space-y-4">
        {page.cards.map((card) => (
          <div key={card.title} className="card px-5 pt-4 pb-1">
            <p className="flex items-center gap-2 text-sm font-semibold text-app-primary">
              {card.title}
              {card.readOnly && <span className="inline-flex items-center gap-1 text-xs font-normal text-app-faint"><Lock size={11} /> Read only</span>}
            </p>
            <div className="divide-y divide-app-subtle">
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
    <div className="space-y-4 animate-fadeIn">
      <div className="card px-5 py-4">
        <p className="text-sm font-semibold text-app-primary">Your pages</p>
        <div className="mt-2 divide-y divide-app-subtle">
          {contentPages.map((page) => {
            const fields = page.cards.flatMap((c) => c.fields);
            const filled = filledCount(fields, profileFields);
            const Icon = page.icon;
            return (
              <button key={page.key} type="button" onClick={() => onOpenPage(page.key)}
                className="group flex w-full items-center gap-3 py-3 text-left">
                <Icon size={15} className="flex-shrink-0 text-app-muted" />
                <span className="flex-1 text-sm text-app-primary">{page.label}</span>
                <ProgressBar value={filled} max={fields.length || 1} className="w-24 sm:w-32" />
                <span className="w-10 text-right text-xs text-app-muted">{filled}/{fields.length}</span>
                <ChevronRight size={14} className="text-app-faint transition group-hover:translate-x-0.5 group-hover:text-brand-300" />
              </button>
            );
          })}
        </div>
      </div>

      {conflicts.length > 0 && (
        <div className="card border border-amber-400/30 px-5 py-4">
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

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="card px-5 py-4">
          <p className="text-sm font-semibold text-app-primary">Latest CV import</p>
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
        <div className="card px-5 py-4">
          <p className="text-sm font-semibold text-app-primary">What the assistant can use</p>
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
