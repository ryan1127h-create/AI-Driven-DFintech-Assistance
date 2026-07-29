// Data for the 3-step profile wizard converted from the HTML templates

export const applicationTypes = ["Full-time", "Part-time"];
export const degreeLevels = ["Bachelor", "Master", "PhD"];
export const fields = [
  "Computer Science",
  "Finance",
  "Engineering",
  "Statistics",
  "Mathematics",
  "Business Analytics",
  "Other",
];
export const proficiencies = ["Beginner", "Intermediate", "Advanced", "Expert"];
export const roles = [
  "FinTech Product Manager",
  "Quantitative Analyst",
  "Blockchain Engineer",
  "Data Scientist (Finance)",
  "Risk Technology Lead",
  "Digital Banking Strategist",
  "RegTech Consultant",
  "Founder / Startup",
];

export const materials = [
  { key: "transcript", label: "Academic Transcript (sealed)", required: "required", hint: "Official transcript in a sealed envelope from your institution." },
  { key: "resume", label: "Resume / CV", required: "required", hint: "Current resume listing education and work experience." },
  { key: "sop", label: "Statement of Purpose", required: "required", hint: "500-800 words on FinTech motivation and career goals." },
  { key: "reference", label: "Academic Reference Letter", required: "required", hint: "At least one academic reference; two recommended." },
  { key: "english", label: "English Proficiency Proof", required: "conditional", hint: "TOEFL iBT 90+ or IELTS 6.5+ (if non-English medium)." },
  { key: "passport", label: "Passport Copy", required: "required", hint: "Clear scan of the biographical data page." },
  { key: "fee", label: "Application Fee (S$50)", required: "required", hint: "Non-refundable fee payable online during submission." },
];

export const moduleCatalogue = [
  { code: "IS5452", name: "Digital Banking & Innovation", credits: 4 },
  { code: "IS5152", name: "FinTech Innovation & Smart Contracts", credits: 4 },
  { code: "CS5340", name: "Quantitative Reasoning for FinTech", credits: 4 },
  { code: "IS5462", name: "Risk Management Technologies", credits: 4 },
  { code: "CS5345", name: "Machine Learning for Finance", credits: 4 },
  { code: "CS6204", name: "Blockchain Technology", credits: 4 },
  { code: "CS6202", name: "Natural Language Processing", credits: 4 },
  { code: "IS5153", name: "AI in Finance & RegTech", credits: 4 },
  { code: "CS5424", name: "Big Data Systems for FinTech", credits: 4 },
  { code: "CS5242", name: "Distributed Systems", credits: 4 },
  { code: "CS5344", name: "Cloud Computing", credits: 4 },
  { code: "IS5451", name: "Programmable Money & CBDC", credits: 4 },
  { code: "BT5211", name: "Computational Finance", credits: 4 },
  { code: "FE5216", name: "Quantitative Methods in Finance", credits: 4 },
  { code: "CAPSTONE", name: "FinTech Capstone Project", credits: 12 },
];

export const compareProgrammeRows = [
  {
    program: "MSc DFT (NUS)",
    isTarget: true,
    facts: { focus: "AI + Finance + Systems", duration: "1.5-2 yrs", capstone: "Yes", tuition: "S$58,860" },
    source_url: "https://www.nus.edu.sg",
  },
  {
    program: "MSc Financial Engineering (NUS RM)",
    isTarget: false,
    facts: { focus: "Quant + Derivatives", duration: "1.5 yrs", capstone: "Yes", tuition: "S$60,000" },
    source_url: "https://www.nus.edu.sg",
  },
  {
    program: "MSc Computer Science (NUS)",
    isTarget: false,
    facts: { focus: "General Computing", duration: "1.5 yrs", capstone: "No", tuition: "S$54,000" },
    source_url: "https://www.nus.edu.sg",
  },
  {
    program: "MSc FinTech (NTU)",
    isTarget: false,
    facts: { focus: "Finance + Analytics", duration: "1 yr", capstone: "Yes", tuition: "S$52,000" },
    source_url: "https://www.ntu.edu.sg",
  },
];

export const compareDimensions = ["focus", "duration", "capstone", "tuition"];

// Generate a mock analysis result from the submitted profile
export function buildResults(profile) {
  const isApplicant = profile.lifecycle_stage === "applicant";
  const completedCodes = (profile.completed_modules || "")
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
  const completedModules = completedCodes
    .map((code) => moduleCatalogue.find((m) => m.code === code))
    .filter(Boolean);
  const unrecognized = completedCodes.filter(
    (code) => !moduleCatalogue.some((m) => m.code === code),
  );
  const completedCredits = completedModules.reduce((sum, m) => sum + m.credits, 0);

  const remainingPool = moduleCatalogue.filter(
    (m) => !completedCodes.includes(m.code) && m.code !== "CAPSTONE",
  );
  const recommended = remainingPool.slice(0, 4).map((m) => ({
    ...m,
    closesGaps: ["AI", "Systems"].slice(0, 2),
    verified: true,
  }));
  const plannedCredits = recommended.reduce((sum, m) => sum + m.credits, 0);
  const requiredTotal = 52;
  const remaining = Math.max(0, requiredTotal - completedCredits - plannedCredits);

  const skillGaps = [];
  if (profile.technical_proficiency === "Beginner" || profile.technical_proficiency === "Intermediate") {
    skillGaps.push("Programming", "Data Analysis");
  }
  if (profile.finance_knowledge === "Beginner" || profile.finance_knowledge === "Intermediate") {
    skillGaps.push("Financial Markets", "Risk Modelling");
  }
  if (skillGaps.length === 0) skillGaps.push("Advanced ML", "Distributed Systems");

  const studyPlans = {
    full_time: {
      term_credit_cap: 16,
      num_terms: 3,
      semesters: [
        { term: "Sem 1", credits: 16, modules: recommended.slice(0, 4) },
        { term: "Sem 2", credits: 12, modules: [{ code: "CAPSTONE", name: "Capstone", credits: 12 }] },
      ],
    },
    part_time: {
      term_credit_cap: 8,
      num_terms: 6,
      semesters: [
        { term: "Sem 1", credits: 8, modules: recommended.slice(0, 2) },
        { term: "Sem 2", credits: 8, modules: recommended.slice(2, 4) },
        { term: "Sem 3", credits: 12, modules: [{ code: "CAPSTONE", name: "Capstone", credits: 12 }] },
      ],
    },
  };

  const materialAnalysis = isApplicant
    ? materials.map((m) => ({
        ...m,
        status: profile.uploads?.[m.key] ? "submitted" : "missing",
        filename: profile.uploads?.[m.key]?.name || null,
        reason: m.hint,
      }))
    : null;

  const materialSummary = isApplicant
    ? {
        required_total: materials.length,
        submitted_required: Object.keys(profile.uploads || {}).length,
        missing_required: materials.length - Object.keys(profile.uploads || {}).length,
        rejected_required: 0,
        is_complete: Object.keys(profile.uploads || {}).length === materials.length,
      }
    : null;

  const checklistItems = isApplicant
    ? materials.map((m) => ({
        label: m.label,
        required: m.required === "required",
        status: profile.uploads?.[m.key] ? "verified" : "missing",
        status_label: profile.uploads?.[m.key] ? "Verified" : "Not uploaded",
        urgency: m.required === "required" && !profile.uploads?.[m.key] ? "urgent" : null,
        deadline: "15 Mar 2026",
        why: m.hint,
      }))
    : null;

  const tracker = isApplicant
    ? {
        status: "ok",
        speakable: "Your application is in the Review stage.",
        data: {
          human_status: "Application under review",
          next_step: "Submit missing documents before the Round 2 deadline.",
          demo_disclaimer: "Mock status for demonstration only.",
          demo_milestones: [
            { label: "Submitted", state: "done" },
            { label: "Document Verification", state: "done" },
            { label: "Review", state: "current" },
            { label: "Decision", state: "pending" },
            { label: "Offer", state: "pending" },
          ],
          outstanding_documents: materials
            .filter((m) => !profile.uploads?.[m.key])
            .map((m) => ({ label: m.label })),
          reminders: [
            { name: "Round 2 deadline", date: "15 Mar 2026", message: "Submit all required materials before this date." },
          ],
          escalation_packet: {
            suggested_team: "Admissions Office",
            reason: "Missing required documents",
            application_id: "DFT-2026-0481",
            current_status: "Review",
            official_enquiry_url: "https://www.nus.edu.sg",
            graduate_admission_system_url: "https://admissions.nus.edu.sg",
          },
        },
      }
    : null;

  const comparison = isApplicant
    ? {
        status: "ok",
        data: {
          dimensions: compareDimensions,
          facts_table: { rows: compareProgrammeRows },
          synthesis: {
            narrative: "MSc DFT offers the strongest AI-finance-systems integration among compared programmes.",
            best_for_you: "MSc DFT (NUS)",
            weights: { role_fit: 0.5, cost: 0.3, duration: 0.2 },
            rows: compareProgrammeRows.map((r) => ({
              program: r.program,
              weighted_score: r.isTarget ? 9.2 : 8.5,
            })),
          },
          disclaimer: "Comparison is based on publicly available information and is not a ranking.",
        },
      }
    : null;

  return {
    profile,
    material_analysis: materialAnalysis,
    material_summary: materialSummary,
    r: {
      checklist: checklistItems ? { status: "ok", speakable: "Checklist generated.", data: { items: checklistItems } } : undefined,
      tracker,
      comparison,
      recommendation: {
        status: "ok",
        data: {
          explanation: isApplicant
            ? "Based on your profile, here are recommended post-enrolment modules."
            : "Based on your completed modules and target roles, here are recommended next courses.",
          selection_source: "rule-based",
          recommended,
          already_completed: completedModules,
          unrecognized_completed: unrecognized,
          skill_gaps: skillGaps,
          prereq_warnings: [],
          graduation_progress: {
            completed_credits: completedCredits,
            planned_credits: plannedCredits,
            required: requiredTotal,
            remaining,
          },
          study_plans: studyPlans,
        },
      },
    },
  };
}
