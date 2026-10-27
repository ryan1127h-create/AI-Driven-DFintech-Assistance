// Real student roles for the chatbot UI. These must match the values the
// backend actually returns (see backend/app/domains/auth/schemas.py::
// SelfRegisterableRole) — "admin" is deliberately excluded, since admin is a
// separate back-office role that never reaches ChatWorkspace/WorkspaceLayout/
// StudentSidebar (it will get its own monitoring UI, unrelated to this file).
export const ROLES = {
  APPLICANT: "applicant",
  ENROLLED_STUDENT: "enrolled_student",
};

export const ROLE_META = {
  [ROLES.APPLICANT]: {
    label: "Applicant",
    stage: "Apply",
    color: "royal",
    icon: "FileText"
  },

  [ROLES.ENROLLED_STUDENT]: {
    label: "Enrolled Student",
    stage: "Study",
    color: "emerald2",
    icon: "BookOpen"
  },
};
