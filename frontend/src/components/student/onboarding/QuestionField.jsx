import { Check, FileText } from "lucide-react";
import { cn } from "../../../utils/cn";
import { FieldInput, refChoices } from "../profile/ProfileFields";
import { FIELD_HINTS, upcomingIntakeTerms } from "../../../data/onboarding";

// One questionnaire field, answered by tapping options rather than typing:
// chips for single and multiple choice, a stacked list for proficiency
// levels (whose descriptions are full sentences). Options and their labels
// come from the field dictionary.

function optionLabel(definition, value, refOptions) {
  if (definition.value_type === "bool") return value ? "Yes" : "No";
  return definition.value_labels?.[String(value)] ?? refChoices(definition, refOptions)?.[value] ?? String(value);
}

function optionsFor(definition, answers, refOptions) {
  const key = definition.field_key;
  if (key === "main_target_role") return answers.target_role_families || [];
  if (definition.value_type === "bool") return [true, false];
  if (definition.value_type === "term") {
    const terms = upcomingIntakeTerms();
    return answers[key] && !terms.includes(answers[key]) ? [answers[key], ...terms] : terms;
  }
  if (definition.allowed_values) return definition.allowed_values;
  return Object.keys(refChoices(definition, refOptions) || {});
}

function Chip({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition",
        active
          ? "border-brand-400/40 bg-brand-500/15 text-brand-300"
          : "border-app-subtle text-app-secondary hover:border-brand-400/30 hover:text-app-primary",
      )}
    >
      {active && <Check size={13} />}
      {children}
    </button>
  );
}

function LevelList({ definition, options, value, onChange }) {
  return (
    <div className="space-y-1.5">
      {options.map((option) => {
        const active = value === option;
        return (
          <button
            key={option}
            type="button"
            onClick={() => onChange(active ? null : option)}
            className={cn(
              "flex w-full items-start gap-3 rounded-lg border px-3 py-2 text-left text-sm transition",
              active
                ? "border-brand-400/40 bg-brand-500/10"
                : "border-app-subtle hover:border-brand-400/30",
            )}
          >
            <span
              className={cn(
                "mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border text-[11px] font-medium",
                active ? "border-brand-400 bg-brand-500 text-white" : "border-app-input text-app-muted",
              )}
            >
              {option}
            </span>
            <span className={active ? "text-app-primary" : "text-app-secondary"}>
              {optionLabel(definition, option)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// cvQuote: the CV line this answer was filled from, while the answer still
// holds the CV's value.
// definitions ({field_key: definition}) is only needed by the general inputs
// of structured fields.
export default function QuestionField({ definition, value, onChange, answers, refOptions, recommended, cvQuote, definitions }) {
  const key = definition.field_key;
  const options = optionsFor(definition, answers, refOptions);
  const hint = FIELD_HINTS[key];

  // The general-purpose inputs cover what tapping options can't: structured
  // values, years and free-text lists, and list items carrying extra detail
  // (e.g. {key: "cfa", level: "L2"}), which chips would flatten.
  const needsGeneralInput =
    ["structured", "list", "year"].includes(definition.value_type) ||
    key === "languages" ||
    (definition.value_type !== "bool" && definition.value_type !== "term" && !options.length) ||
    (Array.isArray(value) && value.some((item) => item && typeof item === "object"));

  let input;
  if (needsGeneralInput) {
    input = <FieldInput definition={definition} value={value} onChange={onChange} refOptions={refOptions} definitions={definitions} />;
  } else if (definition.value_type === "single" && options.length && options.every((o) => typeof o === "number")) {
    input = <LevelList definition={definition} options={options} value={value} onChange={onChange} />;
  } else if (definition.value_type === "multi") {
    const selected = Array.isArray(value) ? value : [];
    const max = definition.max_items;
    const toggle = (option) => {
      if (selected.includes(option)) {
        const next = selected.filter((v) => v !== option);
        onChange(next.length ? next : null);
      } else if (!max || selected.length < max) {
        onChange([...selected, option]);
      }
    };
    input = (
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <Chip key={String(option)} active={selected.includes(option)} onClick={() => toggle(option)}>
            {optionLabel(definition, option, refOptions)}
          </Chip>
        ))}
      </div>
    );
  } else {
    input = (
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <Chip key={String(option)} active={value === option} onClick={() => onChange(value === option ? null : option)}>
            {optionLabel(definition, option, refOptions)}
          </Chip>
        ))}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-2">
        <p className="text-sm font-medium text-app-primary">{definition.label}</p>
        {recommended && (
          <span className="chip bg-brand-500/10 text-[10px] text-brand-300">Recommended</span>
        )}
        {cvQuote && (
          <span className="chip bg-amber-500/15 text-[10px] text-amber-300" title={cvQuote}>
            <FileText size={10} /> From your CV
          </span>
        )}
      </div>
      {cvQuote && <p className="mt-0.5 truncate text-xs italic text-app-faint" title={cvQuote}>&ldquo;{cvQuote}&rdquo;</p>}
      {(hint || definition.max_items) && (
        <p className="mt-0.5 text-xs text-app-muted">
          {[hint, definition.max_items && `Pick up to ${definition.max_items}`].filter(Boolean).join(" · ")}
        </p>
      )}
      <div className="mt-2.5">{input}</div>
    </div>
  );
}
