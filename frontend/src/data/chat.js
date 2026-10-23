// Chat workspace content: the suggested prompts and input placeholder on the
// welcome screen (per policy stage, see backend app/core/stage_policy.py) and
// the agent badges shown on assistant replies.

export const suggestedPrompts = {
  prospect: [
    { text: "Am I eligible for MSc DFT?", intent: "Assessment" },
    { text: "Compare MSc DFT with other fintech programmes", intent: "Programme Comparison" },
    { text: "What jobs can I get after this programme?", intent: "Career Paths" },
    { text: "How much are the fees, and what scholarships are there?", intent: "Fees & Scholarships" },
    { text: "Which documents do I need to apply?", intent: "Application Requirements" },
    { text: "What should I brush up on before starting?", intent: "Preparation" },
  ],
  applicant: [
    { text: "Where is my application at?", intent: "Status Check" },
    { text: "What documents are still missing?", intent: "Document Audit" },
    { text: "When is the application deadline?", intent: "Deadlines" },
    { text: "What does each document requirement mean?", intent: "Requirements" },
    { text: "How should I write my personal statement?", intent: "Essay Guidance" },
    { text: "I'd like to talk to the programme office", intent: "Staff Support" },
  ],
  rejected: [
    { text: "My application wasn't successful. What are my options?", intent: "Next Steps" },
    { text: "What should I strengthen before reapplying?", intent: "Preparation" },
    { text: "Am I eligible if I apply again?", intent: "Assessment" },
    { text: "When does the next application round open?", intent: "Deadlines" },
    { text: "Who can give me feedback on my application?", intent: "Staff Support" },
    { text: "Compare MSc DFT with other fintech programmes", intent: "Programme Comparison" },
  ],
  admitted: [
    { text: "How do I accept my offer?", intent: "Offer Acceptance" },
    { text: "What do I need for my Student's Pass?", intent: "Student's Pass" },
    { text: "When and how do I pay the fees?", intent: "Fees" },
    { text: "How should I prepare before the programme starts?", intent: "Getting Ready" },
    { text: "Plan my first semester", intent: "Course Planning" },
    { text: "Which career paths fit my background?", intent: "Career Paths" },
  ],
  current: [
    { text: "Plan my courses for next semester", intent: "Course Planning" },
    { text: "Am I on track to graduate?", intent: "Progress Check" },
    { text: "Which electives fit my target role?", intent: "Course Recommendation" },
    { text: "How does the Capstone internship work?", intent: "Capstone" },
    { text: "Help me get ready for my job search", intent: "Career Prep" },
    { text: "Which alumni could I talk to?", intent: "Alumni" },
  ],
  alumni: [
    { text: "How can I mentor or speak to current students?", intent: "Giving Back" },
    { text: "Which NUS career services can alumni use?", intent: "Career Services" },
    { text: "What's new in the MSc DFT programme?", intent: "Programme News" },
    { text: "How does the Capstone work now? A student asked me", intent: "Programme Knowledge" },
    { text: "What do MSc DFT graduates typically go on to do?", intent: "Career Outcomes" },
    { text: "I'd like to contact the programme office", intent: "Staff Support" },
  ],
};
suggestedPrompts.graduating = suggestedPrompts.current;

export const inputPlaceholders = {
  prospect: "Ask about applying to MSc DFT...",
  rejected: "Ask about your next steps...",
  applicant: "Ask about your application...",
  admitted: "Ask about joining the programme...",
  current: "Ask about your studies...",
  graduating: "Ask about your studies...",
  alumni: "Ask about alumni life...",
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
  alumni: { name: "Alumni Match", role: "Alumni who share your goals" },
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
