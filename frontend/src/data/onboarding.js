// The profile welcome questionnaire: which steps each lifecycle stage sees
// and which profile fields each step asks. Labels and options come from the
// field dictionary (GET /profile/definitions); this file only decides the
// order, the grouping and a short hint where the dictionary's own
// description is written for the system rather than the user.

const STEPS = {
  goals: {
    title: "Your goals",
    subtitle: "So advice is tailored to where you want to go",
    fields: ["program_motivation", "career_goal_clarity", "target_role_families", "main_target_role", "target_markets"],
  },
  goalsStudy: {
    title: "Your goals",
    subtitle: "Course recommendations are planned around your main target role",
    fields: [
      "program_motivation", "career_goal_clarity", "target_role_families", "main_target_role", "target_markets",
      "job_search_timeline", "internship_status",
    ],
  },
  education: {
    title: "Education",
    subtitle: "Used for eligibility checks and course advice",
    fields: ["highest_degree", "degree_discipline_category", "english_medium_degree", "gpa_band", "prior_coursework"],
  },
  work: {
    title: "Work experience",
    subtitle: "Used for admission and career advice",
    fields: ["total_work_years", "employment_status", "function_experience", "seniority_level", "employer_sponsorship"],
  },
  background: {
    title: "Background",
    subtitle: "Used for course and career advice",
    fields: [
      "highest_degree", "degree_discipline_category", "prior_coursework", "total_work_years",
      "employment_status", "function_experience", "seniority_level",
    ],
  },
  skills: {
    title: "Skills",
    subtitle: "Rate yourself honestly, it only shapes the advice you get",
    fields: ["code_level", "math_stats_level", "finance_level", "ml_ai_level", "tech_stack"],
  },
  skillsStudy: {
    title: "Skills",
    subtitle: "Each level feeds into your course recommendations",
    fields: [
      "code_level", "math_stats_level", "finance_level", "ml_ai_level", "data_engineering_level",
      "blockchain_level", "tech_stack", "domain_knowledge", "certifications",
    ],
  },
  applying: {
    title: "Applying",
    subtitle: "Fees, eligibility and programme comparison",
    fields: [
      "residency_category", "admission_tests", "intake_term", "study_mode", "is_nus_alumnus",
      "track_interest", "decision_factors", "concerns",
    ],
  },
  starting: {
    title: "Getting ready to start",
    subtitle: "Shapes your first-semester course plan",
    fields: ["intake_term", "study_mode", "track_interest", "weekly_study_hours", "capstone_intent", "concerns"],
  },
  record: {
    title: "From your school record",
    subtitle: "What the school already has on file, so you don't need to enter it",
    record: true,
  },
  alumniCareer: {
    title: "Where you are now",
    subtitle: "So students looking for mentors can find the right alumni",
    fields: ["outcome_status", "current_position", "currently_hiring"],
  },
  givingBack: {
    title: "Giving back",
    subtitle: "How you'd like to support current students",
    fields: ["volunteer_roles"],
  },
  studyPlan: {
    title: "Study plan",
    subtitle: "Shapes your course load and capstone route",
    fields: ["weekly_study_hours", "capstone_intent"],
  },
};

const FLOWS = {
  prospect: ["goals", "education", "work", "skills", "applying"],
  applicant: ["goals", "education", "work", "skills", "applying"],
  admitted: ["goals", "education", "work", "skills", "starting"],
  current: ["record", "goalsStudy", "background", "skillsStudy", "studyPlan"],
  graduating: ["record", "goalsStudy", "background", "skillsStudy"],
  alumni: ["alumniCareer", "givingBack"],
};

export function onboardingSteps(stage) {
  return (FLOWS[stage] || FLOWS.prospect).map((key) => ({ key, ...STEPS[key] }));
}

// Fields shown to some of a flow's stages only.
const FIELD_STAGES = {
  program_motivation: ["prospect", "applicant", "admitted", "current"],
  internship_status: ["current"],
};

export const FIELD_HINTS = {
  target_role_families: "Pick every direction you're considering",
  main_target_role: "Course recommendations are planned around this one",
  english_medium_degree: "Decides whether you need an English test score",
  total_work_years: "Full-time roles only",
  residency_category: "Decides tuition subsidy eligibility",
  admission_tests: "GRE and GMAT stay valid for 5 years, TOEFL and IELTS for 2",
  is_nus_alumnus: "NUS alumni get a 20% tuition rebate",
  weekly_study_hours: "Outside class time",
  capstone_intent: "Part-time students are usually advised to take electives instead",
};

// Whether a field is shown, given the stage and the answers so far: target
// roles only once the user isn't still exploring, and a main target role only
// when there are several to choose between.
export function isFieldShown(key, stage, answers) {
  if (FIELD_STAGES[key] && !FIELD_STAGES[key].includes(stage)) return false;
  if (key === "target_role_families") return answers.career_goal_clarity !== "exploring";
  if (key === "main_target_role") {
    return answers.career_goal_clarity !== "exploring" && (answers.target_role_families || []).length > 1;
  }
  return true;
}

// Fields worth flagging as recommended: the dictionary's core (P0) tier,
// plus weekly study time for part-time students.
export function isRecommended(definition, answers) {
  if (definition.field_key === "weekly_study_hours") return answers.study_mode === "part_time";
  return definition.tier === "P0";
}

// The next three intake terms after today, e.g. ["AY2026/27 Sem2",
// "AY2027/28 Sem1", "AY2027/28 Sem2"]. Semester 1 of AY y/y+1 starts in
// August of y, semester 2 in January of y+1.
export function upcomingIntakeTerms(today = new Date()) {
  const terms = [];
  let year = today.getFullYear() - 1;
  while (terms.length < 3) {
    const ay = `AY${year}/${String((year + 1) % 100).padStart(2, "0")}`;
    if (new Date(year, 7, 1) > today) terms.push(`${ay} Sem1`);
    if (terms.length < 3 && new Date(year + 1, 0, 1) > today) terms.push(`${ay} Sem2`);
    year += 1;
  }
  return terms;
}
