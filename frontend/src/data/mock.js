// Mock data for workspaces, applications, analytics, alumni, and admin

export const applicationStatus = {
  ref: "DFT-2026-0481",
  stage: "Review",
  submitted: "12 Feb 2026",
  rounds: [
    { name: "Submitted", done: true, date: "12 Feb 2026" },
    { name: "Document Verification", done: true, date: "14 Feb 2026" },
    { name: "Review", done: false, date: "In progress", active: true },
    { name: "Decision", done: false, date: "Pending" },
    { name: "Offer", done: false, date: "Pending" },
  ],
  documents: [
    { name: "Personal Particulars Form", status: "verified" },
    { name: "Academic Transcript (sealed)", status: "missing" },
    { name: "Resume / CV", status: "verified" },
    { name: "Statement of Purpose", status: "verified" },
    { name: "Academic Reference Letter", status: "pending" },
    { name: "English Proficiency Proof", status: "missing" },
    { name: "Passport Copy", status: "verified" },
    { name: "Application Fee (S$50)", status: "verified" },
  ],
};

export const academicProgress = {
  creditsCompleted: 24,
  creditsTotal: 40,
  gpa: 4.6,
  cap: 4.6,
  capMax: 5.0,
  semester: "Year 1, Semester 2",
  completedModules: [
    { code: "IS5452", name: "Digital Banking & Innovation", grade: "A", credits: 4 },
    { code: "IS5152", name: "FinTech Innovation & Smart Contracts", grade: "A-", credits: 4 },
    { code: "CS5340", name: "Quantitative Reasoning for FinTech", grade: "A", credits: 4 },
    { code: "IS5462", name: "Risk Management Technologies", grade: "A+", credits: 4 },
    { code: "CS5345", name: "Machine Learning for Finance", grade: "A-", credits: 4 },
    { code: "CS6204", name: "Blockchain Technology", grade: "B+", credits: 4 },
  ],
  remainingModules: [
    { code: "CS6202", name: "Natural Language Processing", credits: 4, planned: true },
    { code: "IS5153", name: "AI in Finance & RegTech", credits: 4, planned: true },
    { code: "CS5424", name: "Big Data Systems for FinTech", credits: 4, planned: false },
    { code: "CAPSTONE", name: "FinTech Capstone Project", credits: 8, inProgress: true },
  ],
};

export const degreePlan = {
  track: "AI & Machine Learning",
  semesters: [
    {
      name: "Semester 1 (completed)",
      modules: [
        { code: "IS5452", name: "Digital Banking & Innovation", credits: 4 },
        { code: "IS5152", name: "FinTech Innovation & Smart Contracts", credits: 4 },
        { code: "CS5340", name: "Quantitative Reasoning for FinTech", credits: 4 },
      ],
    },
    {
      name: "Semester 2 (completed)",
      modules: [
        { code: "IS5462", name: "Risk Management Technologies", credits: 4 },
        { code: "CS5345", name: "Machine Learning for Finance", credits: 4 },
        { code: "CS6204", name: "Blockchain Technology", credits: 4 },
      ],
    },
    {
      name: "Semester 3 (current)",
      modules: [
        { code: "CS6202", name: "Natural Language Processing", credits: 4, status: "planned" },
        { code: "IS5153", name: "AI in Finance & RegTech", credits: 4, status: "planned" },
        { code: "CS5424", name: "Big Data Systems for FinTech", credits: 4, status: "planned" },
        { code: "CAPSTONE", name: "FinTech Capstone Project", credits: 8, status: "inProgress" },
      ],
    },
  ],
};

export const graduationAudit = {
  requirements: [
    { name: "Core Modules (16 cr)", required: 16, completed: 16, status: "met" },
    { name: "Elective Modules (16 cr)", required: 16, completed: 16, status: "met" },
    { name: "Capstone Project (8 cr)", required: 8, completed: 0, status: "inProgress" },
    { name: "Minimum CAP 3.5", required: 3.5, completed: 4.6, status: "met" },
    { name: "Residency Requirement", required: "2 semesters", completed: "2 semesters", status: "met" },
  ],
  eligible: false,
  remaining: "Capstone Project final report submission",
};

export const alumniDirectory = [
  {
    id: "a1",
    name: "Dr. Marcus Tan",
    role: "Head of FinTech Strategy, DBS Bank",
    cohort: "2021",
    verified: true,
    consent: "open",
    connection: "none",
    expertise: ["Digital Banking", "Strategy", "Payments"],
    bio: "Leads digital transformation initiatives at DBS. Open to mentoring 2 students per year.",
  },
  {
    id: "a2",
    name: "Aisha Wong",
    role: "Senior Quant, Citadel",
    cohort: "2022",
    verified: true,
    consent: "introduction",
    connection: "none",
    expertise: ["Quant Trading", "Machine Learning"],
    bio: "Quant researcher in systematic strategies. Accepts introduction requests only.",
  },
  {
    id: "a3",
    name: "Rahul Mehta",
    role: "Founder, FinTech startup",
    cohort: "2020",
    verified: true,
    consent: "closed",
    connection: "connected",
    expertise: ["Blockchain", "DeFi", "Startups"],
    bio: "Building a regulated stablecoin platform. Currently not accepting new connections.",
  },
  {
    id: "a4",
    name: "Jia Hui Lee",
    role: "Risk Tech Lead, MAS",
    cohort: "2023",
    verified: true,
    consent: "open",
    connection: "pending",
    expertise: ["RegTech", "Risk", "Policy"],
    bio: "Regulatory technology at the Monetary Authority of Singapore. Happy to share career insights.",
  },
  {
    id: "a5",
    name: "Kenji Sato",
    role: "Data Scientist, Stripe",
    cohort: "2022",
    verified: true,
    consent: "introduction",
    connection: "none",
    expertise: ["Payments", "Data Science", "Fraud"],
    bio: "Fraud detection ML at Stripe. Available for one-off career chats.",
  },
];

export const alumniEvents = [
  { id: "e1", title: "FinTech Alumni Mixer 2026", date: "22 Aug 2026", location: "NUS SOC, Singapore", type: "Networking" },
  { id: "e2", title: "Mentoring Circle: Careers in Quant", date: "10 Sep 2026", location: "Virtual", type: "Mentoring" },
  { id: "e3", title: "Panel: The Future of Digital Assets", date: "5 Oct 2026", location: "Marina Bay, Singapore", type: "Panel" },
  { id: "e4", title: "DFT Hackathon Alumni Track", date: "15 Nov 2026", location: "NUS Innovation 4.0", type: "Hackathon" },
];

export const mentorRequests = [
  { id: "m1", student: "Sofia Rahman", topic: "Careers in FinTech Product", status: "pending", date: "2 days ago" },
  { id: "m2", student: "Daniel Lim", topic: "Transition to Quant", status: "accepted", date: "1 week ago" },
  { id: "m3", student: "Anonymous", topic: "Blockchain startup advice", status: "pending", date: "3 days ago" },
];

// ============ APPLICATION GUIDANCE DATA ============

export const applicationTimeline = [
  { phase: "Application Open", date: "15 Nov 2025", status: "completed", desc: "Applications open for August 2026 intake" },
  { phase: "Application Submission", date: "12 Feb 2026", status: "completed", desc: "Your application was submitted" },
  { phase: "Review Phase", date: "In progress", status: "current", desc: "Admissions committee reviewing applications" },
  { phase: "Interview", date: "If applicable", status: "upcoming", desc: "Shortlisted candidates may be invited for interview" },
  { phase: "Offer Release", date: "4-6 weeks", status: "upcoming", desc: "Decision notification after complete submission" },
];

export const applicationRequirements = [
  { category: "Academic Qualification", items: ["Bachelor's degree in relevant discipline", "Minimum B+ average (CAP 4.0+)", "GRE/GMAT recommended but not mandatory"], status: "verified" },
  { category: "Supporting Documents", items: ["Resume / CV", "Statement of Purpose (500-800 words)", "Passport copy"], status: "verified" },
  { category: "English Requirement", items: ["TOEFL iBT 90+ or IELTS 6.5+", "Waiver for English-medium degree holders"], status: "missing" },
  { category: "Personal Statement", items: ["FinTech motivation and career goals", "Relevant experience and skills", "Why NUS MSc DFT"], status: "verified" },
  { category: "Reference Letters", items: ["At least 1 academic reference", "2 references recommended for stronger application"], status: "pending" },
];

export const guidedPreparation = [
  { title: "Build Application Checklist", icon: "ListChecks", desc: "Generate a personalised checklist based on your profile and track missing items.", action: "Generate Checklist", prompt: "Generate my application checklist" },
  { title: "Eligibility Check", icon: "CheckCircle", desc: "AI-powered assessment of your qualifications against programme requirements.", action: "Check Now", prompt: "Am I eligible for MSc DFT?" },
  { title: "Document Preparation Guide", icon: "FileText", desc: "Step-by-step guidance for preparing each required document.", action: "View Guide", prompt: "Guide me through document preparation" },
  { title: "Application Tips", icon: "Lightbulb", desc: "Expert tips for writing a strong SOP, choosing referees, and highlighting FinTech awareness.", action: "View Tips", prompt: "Give me application tips" },
];

export const applicationFAQs = [
  { q: "Am I eligible with a non-computing degree?", a: "Yes, if your degree is in Finance, Engineering, Statistics, or Mathematics. A strong quantitative background is required. Programming experience is recommended but can be developed during the programme." },
  { q: "What documents are required?", a: "You need: personal particulars form, academic transcript (sealed), resume/CV, statement of purpose, at least 1 academic reference letter, English proficiency proof (if applicable), passport copy, and S$50 application fee." },
  { q: "How long is the programme?", a: "Full-time: 1.5-2 years. Part-time (local students only): 2.5-3 years. The programme requires 40 credits: 16 core + 16 electives + 8 capstone." },
  { q: "Can I study part-time?", a: "Yes, part-time study is available for local students, extending the programme to 2.5-3 years. International students must enrol full-time due to visa requirements." },
  { q: "When are the application deadlines?", a: "Applications open 15 November 2025. Round 1 deadline: 31 December 2025. Round 2 deadline: 15 March 2026. Decisions are released 4-6 weeks after complete submission." },
  { q: "Is GRE/GMAT required?", a: "GRE/GMAT is recommended but not mandatory. Strong quantitative scores can strengthen your application, especially if your undergraduate degree is not in a quantitative field." },
  { q: "Are scholarships available?", a: "Yes. NUS Graduate Scholarship, ASEAN Scholarship, and industry-sponsored FinTech scholarships are available on a competitive basis. Check the Scholarships page for eligibility criteria." },
  { q: "What is the application fee?", a: "The application fee is S$50, payable online during submission. The fee is non-refundable." },
];

// ============ ADMIN / STAFF DATA ============

export const adminKPIs = [
  { id: "inquiries", label: "Total Inquiries", value: 1284, delta: "+12.4%", trend: "up", icon: "MessageSquare" },
  { id: "automation", label: "Automation Rate", value: "78.3%", delta: "+3.1%", trend: "up", icon: "Cpu" },
  { id: "escalation", label: "Escalation Rate", value: "8.6%", delta: "-1.2%", trend: "down", icon: "AlertTriangle" },
  { id: "response", label: "Avg Response Time", value: "1.4s", delta: "-0.3s", trend: "down", icon: "Clock" },
  { id: "satisfaction", label: "Satisfaction Score", value: "4.6/5", delta: "+0.2", trend: "up", icon: "Star" },
  { id: "active", label: "Active Users", value: 642, delta: "+8.7%", trend: "up", icon: "Users" },
];

export const inquiryTrends = [
  { month: "Jan", inquiries: 142, automated: 108, escalated: 12 },
  { month: "Feb", inquiries: 168, automated: 132, escalated: 14 },
  { month: "Mar", inquiries: 210, automated: 165, escalated: 18 },
  { month: "Apr", inquiries: 195, automated: 156, escalated: 15 },
  { month: "May", inquiries: 234, automated: 189, escalated: 19 },
  { month: "Jun", inquiries: 268, automated: 218, escalated: 21 },
  { month: "Jul", inquiries: 245, automated: 201, escalated: 17 },
];

export const automationTrends = [
  { month: "Jan", rate: 71 },
  { month: "Feb", rate: 73 },
  { month: "Mar", rate: 74 },
  { month: "Apr", rate: 76 },
  { month: "May", rate: 77 },
  { month: "Jun", rate: 79 },
  { month: "Jul", rate: 78 },
];

export const escalationRoots = [
  { name: "Low Confidence", value: 34, color: "#3366ff" },
  { name: "Unknown Intent", value: 28, color: "#8b5cf6" },
  { name: "Policy Ambiguity", value: 18, color: "#22d3ee" },
  { name: "Emotional Content", value: 12, color: "#f59e0b" },
  { name: "Appeal Request", value: 8, color: "#ef4444" },
];

export const applicationFunnel = [
  { stage: "Inquiries", count: 1284 },
  { stage: "Started", count: 642 },
  { stage: "Submitted", count: 318 },
  { stage: "Reviewed", count: 204 },
  { stage: "Admitted", count: 96 },
  { stage: "Enrolled", count: 72 },
];

export const lifecycleDistribution = [
  { stage: "Prospective", count: 412 },
  { stage: "Applicant", count: 186 },
  { stage: "Admitted", count: 48 },
  { stage: "Enrolled", count: 94 },
  { stage: "Graduating", count: 26 },
  { stage: "Alumni", count: 198 },
];

// Escalation cases with full conversation history
export const escalations = [
  {
    id: "ESC-001",
    user: "Mei Ling Chen",
    email: "meiling.chen@example.com",
    role: "Applicant",
    category: "Low Confidence",
    confidence: 0.42,
    trigger: "Low Confidence",
    reason: "Ambiguous eligibility query — could not determine if user's degree qualifies",
    status: "open",
    assigned: null,
    assignedTeam: null,
    priority: "medium",
    notes: [],
    conversation: [
      { role: "user", text: "I have a degree in business analytics, can I apply?", time: "10:32 AM", confidence: null, intent: "Eligibility Check" },
      { role: "assistant", text: "A degree in business analytics may qualify if it includes sufficient quantitative coursework. Could you share your transcript?", time: "10:32 AM", confidence: 0.52, intent: "Eligibility Check", agent: "admissions" },
      { role: "user", text: "My degree had some statistics but mostly marketing courses", time: "10:33 AM", confidence: null, intent: "Eligibility Check" },
      { role: "assistant", text: "I'm not fully certain whether marketing-focused business analytics degrees meet our quantitative requirement. Let me connect you with an admissions officer for a definitive answer.", time: "10:33 AM", confidence: 0.42, intent: "Eligibility Check", agent: "admissions" },
    ],
  },
  {
    id: "ESC-002",
    user: "Arjun Kumar",
    email: "arjun.kumar@example.com",
    role: "Admitted",
    category: "Policy Ambiguity",
    confidence: 0.51,
    trigger: "Policy Ambiguity",
    reason: "Housing policy unclear for international admitted students",
    status: "assigned",
    assigned: "Dr. Lin Wei",
    assignedTeam: "Admissions",
    priority: "high",
    notes: [{ author: "Dr. Lin Wei", text: "Need to clarify on-campus housing allocation for international students. Checking with housing office.", time: "1h ago" }],
    conversation: [
      { role: "user", text: "What are my housing options as an international student?", time: "09:15 AM", confidence: null, intent: "Housing Info" },
      { role: "assistant", text: "NUS offers on-campus housing at UTown and PGPR. International students typically get priority allocation.", time: "09:15 AM", confidence: 0.68, intent: "Housing Info", agent: "supervisor" },
      { role: "user", text: "But I heard international students don't get guaranteed housing anymore. Is that true?", time: "09:16 AM", confidence: null, intent: "Housing Info" },
      { role: "assistant", text: "I'm not certain about the current housing guarantee policy for international students. Let me escalate this to get you accurate information.", time: "09:16 AM", confidence: 0.51, intent: "Housing Info", agent: "supervisor" },
    ],
  },
  {
    id: "ESC-003",
    user: "Sofia Rahman",
    email: "sofia.rahman@example.com",
    role: "Enrolled",
    category: "Unknown Intent",
    confidence: 0.38,
    trigger: "Unknown Intent",
    reason: "Cross-module credit transfer request — no matching policy found",
    status: "in-progress",
    assigned: "Prof. Ng",
    assignedTeam: "Academic",
    priority: "medium",
    notes: [{ author: "Prof. Ng", text: "Reviewing credit transfer policy for cross-faculty modules. Will respond by end of week.", time: "3h ago" }],
    conversation: [
      { role: "user", text: "Can I transfer credits from my exchange programme at ETH Zurich?", time: "02:45 PM", confidence: null, intent: "Credit Transfer" },
      { role: "assistant", text: "Credit transfers are possible for equivalent modules. Could you provide the syllabus?", time: "02:45 PM", confidence: 0.55, intent: "Credit Transfer", agent: "academic" },
      { role: "user", text: "It was a special topics course on DeFi protocols, not a standard module", time: "02:46 PM", confidence: null, intent: "Credit Transfer" },
      { role: "assistant", text: "I don't have a matching policy for special topics courses from exchange programmes. Escalating to the academic team for manual review.", time: "02:46 PM", confidence: 0.38, intent: "Credit Transfer", agent: "academic" },
    ],
  },
  {
    id: "ESC-004",
    user: "Daniel Lim",
    email: "daniel.lim@example.com",
    role: "Graduating",
    category: "Emotional Content",
    confidence: 0.29,
    trigger: "Emotional Content",
    reason: "Transcript delay frustration — user expressed significant distress",
    status: "in-progress",
    assigned: "Dr. Lin Wei",
    assignedTeam: "Admissions",
    priority: "urgent",
    notes: [
      { author: "Dr. Lin Wei", text: "User is very frustrated. Contacted registrar to expedite transcript. Following up tomorrow.", time: "5h ago" },
    ],
    conversation: [
      { role: "user", text: "I've been waiting 3 weeks for my transcript and nobody is responding to my emails!", time: "11:20 AM", confidence: null, intent: "Transcript Request" },
      { role: "assistant", text: "I understand your frustration. Let me check the status of your transcript request.", time: "11:20 AM", confidence: 0.61, intent: "Transcript Request", agent: "academic" },
      { role: "user", text: "This is unacceptable. I need it for a job application and the deadline is tomorrow. This is ruining my career!", time: "11:21 AM", confidence: null, intent: "Complaint" },
      { role: "assistant", text: "I hear your concern and I'm escalating this immediately to our admissions team who can expedite your request. Someone will contact you within the hour.", time: "11:21 AM", confidence: 0.29, intent: "Complaint", agent: "supervisor" },
    ],
  },
  {
    id: "ESC-005",
    user: "Priya Nair",
    email: "priya.nair@example.com",
    role: "Alumni",
    category: "Emotional Content",
    confidence: 0.61,
    trigger: "Emotional Content",
    reason: "Career transition stress — user expressed anxiety about industry change",
    status: "resolved",
    assigned: "Counsellor",
    assignedTeam: "Student Affairs",
    priority: "medium",
    notes: [
      { author: "Counsellor", text: "Had a 45-min session. User is transitioning from banking to startup. Provided career resources and mentor connection.", time: "1 day ago" },
    ],
    conversation: [
      { role: "user", text: "I'm thinking about leaving banking to start something in FinTech but I'm really scared", time: "03:30 PM", confidence: null, intent: "Career Guidance" },
      { role: "assistant", text: "Career transitions can be daunting. Many DFT alumni have successfully made similar moves.", time: "03:30 PM", confidence: 0.74, intent: "Career Guidance", agent: "career" },
      { role: "user", text: "What if I fail? I have a family to support and I can't afford to make a mistake", time: "03:31 PM", confidence: null, intent: "Career Guidance" },
      { role: "assistant", text: "Your concern is completely valid. I'd like to connect you with our career counsellor and an alumni mentor who made a similar transition. They can provide perspective and support.", time: "03:31 PM", confidence: 0.61, intent: "Career Guidance", agent: "career" },
    ],
  },
  {
    id: "ESC-006",
    user: "Wei Jie Tan",
    email: "weijie.tan@example.com",
    role: "Prospective",
    category: "Low Confidence",
    confidence: 0.45,
    trigger: "Unknown Intent",
    reason: "Comparison with non-NUS programme — no data available",
    status: "open",
    assigned: null,
    assignedTeam: null,
    priority: "low",
    notes: [],
    conversation: [
      { role: "user", text: "How does MSc DFT compare to the FinTech programme at SMU?", time: "01:10 PM", confidence: null, intent: "Programme Comparison" },
      { role: "assistant", text: "I can provide detailed comparisons with NUS programmes. For external institutions like SMU, I'd recommend checking their official programme pages alongside our curriculum details.", time: "01:10 PM", confidence: 0.45, intent: "Programme Comparison", agent: "knowledge" },
    ],
  },
];

export const escalationStatuses = ["open", "assigned", "in-progress", "waiting", "resolved", "closed"];
export const escalationTriggers = ["Low Confidence", "Emotional Content", "Sensitive Content", "Unknown Intent", "Policy Ambiguity", "Appeal Request"];
export const staffMembers = ["Dr. Lin Wei", "Prof. Ng", "Counsellor", "Admin Team", "Registrar"];
export const staffTeams = ["Admissions", "Academic", "Student Affairs", "Finance", "IT Support"];

// Knowledge Base with version control and analytics
export const knowledgeBase = [
  {
    id: "kb1",
    title: "MSc DFT Admission Requirements",
    category: "Admissions",
    status: "published",
    author: "Dr. Lin Wei",
    versions: [
      { version: "3.2", date: "13 Jul 2026", updatedBy: "Dr. Lin Wei", notes: "Updated GRE/GMAT recommendation wording" },
      { version: "3.1", date: "2 Jun 2026", updatedBy: "Admin Team", notes: "Added ASEAN Scholarship eligibility" },
      { version: "3.0", date: "15 Jan 2026", updatedBy: "Dr. Lin Wei", notes: "Major revision for 2026 intake requirements" },
      { version: "2.0", date: "10 Aug 2025", updatedBy: "Admin Team", notes: "New curriculum structure" },
      { version: "1.0", date: "1 Mar 2025", updatedBy: "Admin Team", notes: "Initial upload" },
    ],
    analytics: { usageCount: 842, lastAccessed: "2h ago", relatedQuestions: 124, confidencePerf: 0.94 },
  },
  {
    id: "kb2",
    title: "Application Deadlines & Rounds",
    category: "Admissions",
    status: "published",
    author: "Admin Team",
    versions: [
      { version: "2.0", date: "8 Jul 2026", updatedBy: "Admin Team", notes: "Updated admission deadline for Round 2" },
      { version: "1.1", date: "15 May 2026", updatedBy: "Admin Team", notes: "Added Round 2 dates" },
      { version: "1.0", date: "1 Nov 2025", updatedBy: "Admin Team", notes: "Initial upload" },
    ],
    analytics: { usageCount: 614, lastAccessed: "1h ago", relatedQuestions: 89, confidencePerf: 0.97 },
  },
  {
    id: "kb3",
    title: "Tuition Fees & Payment Schedule",
    category: "Policies",
    status: "published",
    author: "Finance Office",
    versions: [
      { version: "4.1", date: "12 Jul 2026", updatedBy: "Finance Office", notes: "Updated GST-inclusive fee structure" },
      { version: "4.0", date: "1 Jan 2026", updatedBy: "Finance Office", notes: "Annual fee revision" },
      { version: "3.0", date: "15 Aug 2025", updatedBy: "Finance Office", notes: "New payment schedule" },
      { version: "1.0", date: "1 Sep 2024", updatedBy: "Finance Office", notes: "Initial upload" },
    ],
    analytics: { usageCount: 456, lastAccessed: "3h ago", relatedQuestions: 67, confidencePerf: 0.96 },
  },
  {
    id: "kb4",
    title: "Module Registration Guide",
    category: "Courses",
    status: "review",
    author: "Registrar",
    versions: [
      { version: "2.5", date: "10 Jul 2026", updatedBy: "Registrar", notes: "Updated add/drop deadline dates" },
      { version: "2.0", date: "1 Aug 2025", updatedBy: "Registrar", notes: "New registration system guide" },
      { version: "1.0", date: "15 Jul 2024", updatedBy: "Registrar", notes: "Initial upload" },
    ],
    analytics: { usageCount: 389, lastAccessed: "5h ago", relatedQuestions: 52, confidencePerf: 0.91 },
  },
  {
    id: "kb5",
    title: "Scholarship Eligibility Criteria",
    category: "Scholarships",
    status: "published",
    author: "Admin Team",
    versions: [
      { version: "1.8", date: "8 Jul 2026", updatedBy: "Admin Team", notes: "Added FinTech Industry Scholarship" },
      { version: "1.0", date: "1 Oct 2025", updatedBy: "Admin Team", notes: "Initial upload" },
    ],
    analytics: { usageCount: 298, lastAccessed: "1 day ago", relatedQuestions: 43, confidencePerf: 0.93 },
  },
  {
    id: "kb6",
    title: "Capstone Project Guidelines",
    category: "Courses",
    status: "draft",
    author: "Prof. Ng",
    versions: [
      { version: "3.0", date: "14 Jul 2026", updatedBy: "Prof. Ng", notes: "New capstone rubric and timeline" },
      { version: "2.0", date: "1 Aug 2025", updatedBy: "Prof. Ng", notes: "Updated industry partner process" },
      { version: "1.0", date: "15 Jul 2024", updatedBy: "Prof. Ng", notes: "Initial upload" },
    ],
    analytics: { usageCount: 187, lastAccessed: "6h ago", relatedQuestions: 31, confidencePerf: 0.88 },
  },
  {
    id: "kb7",
    title: "Graduation Audit Process",
    category: "Policies",
    status: "published",
    author: "Registrar",
    versions: [
      { version: "2.2", date: "1 Jul 2026", updatedBy: "Registrar", notes: "Clarified residency requirement" },
      { version: "2.0", date: "1 Jan 2026", updatedBy: "Registrar", notes: "Updated audit checklist" },
      { version: "1.0", date: "15 Aug 2024", updatedBy: "Registrar", notes: "Initial upload" },
    ],
    analytics: { usageCount: 156, lastAccessed: "2 days ago", relatedQuestions: 24, confidencePerf: 0.95 },
  },
  {
    id: "kb8",
    title: "Alumni Networking Consent Policy",
    category: "Alumni",
    status: "review",
    author: "Dr. Lin Wei",
    versions: [
      { version: "1.0", date: "11 Jul 2026", updatedBy: "Dr. Lin Wei", notes: "Initial upload" },
    ],
    analytics: { usageCount: 72, lastAccessed: "4 days ago", relatedQuestions: 18, confidencePerf: 0.82 },
  },
];

export const kbCategories = ["Admissions", "Policies", "Courses", "Scholarships", "FAQs", "Alumni"];

export const activityLogs = [
  { id: "log1", actor: "Supervisor Agent", action: "Routed inquiry to Admissions Advisor", time: "2 min ago", type: "routing" },
  { id: "log2", actor: "Dr. Lin Wei", action: "Resolved escalation ESC-005", time: "15 min ago", type: "escalation" },
  { id: "log3", actor: "Career Navigator Agent", action: "Generated career recommendation for Sofia Rahman", time: "32 min ago", type: "ai" },
  { id: "log4", actor: "System", action: "Knowledge Base article 'Module Registration Guide' submitted for review", time: "1h ago", type: "kb" },
  { id: "log5", actor: "Prof. Ng", action: "Assigned ESC-003 to self", time: "2h ago", type: "escalation" },
  { id: "log6", actor: "Programme Knowledge Agent", action: "Answered 24 curriculum queries (96% confidence)", time: "3h ago", type: "ai" },
];

// Comprehensive student management data
export const studentsList = [
  {
    id: "s1", studentId: "A0285412H", name: "Sofia Rahman", email: "sofia.rahman@example.com", contact: "+65 9123 4567",
    country: "Singapore", role: "Enrolled", stage: "Study", programme: "MSc DFT", intake: "Aug 2025",
    status: "active", creditsCompleted: 24, creditsTotal: 40, progress: 60, cap: 4.6,
    lastLogin: "1h ago", chatSessions: 47, escalationsGenerated: 1, lastActive: "1h ago",
  },
  {
    id: "s2", studentId: "A0298321K", name: "Daniel Lim", email: "daniel.lim@example.com", contact: "+65 8234 5678",
    country: "Singapore", role: "Graduating", stage: "Graduate", programme: "MSc DFT", intake: "Aug 2024",
    status: "active", creditsCompleted: 32, creditsTotal: 40, progress: 80, cap: 4.4,
    lastLogin: "3h ago", chatSessions: 89, escalationsGenerated: 2, lastActive: "3h ago",
  },
  {
    id: "s3", studentId: "A0312456M", name: "Mei Ling Chen", email: "meiling.chen@example.com", contact: "+65 9345 6789",
    country: "Malaysia", role: "Applicant", stage: "Apply", programme: "MSc DFT", intake: "Aug 2026",
    status: "pending", creditsCompleted: 0, creditsTotal: 40, progress: 28, cap: null,
    lastLogin: "5h ago", chatSessions: 23, escalationsGenerated: 1, lastActive: "5h ago",
  },
  {
    id: "s4", studentId: "A0325678N", name: "Arjun Kumar", email: "arjun.kumar@example.com", contact: "+91 98765 43210",
    country: "India", role: "Admitted", stage: "Enroll", programme: "MSc DFT", intake: "Aug 2026",
    status: "active", creditsCompleted: 0, creditsTotal: 40, progress: 42, cap: null,
    lastLogin: "1 day ago", chatSessions: 31, escalationsGenerated: 1, lastActive: "1 day ago",
  },
  {
    id: "s5", studentId: "A0337890P", name: "Wei Jie Tan", email: "weijie.tan@example.com", contact: "+65 8456 7890",
    country: "Singapore", role: "Prospective", stage: "Discover", programme: "MSc DFT", intake: "Aug 2026",
    status: "active", creditsCompleted: 0, creditsTotal: 40, progress: 5, cap: null,
    lastLogin: "2h ago", chatSessions: 12, escalationsGenerated: 0, lastActive: "2h ago",
  },
  {
    id: "s6", studentId: "A0254321Q", name: "Priya Nair", email: "priya.nair@example.com", contact: "+65 9678 9012",
    country: "Singapore", role: "Alumni", stage: "Alumni", programme: "MSc DFT", intake: "Aug 2022",
    status: "active", creditsCompleted: 40, creditsTotal: 40, progress: 100, cap: 4.7,
    lastLogin: "4h ago", chatSessions: 56, escalationsGenerated: 1, lastActive: "4h ago",
  },
  {
    id: "s7", studentId: "A0345678R", name: "Hafiz Rahman", email: "hafiz.rahman@example.com", contact: "+65 8789 0123",
    country: "Singapore", role: "Enrolled", stage: "Study", programme: "MSc DFT", intake: "Aug 2025",
    status: "active", creditsCompleted: 20, creditsTotal: 40, progress: 50, cap: 4.2,
    lastLogin: "6h ago", chatSessions: 34, escalationsGenerated: 0, lastActive: "6h ago",
  },
  {
    id: "s8", studentId: "A0356789S", name: "Yuki Tanaka", email: "yuki.tanaka@example.com", contact: "+81 90 1234 5678",
    country: "Japan", role: "Applicant", stage: "Apply", programme: "MSc DFT", intake: "Aug 2026",
    status: "active", creditsCompleted: 0, creditsTotal: 40, progress: 60, cap: null,
    lastLogin: "8h ago", chatSessions: 18, escalationsGenerated: 0, lastActive: "8h ago",
  },
];

// Application management data with detailed tracking
export const applicationsList = [
  {
    id: "DFT-2026-0481", applicant: "Mei Ling Chen", email: "meiling.chen@example.com", nationality: "Malaysia",
    intake: "Aug 2026", status: "submitted", submittedDate: "12 Feb 2026", lastUpdated: "2h ago",
    progress: 60, missingDocuments: ["Academic Transcript (sealed)", "English Proficiency Proof"],
    documents: [
      { name: "Personal Particulars Form", status: "verified" },
      { name: "Academic Transcript (sealed)", status: "missing" },
      { name: "Resume / CV", status: "verified" },
      { name: "Statement of Purpose", status: "verified" },
      { name: "Academic Reference Letter", status: "pending" },
      { name: "English Proficiency Proof", status: "missing" },
      { name: "Passport Copy", status: "verified" },
      { name: "Application Fee (S$50)", status: "verified" },
    ],
  },
  {
    id: "DFT-2026-0512", applicant: "Yuki Tanaka", email: "yuki.tanaka@example.com", nationality: "Japan",
    intake: "Aug 2026", status: "under-review", submittedDate: "28 Feb 2026", lastUpdated: "5h ago",
    progress: 75, missingDocuments: [],
    documents: [
      { name: "Personal Particulars Form", status: "verified" },
      { name: "Academic Transcript (sealed)", status: "verified" },
      { name: "Resume / CV", status: "verified" },
      { name: "Statement of Purpose", status: "verified" },
      { name: "Academic Reference Letter", status: "verified" },
      { name: "English Proficiency Proof", status: "verified" },
      { name: "Passport Copy", status: "verified" },
      { name: "Application Fee (S$50)", status: "verified" },
    ],
  },
  {
    id: "DFT-2026-0498", applicant: "Arjun Kumar", email: "arjun.kumar@example.com", nationality: "India",
    intake: "Aug 2026", status: "offered", submittedDate: "15 Jan 2026", lastUpdated: "1 day ago",
    progress: 90, missingDocuments: [],
    documents: [
      { name: "Personal Particulars Form", status: "verified" },
      { name: "Academic Transcript (sealed)", status: "verified" },
      { name: "Resume / CV", status: "verified" },
      { name: "Statement of Purpose", status: "verified" },
      { name: "Academic Reference Letter", status: "verified" },
      { name: "English Proficiency Proof", status: "verified" },
      { name: "Passport Copy", status: "verified" },
      { name: "Application Fee (S$50)", status: "verified" },
    ],
  },
  {
    id: "DFT-2026-0523", applicant: "Liu Wei Ming", email: "liuweiming@example.com", nationality: "China",
    intake: "Aug 2026", status: "draft", submittedDate: null, lastUpdated: "3 days ago",
    progress: 15, missingDocuments: ["Academic Transcript (sealed)", "Resume / CV", "Statement of Purpose", "Academic Reference Letter", "English Proficiency Proof", "Passport Copy", "Application Fee (S$50)"],
    documents: [
      { name: "Personal Particulars Form", status: "verified" },
      { name: "Academic Transcript (sealed)", status: "missing" },
      { name: "Resume / CV", status: "missing" },
      { name: "Statement of Purpose", status: "missing" },
      { name: "Academic Reference Letter", status: "missing" },
      { name: "English Proficiency Proof", status: "missing" },
      { name: "Passport Copy", status: "missing" },
      { name: "Application Fee (S$50)", status: "missing" },
    ],
  },
  {
    id: "DFT-2026-0507", applicant: "Sarah Johnson", email: "sarah.johnson@example.com", nationality: "UK",
    intake: "Aug 2026", status: "interview", submittedDate: "20 Jan 2026", lastUpdated: "6h ago",
    progress: 85, missingDocuments: [],
    documents: [
      { name: "Personal Particulars Form", status: "verified" },
      { name: "Academic Transcript (sealed)", status: "verified" },
      { name: "Resume / CV", status: "verified" },
      { name: "Statement of Purpose", status: "verified" },
      { name: "Academic Reference Letter", status: "verified" },
      { name: "English Proficiency Proof", status: "verified" },
      { name: "Passport Copy", status: "verified" },
      { name: "Application Fee (S$50)", status: "verified" },
    ],
  },
  {
    id: "DFT-2026-0465", applicant: "Raj Patel", email: "raj.patel@example.com", nationality: "India",
    intake: "Aug 2026", status: "rejected", submittedDate: "10 Dec 2025", lastUpdated: "2 weeks ago",
    progress: 100, missingDocuments: [],
    documents: [
      { name: "Personal Particulars Form", status: "verified" },
      { name: "Academic Transcript (sealed)", status: "verified" },
      { name: "Resume / CV", status: "verified" },
      { name: "Statement of Purpose", status: "verified" },
      { name: "Academic Reference Letter", status: "verified" },
      { name: "English Proficiency Proof", status: "verified" },
      { name: "Passport Copy", status: "verified" },
      { name: "Application Fee (S$50)", status: "verified" },
    ],
  },
];

export const applicationStatuses = ["draft", "submitted", "under-review", "interview", "offered", "accepted", "rejected"];
