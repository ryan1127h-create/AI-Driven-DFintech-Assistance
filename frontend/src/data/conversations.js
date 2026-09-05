// Suggested prompts, conversations, and AI agent definitions per role.
// Only "applicant" and "enrolled_student" are covered here — admin never
// reaches this chatbot UI (see data/roles.js).

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

export const agents = [
  {
    id: "supervisor",
    name: "Supervisor Agent",
    role: "Routes and orchestrates specialist agents",
    icon: "Network",
    color: "brand",
  },
  {
    id: "admissions",
    name: "Admissions Advisor Agent",
    role: "Eligibility, deadlines, documents, application status",
    icon: "FileText",
    color: "royal",
  },
  {
    id: "knowledge",
    name: "Programme Knowledge Agent",
    role: "Curriculum, modules, policies, FAQs",
    icon: "BookOpen",
    color: "cyan2",
  },
  {
    id: "career",
    name: "Career Navigator Agent",
    role: "Career outcomes, guidance, industry trends",
    icon: "Compass",
    color: "emerald2",
  },
  {
    id: "academic",
    name: "Academic Planner Agent",
    role: "Degree planning, progress, course recommendations",
    icon: "Map",
    color: "brand",
  },
  {
    id: "alumni",
    name: "Alumni Network Agent",
    role: "Networking, mentoring, events, consent matching",
    icon: "Users",
    color: "royal",
  },
];

export const recentConversations = [
  {
    id: "c1",
    title: "Eligibility Assessment — Finance Background",
    prompt: "Am I eligible for MSc DFT with a finance background?",
    lastAccessed: "2026-07-15T10:30:00Z",
    lastAccessedLabel: "2h ago",
    role: "prospective",
    stage: "Discover",
    status: "active",
    pinned: false,
    saved: false,
    messages: 8,
    intent: "Eligibility Check",
    confidence: 0.94,
  },
  {
    id: "c2",
    title: "Programme Comparison Request — DFT vs FinEng",
    prompt: "Compare MSc DFT with similar programmes",
    lastAccessed: "2026-07-15T07:15:00Z",
    lastAccessedLabel: "5h ago",
    role: "prospective",
    stage: "Discover",
    status: "active",
    pinned: true,
    saved: true,
    messages: 12,
    intent: "Programme Comparison",
    confidence: 0.89,
  },
  {
    id: "c3",
    title: "Career Path Exploration — Quant vs Product",
    prompt: "View career outcomes for graduates",
    lastAccessed: "2026-07-14T14:00:00Z",
    lastAccessedLabel: "Yesterday",
    role: "prospective",
    stage: "Discover",
    status: "active",
    pinned: false,
    saved: true,
    messages: 6,
    intent: "Career Outcomes",
    confidence: 0.91,
  },
  {
    id: "c4",
    title: "Application Preparation Plan — Round 2",
    prompt: "Generate my application checklist",
    lastAccessed: "2026-07-13T09:00:00Z",
    lastAccessedLabel: "2 days ago",
    role: "applicant",
    stage: "Apply",
    status: "active",
    pinned: true,
    saved: true,
    messages: 10,
    intent: "Checklist Build",
    confidence: 0.95,
  },
  {
    id: "c5",
    title: "Missing Documents Audit — Transcript & Reference",
    prompt: "What documents are still missing?",
    lastAccessed: "2026-07-13T06:00:00Z",
    lastAccessedLabel: "2 days ago",
    role: "applicant",
    stage: "Apply",
    status: "resolved",
    pinned: false,
    saved: false,
    messages: 5,
    intent: "Document Audit",
    confidence: 0.92,
  },
  {
    id: "c6",
    title: "Degree Plan — FinTech AI Track",
    prompt: "Plan my modules for next semester",
    lastAccessed: "2026-07-12T11:00:00Z",
    lastAccessedLabel: "3 days ago",
    role: "enrolled",
    stage: "Study",
    status: "active",
    pinned: false,
    saved: true,
    messages: 14,
    intent: "Degree Planning",
    confidence: 0.88,
  },
  {
    id: "c7",
    title: "Graduation Audit Check",
    prompt: "Run my graduation audit",
    lastAccessed: "2026-07-11T08:00:00Z",
    lastAccessedLabel: "4 days ago",
    role: "graduating",
    stage: "Graduate",
    status: "active",
    pinned: false,
    saved: false,
    messages: 7,
    intent: "Graduation Audit",
    confidence: 0.97,
  },
  {
    id: "c8",
    title: "Alumni Mentor Introduction Request",
    prompt: "Find networking opportunities",
    lastAccessed: "2026-07-08T15:00:00Z",
    lastAccessedLabel: "1 week ago",
    role: "alumni",
    stage: "Alumni",
    status: "resolved",
    pinned: false,
    saved: true,
    messages: 9,
    intent: "Networking",
    confidence: 0.86,
  },
];

export const savedPlans = [
  { id: "p1", title: "2-year FinTech AI track plan", updated: "Updated 3 days ago", progress: 60, stage: "Study" },
  { id: "p2", title: "Application timeline — Round 2", updated: "Updated 1 week ago", progress: 100, stage: "Apply" },
  { id: "p3", title: "Career pivot to Blockchain", updated: "Updated 2 weeks ago", progress: 25, stage: "Discover" },
];

export const notifications = {
  applicant: [
    { id: "a1", type: "warning", title: "Missing transcript", body: "Your application is missing an official transcript.", time: "1h ago" },
    { id: "a2", type: "deadline", title: "Deadline approaching", body: "Round 2 application closes in 5 days.", time: "2h ago" },
    { id: "a3", type: "info", title: "Reference pending", body: "Your referee has not submitted the reference letter yet.", time: "5h ago" },
  ],
  enrolled_student: [
    { id: "e1", type: "info", title: "New module available", body: "CS6204 Blockchain Technology opens for registration.", time: "4h ago" },
    { id: "e2", type: "deadline", title: "Add/drop deadline", body: "Module add/drop closes on 15 September 2026.", time: "1 day ago" },
    { id: "e3", type: "success", title: "Grades published", body: "Your Semester 1 grades are now available.", time: "3 days ago" },
  ],
};

// Recommended actions per role — clickable, with optional pre-filled prompt or navigation target
export const recommendedActions = {
  [ROLES.APPLICANT]: [
    { text: "Check Eligibility", icon: "CheckCircle2", color: "text-brand-300", prompt: "Am I eligible for MSc DFT?", route: null },
    { text: "Compare Programmes", icon: "GitCompare", color: "text-royal-300", prompt: null, route: "/workspace/compare" },
    { text: "Complete Checklist", icon: "CheckCircle2", color: "text-brand-300", prompt: null, route: "/workspace/checklist" },
    { text: "Review Deadlines", icon: "Clock", color: "text-royal-300", prompt: null, route: "/workspace/deadlines" },
    { text: "Application Guidance", icon: "Lightbulb", color: "text-cyan2-400", prompt: null, route: "/workspace/guidance" },
  ],
  [ROLES.ENROLLED_STUDENT]: [
    { text: "Plan Next Semester", icon: "Map", color: "text-brand-300", prompt: "Plan my modules for next semester", route: null },
    { text: "Check Graduation Progress", icon: "TrendingUp", color: "text-emerald2-400", prompt: null, route: "/workspace/progress" },
    { text: "Explore Career Paths", icon: "Lightbulb", color: "text-royal-300", prompt: null, route: "/workspace/career-guidance" },
    { text: "Review Mentor Requests", icon: "HandHeart", color: "text-brand-300", prompt: null, route: "/workspace/mentoring" },
    { text: "RSVP Alumni Mixer", icon: "Calendar", color: "text-royal-300", prompt: null, route: "/workspace/events" },
  ],
};

// AI Insights per role — with insight type, confidence, and recommendation reason
export const aiInsights = {
  [ROLES.APPLICANT]: [
    {
      type: "Eligibility Match",
      text: "Your finance background aligns with 80% of MSc DFT requirements.",
      confidence: 0.91,
      reason: "Based on your degree in Finance and quantitative coursework matching the programme's eligibility criteria.",
    },
    {
      type: "Deadline Risk",
      text: "Submitting your transcript now increases Round 2 admission odds by ~23%.",
      confidence: 0.88,
      reason: "Historical data shows complete applications submitted before the deadline have higher acceptance rates.",
    },
    {
      type: "Document Quality",
      text: "Applications with 2 reference letters have 15% higher acceptance rate.",
      confidence: 0.82,
      reason: "Only 1 reference letter is currently submitted. Adding a second academic reference is recommended.",
    },
  ],
  [ROLES.ENROLLED_STUDENT]: [
    {
      type: "Track Progress",
      text: "You're on track for the AI & ML track. 2 electives remain.",
      confidence: 0.94,
      reason: "You've completed 3 of 5 AI track electives. CS6202 and IS5153 are recommended next.",
    },
    {
      type: "Graduation Readiness",
      text: "Capstone report submission is the only remaining requirement.",
      confidence: 0.97,
      reason: "All other graduation requirements are met. CAP of 4.6 exceeds the 3.5 minimum.",
    },
    {
      type: "Mentoring Opportunity",
      text: "3 new mentor requests match your expertise profile.",
      confidence: 0.86,
      reason: "Students interested in Digital Banking, Strategy, and Payments match your listed expertise.",
    },
  ],
};

// Workflow steps per role — with current step, completed, and next action
export const workflowSteps = {
  [ROLES.APPLICANT]: {
    steps: [
      { name: "Discover Programme", status: "completed" },
      { name: "Application Submitted", status: "completed" },
      { name: "Documents Review", status: "current" },
      { name: "Offer Decision", status: "upcoming" },
    ],
    nextAction: "Submit your missing transcript before the next round deadline",
  },
  [ROLES.ENROLLED_STUDENT]: {
    steps: [
      { name: "Core Modules", status: "completed" },
      { name: "Track Specialisation", status: "current" },
      { name: "Capstone Project", status: "upcoming" },
      { name: "Graduation & Alumni Transition", status: "upcoming" },
    ],
    nextAction: "Complete your remaining track electives",
  },
};

// Canned AI responses keyed by intent — simulates streaming agent output
export const aiResponses = {
  "Eligibility Check": {
    intent: "Eligibility Check",
    stage: "Discover",
    confidence: 0.94,
    source: "Official Policy",
    agent: "admissions",
    text:
      "Based on the official MSc DFT admissions policy, you are eligible if you hold a Bachelor's degree in a relevant discipline (Computing, Finance, Engineering, Statistics, or Mathematics) with at least a B+ average (CAP 4.0+).\n\nA strong quantitative and programming background strengthens your application. For applicants from non-English-medium institutions, TOEFL iBT 90+ or IELTS 6.5+ is required.\n\nGRE/GMAT is recommended but not mandatory. Would you like me to build a personalised eligibility checklist based on your background?",
  },
  "Programme Comparison": {
    intent: "Programme Comparison",
    stage: "Discover",
    confidence: 0.89,
    source: "Knowledge Base",
    agent: "knowledge",
    text:
      "Here's how MSc DFT compares with similar programmes:\n\n• MSc DFT (NUS) — AI + Finance + Systems, FinTech-first, 1.5-2 yrs, capstone included.\n• MSc Financial Engineering (NUS RM) — Quant + Derivatives, banking/trading focus.\n• MSc Computer Science (NUS) — General computing, broad tech careers.\n• MSc FinTech (NTU) — Finance + Analytics, 1-year intensive.\n\nMSc DFT stands out for its interdisciplinary AI-finance-systems curriculum and industry capstone. I've opened the Compare Programmes workspace with a detailed side-by-side view.",
  },
  "Career Outcomes": {
    intent: "Career Outcomes",
    stage: "Discover",
    confidence: 0.91,
    source: "Knowledge Base",
    agent: "career",
    text:
      "Recent MSc DFT graduates pursue roles across the FinTech spectrum:\n\n• FinTech Product Manager (18%)\n• Quantitative Analyst (16%)\n• Blockchain Engineer (14%)\n• Data Scientist, Finance (13%)\n• Risk Technology Lead (10%)\n\nSalary ranges typically fall between $95k–$170k depending on role and experience. I've surfaced the full career outcomes chart in your context panel.",
  },
  "Curriculum Browse": {
    intent: "Curriculum Browse",
    stage: "Discover",
    confidence: 0.93,
    source: "Knowledge Base",
    agent: "knowledge",
    text:
      "The MSc DFT curriculum is 40 credits: 16 core + 16 electives + 8 capstone.\n\nCore modules cover Digital Banking, Smart Contracts, Quantitative Reasoning, and Risk Management Technologies. Electives are organised into four tracks: AI & ML, Blockchain & Digital Assets, Systems & Cloud, and Quantitative Finance.\n\nYou can explore each track and its modules in the Discover Programme workspace.",
  },
  "Status Check": {
    intent: "Status Check",
    stage: "Apply",
    confidence: 0.96,
    source: "Official Policy",
    agent: "admissions",
    text:
      "Your application (Ref: DFT-2026-0481) is currently in the Review stage.\n\nCompleted: Personal particulars, academic transcript, resume, statement of purpose.\nMissing: 1 reference letter (academic), English proficiency proof.\n\nEstimated decision: 4-6 weeks from complete submission. I recommend submitting the missing reference before the Round 2 deadline on 15 March 2026.",
  },
  "Document Audit": {
    intent: "Document Audit",
    stage: "Apply",
    confidence: 0.92,
    source: "Official Policy",
    agent: "admissions",
    text:
      "I audited your application documents. 2 items are outstanding:\n\n1. Official academic transcript (sealed) — not yet received\n2. Academic reference letter — referee has not submitted\n\nYour statement of purpose, resume, and passport copy are verified. Submitting the missing items will move your application to Complete status.",
  },
  "Checklist Build": {
    intent: "Checklist Build",
    stage: "Apply",
    confidence: 0.95,
    source: "AI Recommendation",
    agent: "admissions",
    text:
      "Here is your personalised application checklist:\n\n✓ Personal particulars form\n✓ Resume / CV\n✓ Statement of purpose\n✗ Official academic transcript (sealed)\n✗ Academic reference letter\n○ English proficiency proof (if applicable)\n○ Application fee payment (S$50)\n\nI've added this checklist to your Application Hub so you can track progress there.",
  },
  "Degree Planning": {
    intent: "Degree Planning",
    stage: "Study",
    confidence: 0.88,
    source: "AI Recommendation",
    agent: "academic",
    text:
      "Based on your AI & ML track interest and completed core modules, I recommend the following plan for next semester:\n\n• CS5345 Machine Learning for Finance (4 cr)\n• CS6202 Natural Language Processing (4 cr)\n• IS5153 AI in Finance & RegTech (4 cr)\n• CS5424 Big Data Systems for FinTech (4 cr)\n\nThis keeps you on track for graduation in 1.5 years. I've saved this as a draft plan — review it in your Degree Planner.",
  },
  "Progress Audit": {
    intent: "Progress Audit",
    stage: "Study",
    confidence: 0.97,
    source: "Official Policy",
    agent: "academic",
    text:
      "Your graduation progress is at 72%.\n\nCompleted: 24 of 40 credits (all 4 core modules + 2 electives + capstone in progress).\nRemaining: 2 electives (8 credits) + capstone final report.\n\nYou are on track to graduate next semester. No policy holds detected.",
  },
  default: {
    intent: "General Inquiry",
    stage: "Discover",
    confidence: 0.78,
    source: "AI Recommendation",
    agent: "supervisor",
    text:
      "I'm your MSc DFT lifecycle assistant. I can help with programme discovery, applications, academic planning, graduation, and alumni networking. Try one of the suggested prompts, or ask me anything about the programme.",
  },
};
