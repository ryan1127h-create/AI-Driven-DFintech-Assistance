// Profile field rendering shared by the profile page and the profile questionnaire.
// Everything is driven by the field dictionary from GET /profile/definitions
// (value_type, allowed_values, value_labels, values_ref), so a field added
// to profile.field_definitions shows up here without frontend changes —
// except the few structured shapes handled explicitly below.

import { Plus, X } from "lucide-react";
import { Badge } from "../../ui";
import { cn } from "../../../utils/cn";

// lifecycle_stage -> the stage codes used in a definition's `stages`.
export const STAGE_CODES = {
  prospect: "PRO",
  applicant: "APP",
  admitted: "ADM",
  current: "CUR",
  graduating: "GRD",
  alumni: "ALU",
};

const SOURCE_BADGES = {
  QA: { color: "brand", label: "Self-reported" },
  CV: { color: "royal", label: "From CV" },
  DB: { color: "emerald2", label: "School records" },
  DER: { color: "ink", label: "System" },
  BHV: { color: "ink", label: "System" },
};

const LANGUAGE_LEVELS = ["fluent", "basic"];

export function SourceBadge({ source }) {
  const badge = SOURCE_BADGES[source];
  return badge ? <Badge color={badge.color}>{badge.label}</Badge> : null;
}

export function isEmptyValue(value) {
  if (value === null || value === undefined || value === "") return true;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value).length === 0;
  return false;
}

// values_ref of the role tag table (current_position and currently_hiring
// pick role families from it too).
export const ROLE_TAGS_REF = "knowledge.tags_definition";

// The options (key -> display name) of a field that takes its values from
// another table (definition.values_ref) — `refOptions` is the dictionary's
// ref_options; null for any other field.
export function refChoices(definition, refOptions) {
  return definition.values_ref ? refOptions?.[definition.values_ref] || {} : null;
}

// The display name of one enum value (falls back to the raw value).
function optionLabel(definition, value, refOptions) {
  const ref = refChoices(definition, refOptions);
  if (ref?.[value]) return ref[value];
  return definition.value_labels?.[String(value)] || String(value);
}

function itemKey(item) {
  return item && typeof item === "object" ? item.key : item;
}

// --- display ------------------------------------------------------------------

export function formatFieldValue(definition, value, refOptions) {
  if (isEmptyValue(value)) return "—";
  const key = definition.field_key;
  if (key === "application_record" && Array.isArray(value)) {
    return value
      .map((app) => {
        const missing = (app.missing_items || []).length;
        return `${app.application_no}: ${app.status}${missing ? ` (${missing} document(s) not yet received)` : ""}`;
      })
      .join("; ");
  }
  if (key === "admission_tests" && Array.isArray(value)) {
    return value.map((t) => `${t.key} ${t.score}${t.test_date ? ` (${t.test_date})` : ""}`).join(", ");
  }
  if (key === "credits" && typeof value === "object") return `${value.earned ?? 0} earned`;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (item && typeof item === "object") {
          if (item.course_code) return item.course_code;
          const extras = Object.entries(item).filter(([k]) => k !== "key").map(([k, v]) => `${k}: ${v}`);
          return optionLabel(definition, item.key, refOptions) + (extras.length ? ` (${extras.join(", ")})` : "");
        }
        return optionLabel(definition, item, refOptions);
      })
      .join(", ");
  }
  if (typeof value === "object") {
    return Object.entries(value)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
      .join(" · ");
  }
  return optionLabel(definition, value, refOptions);
}

// --- inputs -------------------------------------------------------------------

function ChoiceChips({ options, selected, onToggle, labelOf }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((opt) => {
        const active = selected.includes(opt);
        return (
          <button
            key={String(opt)}
            type="button"
            onClick={() => onToggle(opt)}
            className={cn(
              "rounded-lg border px-2.5 py-1 text-xs transition-all",
              active
                ? "bg-brand-500/15 border-brand-400/30 text-brand-300"
                : "bg-app-hover border-app-soft text-app-secondary hover:border-brand-400/20",
            )}
          >
            {labelOf(opt)}
          </button>
        );
      })}
    </div>
  );
}

function SelectInput({ definition, value, onChange, options, refOptions }) {
  const numeric = options.some((o) => typeof o === "number");
  return (
    <select
      className="input"
      value={value === null || value === undefined ? "" : String(value)}
      onChange={(e) => {
        const raw = e.target.value;
        if (raw === "") onChange(null);
        else onChange(numeric ? Number(raw) : raw);
      }}
    >
      <option value="">—</option>
      {options.map((o) => (
        <option key={String(o)} value={String(o)}>
          {optionLabel(definition, o, refOptions)}
        </option>
      ))}
    </select>
  );
}

function MultiChoiceInput({ definition, value, onChange, options, refOptions }) {
  const items = Array.isArray(value) ? value : [];
  const selected = items.map(itemKey);
  const toggle = (opt) => {
    if (selected.includes(opt)) {
      const next = items.filter((i) => itemKey(i) !== opt);
      onChange(next.length ? next : null);
    } else {
      if (definition.max_items && items.length >= definition.max_items) return;
      onChange([...items, opt]);
    }
  };
  return (
    <div>
      <ChoiceChips options={options} selected={selected} onToggle={toggle}
        labelOf={(o) => optionLabel(definition, o, refOptions)} />
      {definition.max_items && (
        <p className="text-xs text-app-faint mt-1">Pick up to {definition.max_items}.</p>
      )}
    </div>
  );
}

function RowList({ rows, onChange, makeRow, renderRow, addLabel }) {
  return (
    <div className="space-y-2">
      {rows.map((row, i) => (
        <div key={i} className="flex items-center gap-2">
          {renderRow(row, (next) => onChange(rows.map((r, j) => (j === i ? next : r))))}
          <button type="button" className="btn-ghost p-1.5" onClick={() => onChange(rows.filter((_, j) => j !== i))}>
            <X size={14} />
          </button>
        </div>
      ))}
      <button type="button" className="btn-outline text-xs" onClick={() => onChange([...rows, makeRow()])}>
        <Plus size={14} /> {addLabel}
      </button>
    </div>
  );
}

function AdmissionTestsInput({ definition, value, onChange }) {
  const rows = Array.isArray(value) ? value : [];
  const tests = definition.allowed_values || [];
  return (
    <RowList
      rows={rows}
      onChange={(next) => onChange(next.length ? next : null)}
      makeRow={() => ({ key: tests[0], score: "" })}
      addLabel="Add test"
      renderRow={(row, set) => (
        <>
          <select className="input w-28" value={row.key} onChange={(e) => set({ ...row, key: e.target.value })}>
            {tests.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <input className="input w-24" type="number" min="0" step="any" placeholder="Score" value={row.score ?? ""}
            onChange={(e) => set({ ...row, score: e.target.value === "" ? "" : Number(e.target.value) })} />
          <input className="input w-40" type="date" value={row.test_date || ""}
            onChange={(e) => set({ ...row, test_date: e.target.value || undefined })} />
        </>
      )}
    />
  );
}

function LanguagesInput({ value, onChange }) {
  const rows = Array.isArray(value) ? value.map((v) => (typeof v === "object" ? v : { key: v })) : [];
  return (
    <RowList
      rows={rows}
      onChange={(next) => onChange(next.length ? next : null)}
      makeRow={() => ({ key: "", level: "fluent" })}
      addLabel="Add language"
      renderRow={(row, set) => (
        <>
          <input className="input w-32" placeholder="e.g. en, zh" value={row.key}
            onChange={(e) => set({ ...row, key: e.target.value.trim() })} />
          <select className="input w-32" value={row.level || ""} onChange={(e) => set({ ...row, level: e.target.value || undefined })}>
            <option value="">—</option>
            {LANGUAGE_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </>
      )}
    />
  );
}

function TextListInput({ value, onChange, placeholder }) {
  const text = Array.isArray(value) ? value.map(itemKey).join(", ") : "";
  return (
    <input
      className="input"
      placeholder={placeholder || "Comma-separated"}
      defaultValue={text}
      onBlur={(e) => {
        const items = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
        onChange(items.length ? items : null);
      }}
    />
  );
}

function CurrentPositionInput({ value, onChange, definitions, refOptions }) {
  const roles = refOptions?.[ROLE_TAGS_REF] || {};
  const v = value || {};
  const set = (k, x) => {
    const next = { ...v, [k]: x || undefined };
    Object.keys(next).forEach((key) => next[key] === undefined && delete next[key]);
    onChange(Object.keys(next).length ? next : null);
  };
  const markets = definitions?.target_markets?.allowed_values || [];
  const seniority = definitions?.seniority_level?.allowed_values || [];
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
      <select className="input" value={v.role_family || ""} onChange={(e) => set("role_family", e.target.value)}>
        <option value="">Role family —</option>
        {Object.entries(roles).map(([tag, name]) => <option key={tag} value={tag}>{name || tag}</option>)}
      </select>
      <select className="input" value={v.region || ""} onChange={(e) => set("region", e.target.value)}>
        <option value="">Region —</option>
        {markets.map((m) => <option key={m} value={m}>{m}</option>)}
      </select>
      <select className="input" value={v.seniority || ""} onChange={(e) => set("seniority", e.target.value)}>
        <option value="">Seniority —</option>
        {seniority.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
    </div>
  );
}

function CurrentlyHiringInput({ value, onChange, refOptions }) {
  const names = refOptions?.[ROLE_TAGS_REF] || {};
  const v = value || {};
  const roles = v.role_families || [];
  const update = (next) => onChange(next.hiring === undefined && !(next.role_families || []).length ? null : next);
  return (
    <div className="space-y-2">
      <label className="flex items-center gap-2 text-sm text-app-secondary">
        <input type="checkbox" checked={!!v.hiring} onChange={(e) => update({ ...v, hiring: e.target.checked })} />
        Currently hiring
      </label>
      <ChoiceChips
        options={Object.keys(names)}
        selected={roles}
        onToggle={(tag) => update({ ...v, role_families: roles.includes(tag) ? roles.filter((r) => r !== tag) : [...roles, tag] })}
        labelOf={(tag) => names[tag] || tag}
      />
    </div>
  );
}

// One input for one field; onChange(null) clears it.
export function FieldInput({ definition, value, onChange, refOptions, definitions }) {
  const key = definition.field_key;
  const type = definition.value_type;
  const allowed = definition.allowed_values;

  if (key === "admission_tests") return <AdmissionTestsInput definition={definition} value={value} onChange={onChange} />;
  if (key === "languages") return <LanguagesInput value={value} onChange={onChange} />;
  if (key === "current_position") {
    return <CurrentPositionInput value={value} onChange={onChange} definitions={definitions} refOptions={refOptions} />;
  }
  if (key === "currently_hiring") return <CurrentlyHiringInput value={value} onChange={onChange} refOptions={refOptions} />;

  if (type === "bool") {
    return (
      <select className="input" value={value === true ? "true" : value === false ? "false" : ""}
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "true")}>
        <option value="">—</option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    );
  }
  if (type === "year") {
    return (
      <input className="input" type="number" min="1950" max="2100" value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))} />
    );
  }
  if (type === "term") {
    return (
      <input className="input" placeholder="AY2027/28 Sem1" value={value ?? ""}
        onChange={(e) => onChange(e.target.value.trim() === "" ? null : e.target.value)} />
    );
  }
  const ref = refChoices(definition, refOptions);
  const options = allowed || (ref ? Object.keys(ref) : null);
  if (type === "single") {
    return options
      ? <SelectInput definition={definition} value={value} onChange={onChange} options={options} refOptions={refOptions} />
      : <input className="input" value={value ?? ""} maxLength={120}
          onChange={(e) => onChange(e.target.value.trim() === "" ? null : e.target.value)} />;
  }
  if (type === "multi") {
    return options
      ? <MultiChoiceInput definition={definition} value={value} onChange={onChange} options={options} refOptions={refOptions} />
      : <TextListInput value={value} onChange={onChange} />;
  }
  return <p className="text-xs text-app-faint">Not editable here.</p>;
}

// --- helpers for forms ----------------------------------------------------------

// The {key: value} PATCH body for everything that changed between the
// stored profile and the form (cleared fields become null).
export function changedFields(profileFields, form) {
  const changes = {};
  for (const [key, value] of Object.entries(form)) {
    const before = profileFields?.[key]?.value;
    const after = isEmptyValue(value) ? null : value;
    if (JSON.stringify(before ?? null) !== JSON.stringify(after)) {
      if (after === null && isEmptyValue(before)) continue;
      changes[key] = after;
    }
  }
  return changes;
}
