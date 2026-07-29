import { ArrowLeft, MessageSquare } from "lucide-react";
import { compareDimensions } from "../../../data/wizard";
import { StepIndicator } from "./LandingStep";

export default function ResultsStep({ results, onBack, onStartChat }) {
  const { profile, material_analysis, material_summary, r } = results;
  const isApplicant = profile.lifecycle_stage === "applicant";

  const sections = [];
  if (material_analysis) sections.push({ id: "materials", icon: "📎", label: "Material analysis" });
  if (r.checklist) sections.push({ id: "checklist", icon: "📋", label: "Application checklist" });
  if (r.tracker) sections.push({ id: "tracker", icon: "🔎", label: "Application status" });
  if (r.tracker) sections.push({ id: "actions", icon: "🧭", label: "Supplement / human support" });
  if (r.comparison) sections.push({ id: "compare", icon: "⚖️", label: "Programme comparison" });
  if (r.recommendation) sections.push({ id: "courses", icon: "🎓", label: "Courses and pathway" });

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6 animate-fadeIn">
      <StepIndicator current={3} />

      <div className="text-center">
        <h1 className="font-display text-2xl font-bold text-app-primary">
          {isApplicant ? "Applicant analysis results" : "Course and skill recommendations for current students"}
        </h1>
        <p className="text-app-muted mt-2 text-sm">
          {isApplicant
            ? "The system has run checks using your profile, CV, and uploaded materials: application checklist, application status, programme comparison, and course/career guidance."
            : "The system is in the current-student flow: no school recommendations or application-material checks are generated; only course planning, graduation progress, and skill direction are analysed."}
        </p>
      </div>

      <div className="flex items-center justify-between">
        <button onClick={onBack} className="btn-ghost text-sm">
          <ArrowLeft size={14} />
          Edit information and regenerate
        </button>
        <button onClick={onStartChat} className="btn-primary">
          <MessageSquare size={16} />
          Continue to chat
        </button>
      </div>

      <nav className="flex flex-wrap gap-2">
        {sections.map((s) => (
          <a
            key={s.id}
            href={`#${s.id}`}
            className="chip border border-app-input bg-app-hover text-app-muted hover:text-app-primary hover:border-brand-400/20 transition"
          >
            <span>{s.icon}</span>
            {s.label}
          </a>
        ))}
      </nav>

      {material_analysis && (
        <Section id="materials" icon="📎" title="Current material analysis">
          {material_summary && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              <SummaryStat value={`${material_summary.submitted_required} / ${material_summary.required_total}`} label="required materials uploaded" />
              <SummaryStat value={material_summary.missing_required} label="missing" />
              <SummaryStat value={material_summary.rejected_required} label="invalid format/size" />
              <SummaryStat value={material_summary.is_complete ? "Complete" : "Incomplete"} label="system material check" />
            </div>
          )}
          <ul className="space-y-2">
            {material_analysis.map((m) => (
              <li key={m.key} className="rounded-lg border border-app-input bg-app-hover p-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-app-primary">{m.label}</span>
                  <Pill kind={m.required === "required" ? "danger" : m.required === "conditional" ? "warn" : "mute"}>
                    {m.required === "required" ? "Required" : m.required === "conditional" ? "Conditional" : "Supporting"}
                  </Pill>
                  <Pill kind={m.status === "submitted" ? "ok" : "mute"}>
                    {m.status === "submitted" ? "Uploaded" : "Not uploaded"}
                  </Pill>
                  {m.filename && <span className="text-xs text-app-muted">{m.filename}</span>}
                </div>
                <p className="text-xs text-app-muted mt-1">{m.reason}</p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.checklist && (
        <Section id="checklist" icon="📋" title="Application checklist: submission status">
          <p className="text-sm text-app-muted mb-3">{r.checklist.speakable}</p>
          <ul className="space-y-2">
            {r.checklist.data.items.map((it, i) => (
              <li key={i} className="rounded-lg border border-app-input bg-app-hover p-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-app-primary">{it.label}</span>
                  {it.required ? (
                    <Pill kind="danger">Required</Pill>
                  ) : (
                    <Pill kind="mute">Supporting</Pill>
                  )}
                  <Pill kind={it.status === "verified" ? "ok" : "mute"}>{it.status_label}</Pill>
                  {it.urgency === "urgent" && <Pill kind="danger">⏰ Deadline approaching {it.deadline}</Pill>}
                </div>
                <p className="text-xs text-app-muted mt-1">{it.why}</p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.tracker && (
        <Section id="tracker" icon="🔎" title="Application status">
          <span className="chip border bg-amber-500/15 text-amber-300 border-amber-400/20 mb-3 inline-flex">
            Demo / Mock Status
          </span>
          <p className="text-sm text-app-muted">{r.tracker.speakable}</p>
          <div className="mt-3 rounded-lg bg-brand-500/5 border border-brand-400/10 p-3">
            <p className="text-sm font-medium text-app-primary">{r.tracker.data.human_status}</p>
            <p className="text-xs text-app-muted mt-1">{r.tracker.data.next_step}</p>
          </div>
          {r.tracker.data.demo_milestones && (
            <div className="mt-4">
              <label className="text-sm font-medium text-app-secondary">Application timeline</label>
              <ol className="mt-2 space-y-2">
                {r.tracker.data.demo_milestones.map((step, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <span
                      className={`h-2.5 w-2.5 rounded-full flex-shrink-0 ${
                        step.state === "done"
                          ? "bg-emerald2-400"
                          : step.state === "current"
                            ? "bg-brand-500 ring-2 ring-brand-400/30"
                            : "bg-app-faint"
                      }`}
                    />
                    <span className="text-sm text-app-primary flex-1">{step.label}</span>
                    <span className="text-xs text-app-faint">
                      {step.state === "done" ? "Done" : step.state === "current" ? "Current" : "Pending"}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          )}
          {r.tracker.data.outstanding_documents?.length > 0 && (
            <div className="mt-4">
              <label className="text-sm font-medium text-app-secondary">Materials requiring action</label>
              <div className="mt-2 flex flex-wrap gap-2">
                {r.tracker.data.outstanding_documents.map((d, i) => (
                  <Pill key={i} kind="warn">{d.label}</Pill>
                ))}
              </div>
            </div>
          )}
          {r.tracker.data.reminders?.length > 0 && (
            <div className="mt-4">
              <label className="text-sm font-medium text-app-secondary">Reminders</label>
              <ul className="mt-2 space-y-2">
                {r.tracker.data.reminders.map((rem, i) => (
                  <li key={i} className="rounded-lg border border-app-input bg-app-hover p-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-app-primary">{rem.name}</span>
                      <Pill kind="mute">{rem.date}</Pill>
                    </div>
                    <p className="text-xs text-app-muted mt-1">{rem.message}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Section>
      )}

      {r.tracker && (
        <Section id="actions" icon="🧭" title="Supplementary material / human support entry">
          {r.tracker.data.outstanding_documents?.length > 0 ? (
            <p className="text-sm text-app-muted">
              <strong>Supplement recommendation:</strong> Some materials are missing or invalid.
              Return to the form, upload the correct files, and regenerate the analysis.
            </p>
          ) : (
            <p className="text-sm text-app-muted">
              <strong>No material-level supplementary action is currently needed.</strong> If your
              issue involves a deadline exception, appeal, or special circumstances, use human support.
            </p>
          )}
          <div className="mt-3 rounded-lg bg-app-hover border border-app-input p-3 space-y-1 text-sm">
            <div><strong className="text-app-primary">Suggested route:</strong> {r.tracker.data.escalation_packet.suggested_team}</div>
            <div><strong className="text-app-primary">Reason:</strong> {r.tracker.data.escalation_packet.reason}</div>
            <div><strong className="text-app-primary">Application ID:</strong> {r.tracker.data.escalation_packet.application_id}</div>
            <div><strong className="text-app-primary">Current status:</strong> {r.tracker.data.escalation_packet.current_status}</div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <a
              href={r.tracker.data.escalation_packet.official_enquiry_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-outline text-xs"
            >
              Open NUS DFinTech official enquiry form ↗
            </a>
            <a
              href={r.tracker.data.escalation_packet.graduate_admission_system_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost text-xs"
            >
              Open Graduate Admission System ↗
            </a>
          </div>
        </Section>
      )}

      {r.comparison && (
        <Section id="compare" icon="⚖️" title="Programme comparison">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-app-subtle">
                  <th className="text-left py-2 px-3 text-app-secondary font-medium">Programme</th>
                  {compareDimensions.map((d) => (
                    <th key={d} className="text-left py-2 px-3 text-app-secondary font-medium capitalize">{d}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {r.comparison.data.facts_table.rows.map((row) => (
                  <tr
                    key={row.program}
                    className={`border-b border-app-soft ${row.isTarget ? "bg-brand-500/5" : ""}`}
                  >
                    <td className="py-2 px-3 text-app-primary font-medium">
                      {row.program}
                      {row.isTarget && <span className="text-brand-300 ml-1">★</span>}
                    </td>
                    {compareDimensions.map((d) => (
                      <td key={d} className="py-2 px-3 text-app-muted">
                        {row.facts[d] || "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {r.comparison.data.synthesis && (
            <div className="mt-4 rounded-lg bg-brand-500/5 border border-brand-400/10 p-3">
              <p className="text-sm font-medium text-app-primary">AI synthesis analysis (not official fact)</p>
              <p className="text-sm text-app-muted mt-1">{r.comparison.data.synthesis.narrative}</p>
              <p className="text-sm text-app-muted mt-2">
                Based on your preferences, <strong className="text-app-primary">{r.comparison.data.synthesis.best_for_you}</strong> is the closest fit under the current rules. This is not a school ranking.
              </p>
            </div>
          )}
          <p className="text-xs text-app-faint mt-3">{r.comparison.data.disclaimer}</p>
        </Section>
      )}

      {r.recommendation && (
        <Section id="courses" icon="🎓" title={isApplicant ? "Post-enrolment course and career advice" : "Course and skill direction advice"}>
          <p className="text-sm text-app-muted">{r.recommendation.data.explanation}</p>
          <p className="text-xs text-app-faint mt-1">
            Selection method: {r.recommendation.data.selection_source === "llm" ? "AI-selected from candidates" : "rule-based ranking (AI not configured)"}
          </p>

          <label className="text-sm font-medium text-app-secondary mt-4 block">Recommended electives / modules to take</label>
          <ul className="mt-2 space-y-2">
            {r.recommendation.data.recommended.map((mod) => (
              <li key={mod.code} className="rounded-lg border border-app-input bg-app-hover p-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm text-app-primary">
                    <strong>{mod.code}</strong> {mod.name}
                  </span>
                  {mod.credits && <Pill kind="mute">{mod.credits} Units</Pill>}
                  {mod.closes_gaps?.length > 0 && (
                    <span className="text-xs text-app-muted">— closes gaps: {mod.closes_gaps.join(", ")}</span>
                  )}
                </div>
              </li>
            ))}
          </ul>

          {r.recommendation.data.already_completed?.length > 0 && (
            <p className="text-xs text-app-muted mt-3">
              Completed ✓: {r.recommendation.data.already_completed.map((m) => m.code).join(", ")}
            </p>
          )}

          {r.recommendation.data.unrecognized_completed?.length > 0 && (
            <div className="mt-3 rounded-lg bg-brand-500/5 border border-brand-400/10 p-3 text-sm text-app-muted">
              The following completed module codes were not found in the course catalogue and may need
              checking: {r.recommendation.data.unrecognized_completed.join(", ")}
            </div>
          )}

          {r.recommendation.data.skill_gaps?.length > 0 && (
            <div className="mt-4">
              <label className="text-sm font-medium text-app-secondary">Skills to strengthen</label>
              <div className="mt-2 flex flex-wrap gap-2">
                {r.recommendation.data.skill_gaps.map((s) => (
                  <Pill key={s} kind="warn">{s}</Pill>
                ))}
              </div>
            </div>
          )}

          {(() => {
            const gp = r.recommendation.data.graduation_progress;
            const completedPct = Math.min(100, (gp.completed_credits / gp.required) * 100);
            const totalPct = Math.min(100, ((gp.completed_credits + gp.planned_credits) / gp.required) * 100);
            const plannedPct = Math.max(0, totalPct - completedPct);
            return (
              <div className="mt-4">
                <label className="text-sm font-medium text-app-secondary">
                  Graduation credit progress
                  <span className="text-xs font-normal text-app-muted ml-2">
                    {gp.completed_credits} / {gp.required} Units completed
                  </span>
                </label>
                <div className="mt-2 h-3 w-full rounded-full bg-app-hover overflow-hidden flex">
                  <div className="h-full bg-emerald2-500" style={{ width: `${completedPct}%` }} />
                  <div className="h-full bg-brand-500" style={{ width: `${plannedPct}%` }} />
                </div>
                <div className="mt-2 flex items-center gap-4 text-xs text-app-muted">
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-emerald2-500" /> Completed: {gp.completed_credits} Units
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-brand-500" /> Recommended plan: +{gp.planned_credits} Units
                  </span>
                  <span>Remaining after plan: {gp.remaining} Units</span>
                </div>
              </div>
            );
          })()}

          <label className="text-sm font-medium text-app-secondary mt-4 block">
            {isApplicant ? "Post-enrolment study path reference" : "Next study path reference"} (full-time vs part-time)
          </label>
          <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {Object.entries(r.recommendation.data.study_plans).map(([pw, plan]) => (
              <div key={pw}>
                <p className="text-xs text-app-muted mb-2">
                  {pw === "full_time" ? "Full-time" : "Part-time"} · term cap {plan.term_credit_cap} Units · {plan.num_terms} terms
                </p>
                <div className="space-y-2">
                  {plan.semesters.map((t, i) => (
                    <div key={i} className="rounded-lg bg-app-hover border border-app-input p-3">
                      <p className="text-sm font-medium text-app-primary">
                        {t.term} · {t.credits} Units
                      </p>
                      <p className="text-xs text-app-muted mt-1">
                        {t.modules.map((m) => m.code).join(" · ")}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function Section({ id, icon, title, children }) {
  return (
    <section id={id} className="card p-5 scroll-mt-4">
      <h2 className="font-display text-base font-semibold text-app-primary mb-3 flex items-center gap-2">
        <span>{icon}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function SummaryStat({ value, label }) {
  return (
    <div className="rounded-lg bg-app-hover border border-app-input p-3 text-center">
      <p className="font-display text-lg font-bold text-app-primary">{value}</p>
      <p className="text-[11px] text-app-muted mt-0.5">{label}</p>
    </div>
  );
}

function Pill({ kind, children }) {
  const kinds = {
    ok: "bg-emerald2-500/15 text-emerald2-400 border-emerald2-400/20",
    danger: "bg-red-500/15 text-red-300 border-red-400/20",
    warn: "bg-amber-500/15 text-amber-300 border-amber-400/20",
    mute: "bg-app-hover text-app-muted border-app-input",
  };
  return <span className={`chip border ${kinds[kind] || kinds.mute}`}>{children}</span>;
}
