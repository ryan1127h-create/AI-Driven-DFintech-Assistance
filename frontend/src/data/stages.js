// Which workspace pages each lifecycle stage sees, on top of the chat and
// the profile every stage has. The stage is the profile's lifecycle_stage
// (returned with the user by login and GET /auth/me); a stage not listed
// here (alumni, or none yet) sees only the chat and the profile.

import { GraduationCap, ListChecks } from "lucide-react";

export const WORKSPACE_PAGES = {
  checklist: { to: "/workspace/checklist", label: "Checklist", icon: ListChecks },
  lifecycle: { to: "/workspace/lifecycle", label: "Lifecycle", icon: GraduationCap },
};

const STAGE_PAGES = {
  prospect: ["checklist"],
  applicant: ["checklist"],
  admitted: ["checklist"],
  current: ["lifecycle"],
  graduating: ["lifecycle"],
};

export const STAGE_LABELS = {
  prospect: "Prospective student",
  applicant: "Applicant",
  admitted: "Admitted",
  current: "Current student",
  graduating: "Graduating",
  alumni: "Alumni",
};

export function canSeePage(stage, page) {
  return (STAGE_PAGES[stage] || []).includes(page);
}

export function pagesForStage(stage) {
  return (STAGE_PAGES[stage] || []).map((key) => ({ key, ...WORKSPACE_PAGES[key] }));
}
