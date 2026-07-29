// User roles, profiles, and lifecycle stages

export const ROLES = {
  PROSPECTIVE: "prospective",
  APPLICANT: "applicant",
  ADMITTED: "admitted",
  ENROLLED: "enrolled",
  GRADUATING: "graduating",
  ALUMNI: "alumni",
  STAFF: "staff",
};

export const ROLE_META = {
  prospective: { label: "Prospective Student", stage: "Discover", color: "brand", icon: "Compass" },
  applicant: { label: "Applicant", stage: "Apply", color: "royal", icon: "FileText" },
  admitted: { label: "Admitted Student", stage: "Enroll", color: "cyan2", icon: "CheckCircle" },
  enrolled: { label: "Enrolled Student", stage: "Study", color: "emerald2", icon: "BookOpen" },
  graduating: { label: "Graduating Student", stage: "Graduate", color: "brand", icon: "GraduationCap" },
  alumni: { label: "Alumni", stage: "Alumni", color: "royal", icon: "Users" },
  staff: { label: "Staff / Admin", stage: "Admin", color: "ink", icon: "ShieldCheck" },
};

export const LIFECYCLE_STAGES = ["Discover", "Apply", "Enroll", "Study", "Graduate", "Alumni"];

export const demoUsers = {
  prospective: {
    name: "Wei Jie Tan",
    email: "weijie.tan@example.com",
    role: "prospective",
    avatar: "WT",
    headline: "Exploring MSc DFT",
    progress: 5,
  },
  applicant: {
    name: "Mei Ling Chen",
    email: "meiling.chen@example.com",
    role: "applicant",
    avatar: "MC",
    headline: "Application in review",
    progress: 28,
  },
  admitted: {
    name: "Arjun Kumar",
    email: "arjun.kumar@example.com",
    role: "admitted",
    avatar: "AK",
    headline: "Offer accepted — onboarding",
    progress: 42,
  },
  enrolled: {
    name: "Sofia Rahman",
    email: "sofia.rahman@example.com",
    role: "enrolled",
    avatar: "SR",
    headline: "Year 1, Semester 2",
    progress: 72,
  },
  graduating: {
    name: "Daniel Lim",
    email: "daniel.lim@example.com",
    role: "graduating",
    avatar: "DL",
    headline: "Final semester",
    progress: 94,
  },
  alumni: {
    name: "Priya Nair",
    email: "priya.nair@example.com",
    role: "alumni",
    avatar: "PN",
    headline: "Class of 2023 · FinTech PM",
    progress: 100,
  },
  staff: {
    name: "Dr. Lin Wei",
    email: "lin.wei@nus.edu.sg",
    role: "staff",
    avatar: "LW",
    headline: "Programme Administrator",
    progress: 0,
  },
};
