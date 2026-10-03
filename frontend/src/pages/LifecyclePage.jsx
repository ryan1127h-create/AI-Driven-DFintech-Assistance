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
    <Card className="mb-4">
      <p className="text-xs text-app-muted">Programme</p>
      <p className="font-display text-lg font-semibold text-app-primary mt-0.5">{programme.name || programme.code}</p>
      {details.length > 0 ? (
        <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-4">
          {details.map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs text-app-muted">{label}</dt>
              <dd className="text-sm text-app-primary">{value}</dd>
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
  const pct = (value) => (target ? Math.min(100, (value / target) * 100) : 0);
  const inProgress = projected - done;
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-app-secondary">{label}</span>
        <span className="text-app-primary font-medium">
          {done}/{target} {unit}
          {inProgress > 0 && <span className="text-app-muted font-normal"> (+{inProgress} in progress)</span>}
        </span>
      </div>
      <div className="relative mt-1.5 h-2 w-full rounded-full bg-app-hover overflow-hidden">
        <div className="absolute inset-y-0 left-0 rounded-full bg-brand-500/35" style={{ width: `${pct(projected)}%` }} />
        <div className="absolute inset-y-0 left-0 rounded-full bg-brand-500" style={{ width: `${pct(done)}%` }} />
      </div>
    </div>
  );
}

function ProgressCard({ progress, projected }) {
  const mandatoryTarget = progress.core_mandatory_done.length + progress.core_mandatory_remaining.length;
  const choiceTarget = progress.core_choice_done.length + progress.core_choice_remaining_count;
  const cautions = projected.core_replacement_cautions;

  return (
    <Card className="mb-4">
      <p className="font-display text-base font-semibold text-app-primary">Degree progress</p>
      <p className="text-xs text-app-muted mt-0.5">Lighter bars count your courses in progress as if passed.</p>
      <div className="space-y-4 mt-4">
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
        <p className="text-xs text-app-secondary mt-4">
          Mandatory core still to take: {projected.core_mandatory_remaining.join(", ")}
        </p>
      )}
      <p className="text-xs text-app-secondary mt-2">{CAPSTONE_PATHS[projected.capstone_path]}</p>
      {projected.elective_level4000_cap_reached && (
        <p className="text-xs text-amber-300 mt-2">
          You have reached the limit of two 4000-level electives; further ones will not count.
        </p>
      )}
      {cautions.map((caution) => (
        <p key={caution} className="text-xs text-amber-300 mt-2">{caution}</p>
      ))}
    </Card>
  );
}

function CourseList({ title, courses }) {
  return (
    <Card className="mb-4">
      <p className="font-display text-base font-semibold text-app-primary">{title}</p>
      <div className="mt-3 divide-y divide-app-soft">
        {courses.map((course) => (
          <div key={`${course.course_code}-${course.term}`} className="flex items-center gap-3 py-2.5">
            <div className="flex-1 min-w-0">
              <p className="text-sm text-app-primary truncate">
                <span className="font-medium">{course.course_code}</span>
                {course.title && <span className="text-app-secondary"> · {course.title}</span>}
              </p>
              <p className="text-xs text-app-muted">
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
    <div>
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
