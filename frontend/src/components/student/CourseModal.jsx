import { Card} from "../ui";

function CourseModal({ course, onClose }) {
  if (!course) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="max-w-3xl w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <Card>
          <div className="flex justify-between items-start mb-4">
            <div>
              <p className="font-mono text-brand-300">
                {course.course_code}
              </p>

              <h2 className="text-xl font-semibold">
                {course.title}
              </h2>
            </div>

            <button
              onClick={onClose}
              className="text-app-muted"
            >
              ✕
            </button>
          </div>

          <div className="space-y-3">
            <p>
              <strong>Credits:</strong> {course.module_credit}
            </p>

            <p>
              <strong>Faculty:</strong> {course.faculty}
            </p>

            <p>
              <strong>Department:</strong> {course.department}
            </p>

            {course.description && (
              <div>
                <strong>Description</strong>
                <p>{course.description}</p>
              </div>
            )}

            {course.prerequisite && (
              <div>
                <strong>Prerequisite</strong>
                <p>{course.prerequisite}</p>
              </div>
            )}

            {course.corequisite && (
              <div>
                <strong>Corequisite</strong>
                <p>{course.corequisite}</p>
              </div>
            )}

            {course.preclusion && (
              <div>
                <strong>Preclusion</strong>
                <p>{course.preclusion}</p>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

export default CourseModal;