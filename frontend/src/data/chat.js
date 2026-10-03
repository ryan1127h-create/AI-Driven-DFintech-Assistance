// Chat workspace content: the suggested prompts on the welcome screen (per
// role) and the agent badges shown on assistant replies.

import { ROLES } from "./roles";

export const suggestedPrompts = {
  [ROLES.APPLICANT]: [
    { icon: "CheckCircle", text: "Am I eligible for MSc DFT?", intent: "Assessment" },
    { icon: "GitCompare", text: "Compare programmes", intent: "Programme Comparison" },
    { icon: "Activity", text: "Check my application status", intent: "Status Check" },
    { icon: "FileWarning", text: "What documents are still missing?", intent: "Document Audit" },
    { icon: "PenLine", text: "Help me write my personal statement", intent: "Essay Guidance" },
    { icon: "CalendarPlus", text: "Guide me through module registration", intent: "Registration Guide" },
  ],
  [ROLES.ENROLLED_STUDENT]: [
    { icon: "Map", text: "Plan my modules for next semester", intent: "Degree Planning" },
    { icon: "TrendingUp", text: "Check my graduation progress", intent: "Progress Audit" },
    { icon: "Briefcase", text: "Recommend courses for fintech roles", intent: "Course Recommendation" },
    { icon: "Briefcase", text: "Prepare me for job interviews", intent: "Career Prep" },
    { icon: "Network", text: "Find networking opportunities", intent: "Networking" },
    { icon: "Briefcase", text: "Access career services", intent: "Career Services" },
  ],
};

// The badge on an assistant reply, keyed by the backend's tool names (see
// backend/app/tools/registration.py). agent_used is not always a plain name:
// "career_agent+clarify", "career_agent+revised" (an evaluated draft),
// "admissions_agent+financial_agent" (a merged multi-topic answer),
// "career_agent_fallback", "career_timeout", "orchestrator_decline" ...
const AGENTS = {
  assistant: { name: "DFT Assistant", role: "General conversation" },
  admissions: { name: "Admissions Advisor", role: "Requirements, deadlines, documents" },
  academic: { name: "Programme Knowledge", role: "Curriculum, courses, policies" },
  financial: { name: "Fees & Scholarships", role: "Tuition, scholarships, financial aid" },
  faq: { name: "Programme FAQ", role: "Student life and general questions" },
  career: { name: "Career Readiness Advisor", role: "Career paths and readiness plans" },
  comparison: { name: "Programme Comparison", role: "MSc DFT against other programmes" },
  assessment: { name: "Application Assessment", role: "Your fit and readiness to apply" },
  course_recommendation: { name: "Course Planner", role: "Personalised course recommendations" },
};

const MODIFIERS = new Set(["clarify", "revised"]);

function agentKey(part) {
  const base = part.replace(/_(fallback|error|timeout|unavailable)$/, "").replace(/_agent$/, "");
  return AGENTS[base] ? base : "assistant";
}

export function resolveAgent(agentUsed) {
  const keys = [
    ...new Set(
      (agentUsed || "")
        .split("+")
        .filter((part) => part && !MODIFIERS.has(part))
        .map(agentKey),
    ),
  ];
  if (keys.length <= 1) return AGENTS[keys[0] || "assistant"];
  return { name: keys.map((k) => AGENTS[k].name).join(" + "), role: "One answer combined from several specialists" };
}
