import { useEffect, useState } from "react";
import { GraduationCap } from "lucide-react";
import { getLifecycle } from "../../api";
import { LoadingState, PageHeader } from "../components/student/PageParts";
import { Badge, Card, EmptyState } from "../components/ui";
import { formatDate } from "../utils/format";

// A current or graduating student's study record (GET /lifecycle): the
// school's academic record, their course enrollments, and degree progress
// against the current curriculum — from completed courses, and with the
// courses in progress counted as if passed.

const ROLE_LABELS = {
  core_mandatory: "Core (mandatory)",
  core_choice: "Core (choice)",
  elective: "Elective",
  capstone: "Capstone",
  core_replacement_candidate: "Core replacement",
  unclassified: "Not counted",
};

const STATUS_SECTIONS = [
  { status: "current", title: "In progress" },
  { status: "completed", title: "Completed" },
  { status: "planned", title: "Planned" },
];

const CAPSTONE_PATHS = {
  undecided: "Not decided yet: the capstone project (FT5007) or three more electives",
  direct_in_progress: "Capstone route: core and electives done, the capstone project is next",
  direct_completed: "Capstone project completed",
  elective_alternative_in_progress: "Elective route: three more electives replace the capstone project",
  elective_alternative_complete: "Elective route completed",
};

function capitalize(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

function RecordCard({ programme, record }) {
  const details = [
    ["Study mode", record?.study_mode],
    ["Specialisation", record?.track],
    ["Enrolled on", formatDate(record?.enrolled_at)],
    ["Academic standing", capitalize(record?.academic_standing)],
    ["GPA band", record?.gpa_band],
    [record?.graduation_term ? "Graduation term" : "Expected graduation", record?.graduation_term || record?.expected_grad_term],
  ].filter(([, value]) => value);

  return (
    <Card className="mb-5 rounded-[20px] border border-slate-200/80 bg-white/90 p-5 shadow-[0_10px_30px_rgba(15,23,42,0.04)] transition duration-300 hover:-translate-y-0.5 dark:border-slate-700 dark:bg-slate-800/85 dark:shadow-[0_14px_35px_rgba(2,6,23,0.2)] sm:p-6">
      <div className="mb-5 flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-300">Programme record</p>
          <p className="mt-1 font-display text-xl font-bold tracking-tight text-slate-900 dark:text-slate-50">{programme.name || programme.code}</p>
        </div>
        <span className="rounded-full bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-600 dark:text-blue-300">Academic profile</span>
      </div>
      {details.length > 0 ? (
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {details.map(([label, value]) => (
            <div key={label} className="rounded-xl bg-slate-50/80 px-3 py-3 dark:bg-slate-900/30">
              <dt className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</dt>
              <dd className="mt-1 text-sm font-semibold text-slate-800 dark:text-slate-100">{value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-sm text-app-muted mt-3">The school has no academic record on file for you yet.</p>
      )}
    </Card>
  );
}

// Completed amount as a solid bar, the extra the courses in progress would
// add as a lighter one behind it.
function RequirementRow({ label, done, projected, target, unit }) {
  const inProgress = projected - done;
  const completedPct = target ? Math.min(100, (done / target) * 100) : 0;
  const inProgressPct = target ? Math.min(100 - completedPct, (Math.max(0, inProgress) / target) * 100) : 0;
  const remainingPct = Math.max(0, 100 - completedPct - inProgressPct);
  const projectedPct = target ? Math.round((Math.min(projected, target) / target) * 100) : 0;
  return (
    <div className="rounded-xl border border-slate-200/70 bg-slate-50/60 p-4 dark:border-slate-700 dark:bg-slate-900/25">
      <div className="mb-2 flex items-center justify-between gap-3 text-sm">
        <span className="font-medium text-slate-600 dark:text-slate-300">{label}</span>
        <span className="font-bold text-slate-900 dark:text-slate-100">
          {done}/{target} {unit}
          {inProgress > 0 && <span className="ml-1 text-xs font-normal text-slate-500 dark:text-slate-400"> (+{inProgress} in progress)</span>}
        </span>
      </div>
      <div
        className="flex h-3 w-full overflow-hidden rounded-full bg-slate-200 shadow-inner dark:bg-slate-700"
        role="progressbar"
        aria-label={`${label}: ${done} of ${target} completed, ${inProgress} in progress`}
        aria-valuemin="0"
        aria-valuemax={target}
        aria-valuenow={Math.min(projected, target)}
      >
        <div className="h-full bg-blue-800 transition-all duration-700 dark:bg-blue-500" style={{ width: `${completedPct}%` }} />
        <div className="h-full bg-blue-300 transition-all duration-700 dark:bg-blue-300/80" style={{ width: `${inProgressPct}%` }} />
        <div className="h-full bg-slate-200 transition-all duration-700 dark:bg-slate-700" style={{ width: `${remainingPct}%` }} />
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500 dark:text-slate-400">
        <span>Projected after current semester: <strong className="text-slate-700 dark:text-slate-200">{Math.min(projected, target)}/{target} {unit}</strong> ({projectedPct}%)</span>
        <span className="inline-flex items-center gap-2">
          <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-blue-800 dark:bg-blue-500" /> Completed</span>
          <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-blue-300" /> In progress</span>
        </span>
      </div>
    </div>
  );
}

function ProgressCard({ progress, projected }) {
  const mandatoryTarget = progress.core_mandatory_done.length + progress.core_mandatory_remaining.length;
  const choiceTarget = progress.core_choice_done.length + progress.core_choice_remaining_count;
  const cautions = projected.core_replacement_cautions;

  return (
    <Card className="mb-5 rounded-[20px] border border-blue-200/70 bg-gradient-to-br from-blue-50/80 via-white to-indigo-50/60 p-5 shadow-[0_10px_30px_rgba(37,99,235,0.06)] dark:border-blue-500/20 dark:from-blue-950/50 dark:via-slate-800 dark:to-indigo-950/50 sm:p-6">
      <div className="mb-5 flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-300">Progress snapshot</p>
          <p className="mt-1 font-display text-xl font-bold tracking-tight text-slate-900 dark:text-slate-50">Degree progress</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Lighter indicators include courses currently in progress.</p>
        </div>
        <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm dark:bg-slate-900/40 dark:text-slate-300">Live record</span>
      </div>
      <div className="space-y-3">
        <RequirementRow label="Total units" done={progress.total_units_done}
          projected={projected.total_units_done} target={progress.total_units_target} unit="units" />
        <RequirementRow label="Mandatory core courses" done={progress.core_mandatory_done.length}
          projected={projected.core_mandatory_done.length} target={mandatoryTarget} unit="courses" />
        <RequirementRow label="Core choice courses" done={progress.core_choice_done.length}
          projected={projected.core_choice_done.length} target={choiceTarget} unit="courses" />
        <RequirementRow label="Elective units" done={progress.elective_units_done}
          projected={projected.elective_units_done} target={projected.elective_units_target} unit="units" />
      </div>

      {projected.core_mandatory_remaining.length > 0 && (
        <p className="mt-4 rounded-xl bg-white/60 px-3 py-3 text-xs text-slate-600 dark:bg-slate-900/30 dark:text-slate-300">
          Mandatory core still to take: {projected.core_mandatory_remaining.join(", ")}
        </p>
      )}
      <p className="mt-2 rounded-xl bg-white/60 px-3 py-3 text-xs text-slate-600 dark:bg-slate-900/30 dark:text-slate-300">{CAPSTONE_PATHS[projected.capstone_path]}</p>
      {projected.elective_level4000_cap_reached && (
        <p className="mt-2 rounded-xl bg-amber-500/10 px-3 py-3 text-xs text-amber-700 dark:text-amber-300">
          You have reached the limit of two 4000-level electives; further ones will not count.
        </p>
      )}
      {cautions.map((caution) => (
        <p key={caution} className="mt-2 rounded-xl bg-amber-500/10 px-3 py-3 text-xs text-amber-700 dark:text-amber-300">{caution}</p>
      ))}
    </Card>
  );
}

function CourseList({ title, courses }) {
  return (
    <Card className="mb-5 rounded-[20px] border border-slate-200/80 bg-white/90 p-5 shadow-[0_10px_30px_rgba(15,23,42,0.04)] dark:border-slate-700 dark:bg-slate-800/85 dark:shadow-[0_14px_35px_rgba(2,6,23,0.2)] sm:p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="font-display text-lg font-bold tracking-tight text-slate-900 dark:text-slate-50">{title}</p>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500 dark:bg-slate-700 dark:text-slate-300">{courses.length} {courses.length === 1 ? "course" : "courses"}</span>
      </div>
      <div className="divide-y divide-slate-200/80 dark:divide-slate-700">
        {courses.map((course) => (
          <div key={`${course.course_code}-${course.term}`} className="group flex flex-wrap items-center gap-3 rounded-xl py-3 transition hover:bg-slate-50 dark:hover:bg-slate-700/40 sm:flex-nowrap sm:px-2">
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm text-slate-800 dark:text-slate-100">
                <span className="font-bold">{course.course_code}</span>
                {course.title && <span className="text-slate-500 dark:text-slate-400"> · {course.title}</span>}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {[course.term, course.units != null && `${course.units} units`].filter(Boolean).join(" · ")}
              </p>
            </div>
            {course.grade_band && <Badge color="emerald2">{course.grade_band}</Badge>}
            <Badge color="ink">{ROLE_LABELS[course.requirement_role] || course.requirement_role}</Badge>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function LifecyclePage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getLifecycle()
      .then(setData)
      .catch((err) => setError(err.message || "Unable to load your study record."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <LoadingState icon={GraduationCap} title="Loading lifecycle" subtitle="Fetching your study record..." />;
  }

  return (
    <div className="mx-auto max-w-7xl px-1 pb-8">
      <PageHeader icon={GraduationCap} title="Lifecycle" subtitle="Your studies and progress toward graduation" />

      {error && (
        <Card className="mb-4 border border-red-400/30 bg-red-500/10">
          <p className="text-sm text-red-300">{error}</p>
        </Card>
      )}

      {data && (
        <>
          <RecordCard programme={data.programme} record={data.record} />
          <ProgressCard progress={data.progress} projected={data.projected_progress} />
          {data.courses.length === 0 ? (
            <Card>
              <EmptyState icon={GraduationCap} title="No courses yet" subtitle="The school has no course enrollments on file for you." />
            </Card>
          ) : (
            STATUS_SECTIONS.map(({ status, title }) => {
              const courses = data.courses.filter((c) => c.status === status);
              return courses.length > 0 && <CourseList key={status} title={title} courses={courses} />;
            })
          )}
        </>
      )}
    </div>
  );
}
