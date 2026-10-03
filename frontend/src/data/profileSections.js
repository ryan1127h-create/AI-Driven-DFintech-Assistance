// How the profile page splits the field dictionary into pages (account
// settings, preferences and privacy live in the settings dialog): which pages
// each lifecycle stage gets, and the cards (and fields) on each page. A
// field shows when it applies to the user's stage or already has a value.
// A displayed field not listed here still appears: it falls into the page
// its dictionary module belongs to (MODULE_PAGES), in an "Other details"
// card, so a field added to the dictionary is never silently missing.

import {
  Briefcase,
  ClipboardList,
  Code2,
  GraduationCap,
  LayoutDashboard,
  School,
  Target,
  Trophy,
} from "lucide-react";
import { STAGE_CODES } from "../components/student/profile/ProfileFields";

const PAGES = {
  overview: { label: "Overview", icon: LayoutDashboard },
  goals: {
    label: "Goals",
    icon: Target,
    cards: [
      {
        title: "Your goals",
        fields: [
          "program_motivation", "career_goal_clarity", "target_role_families", "main_target_role",
          "target_markets", "job_search_timeline", "internship_status",
        ],
      },
      { title: "On your mind", fields: ["concerns"] },
    ],
  },
  studies: {
    label: "Studies",
    icon: School,
    cards: [
      {
        title: "From your school record",
        readOnly: true,
        fields: [
          "track_chosen", "expected_grad_term", "gpa_current_band", "credits",
          "current_modules", "completed_modules", "planned_modules", "graduation_term",
        ],
      },
      { title: "Study plan", fields: ["intake_term", "study_mode", "track_interest", "weekly_study_hours", "capstone_intent", "mentor_seeking"] },
      { title: "Living in Singapore", fields: ["current_region", "pass_status"] },
    ],
  },
  career: {
    label: "Career now",
    icon: Trophy,
    cards: [
      { title: "Where you are", fields: ["outcome_status", "current_position", "graduation_term"] },
      { title: "Giving back", fields: ["currently_hiring", "volunteer_roles"] },
    ],
  },
  education: {
    label: "Education",
    icon: GraduationCap,
    cards: [
      { title: "Degree", fields: ["highest_degree", "degree_discipline_category", "bachelor_grad_year", "english_medium_degree", "gpa_band"] },
      { title: "Coursework and research", fields: ["prior_coursework", "research_output"] },
    ],
  },
  work: {
    label: "Work",
    icon: Briefcase,
    cards: [
      { title: "Experience", fields: ["total_work_years", "employment_status", "function_experience", "seniority_level", "employer_sponsorship"] },
    ],
  },
  skills: {
    label: "Skills",
    icon: Code2,
    cards: [
      {
        title: "Self-rated levels",
        fields: ["code_level", "math_stats_level", "finance_level", "ml_ai_level", "data_engineering_level", "blockchain_level"],
      },
      { title: "Tools and credentials", fields: ["tech_stack", "domain_knowledge", "certifications", "languages"] },
    ],
  },
  application: {
    label: "Application",
    icon: ClipboardList,
    cards: [
      { title: "Eligibility and fees", fields: ["residency_category", "admission_tests", "is_nus_alumnus", "current_region", "pass_status"] },
      { title: "Your plans", fields: ["intake_term", "study_mode", "track_interest", "weekly_study_hours", "capstone_intent"] },
      { title: "Choosing a programme", fields: ["decision_factors", "competing_programs", "funding_interests", "referral_source"] },
      { title: "Application record", readOnly: true, fields: ["application_record"] },
    ],
  },
};

const STAGE_PAGES = {
  prospect: ["overview", "goals", "education", "work", "skills", "application"],
  applicant: ["overview", "goals", "education", "work", "skills", "application"],
  admitted: ["overview", "goals", "education", "work", "skills", "application"],
  current: ["overview", "studies", "goals", "education", "work", "skills"],
  graduating: ["overview", "studies", "goals", "education", "work", "skills"],
  alumni: ["overview", "career", "education", "work", "skills"],
};

// Shown in the page header rather than on a page.
const HEADER_FIELDS = new Set(["lifecycle_stage", "sub_stage"]);

// Dictionary module -> where an unlisted field goes (first page present).
const MODULE_PAGES = {
  A: ["application", "studies"], B: ["application", "studies", "skills"], C: ["education"], D: ["work"],
  E: ["skills"], F: ["goals"], G: ["goals"], H: ["application", "goals"], I: ["studies", "goals"],
  J: ["career", "goals"],
};

export function isRelevant(definition, stage, field) {
  const code = STAGE_CODES[stage];
  const hasValue = field && field.value !== null && field.value !== undefined
    && !(Array.isArray(field.value) && !field.value.length);
  return (code && definition.stages.includes(code)) || hasValue;
}

// [{key, label, icon, cards: [{title, readOnly, fields: [definition]}]}] for
// the stage, with only the fields this user should see.
export function profilePages(stage, definitions, fields) {
  const pageKeys = STAGE_PAGES[stage] || STAGE_PAGES.prospect;
  const shown = definitions.filter((d) => !HEADER_FIELDS.has(d.field_key) && isRelevant(d, stage, fields[d.field_key]));
  const byKey = Object.fromEntries(shown.map((d) => [d.field_key, d]));
  const placed = new Set();

  const pages = pageKeys.map((key) => {
    const page = PAGES[key];
    const cards = (page.cards || []).map((card) => {
      const cardFields = card.fields.filter((k) => byKey[k] && !placed.has(k)).map((k) => byKey[k]);
      cardFields.forEach((d) => placed.add(d.field_key));
      return { ...card, fields: cardFields };
    });
    return { key, label: page.label, icon: page.icon, cards };
  });

  const contentPages = pages.filter((p) => PAGES[p.key].cards);
  for (const definition of shown) {
    if (placed.has(definition.field_key)) continue;
    const target = (MODULE_PAGES[definition.module] || [])
      .map((k) => contentPages.find((p) => p.key === k))
      .find(Boolean) || contentPages[0];
    let other = target.cards.find((c) => c.other);
    if (!other) {
      other = { title: "Other details", other: true, fields: [] };
      target.cards.push(other);
    }
    other.fields.push(definition);
  }

  return pages.map((page) => ({ ...page, cards: page.cards.filter((c) => c.fields.length) }));
}
