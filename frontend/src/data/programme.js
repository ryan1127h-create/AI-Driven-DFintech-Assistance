// Real NUS MSc Digital Financial Technology programme data
// Source: NUS MSc DFT official programme information

export const programme = {
  name: "MSc in Digital Financial Technology",
  short: "MSc DFT",
  school: "NUS School of Computing",
  faculty: "National University of Singapore",
  duration: "1.5 - 2 years (Full-time)",
  intake: "August (Semester 1)",
  tuition: "S$58,860 (full programme, inclusive of GST)",
  minScore: "B+ average / CAP 4.0+",
  applicationFee: "S$50",
  overview:
    "The MSc in Digital Financial Technology (DFT) is designed to meet the growing demand for professionals skilled in both finance and technology. The programme integrates artificial intelligence, data analytics, and financial technology to prepare graduates for leadership roles in the FinTech industry.",
  highlights: [
    "Interdisciplinary curriculum spanning AI, finance, and computing",
    "Industry-aligned FinTech specialisation tracks",
    "Capstone project with industry partners",
    "Access to NUS FinTech Lab and research ecosystem",
    "Strong career outcomes in banking, payments, and digital assets",
  ],
  eligibility: [
    "Bachelor's degree in a relevant discipline (Computing, Finance, Engineering, Statistics, Mathematics)",
    "Strong quantitative and programming background",
    "TOEFL iBT 90+ / IELTS 6.5+ (for non-English medium graduates)",
    "GRE/GMAT recommended but not mandatory",
  ],
  deadlines: {
    open: "15 November 2025",
    close: "15 March 2026",
    round1: "31 December 2025",
    round2: "15 March 2026",
  },
};

export const curriculum = {
  core: [
    { code: "IS5452", name: "Digital Banking & Innovation", credits: 4, sem: 1 },
    { code: "IS5152", name: "FinTech Innovation & Smart Contracts", credits: 4, sem: 1 },
    { code: "CS5340", name: "Quantitative Reasoning for FinTech", credits: 4, sem: 1 },
    { code: "IS5462", name: "Risk Management Technologies", credits: 4, sem: 2 },
  ],
  electives: [
    { code: "CS5242", name: "Distributed Systems", credits: 4, track: "Systems" },
    { code: "CS5344", name: "Cloud Computing", credits: 4, track: "Systems" },
    { code: "CS6204", name: "Blockchain Technology", credits: 4, track: "Blockchain" },
    { code: "IS5451", name: "Programmable Money & Central Bank Digital Currencies", credits: 4, track: "Blockchain" },
    { code: "CS5424", name: "Big Data Systems for FinTech", credits: 4, track: "Data" },
    { code: "CS5345", name: "Machine Learning for Finance", credits: 4, track: "AI" },
    { code: "CS6202", name: "Natural Language Processing", credits: 4, track: "AI" },
    { code: "IS5153", name: "AI in Finance & RegTech", credits: 4, track: "AI" },
    { code: "BT5211", name: "Computational Finance", credits: 4, track: "Finance" },
    { code: "FE5216", name: "Quantitative Methods in Finance", credits: 4, track: "Finance" },
  ],
  capstone: {
    name: "FinTech Capstone Project",
    credits: 8,
    description: "Industry-sponsored project solving a real FinTech problem with a partner organisation.",
  },
  totalCredits: 40,
  breakdown: "16 credits core + 16 credits electives + 8 credits capstone",
};

export const careerOutcomes = [
  { role: "FinTech Product Manager", share: 18, salary: "$110-160k" },
  { role: "Quantitative Analyst", share: 16, salary: "$95-140k" },
  { role: "Blockchain Engineer", share: 14, salary: "$100-150k" },
  { role: "Data Scientist (Finance)", share: 13, salary: "$105-155k" },
  { role: "Risk Technology Lead", share: 10, salary: "$120-170k" },
  { role: "Digital Banking Strategist", share: 9, salary: "$90-130k" },
  { role: "RegTech Consultant", share: 8, salary: "$95-135k" },
  { role: "Founder / Startup", share: 7, salary: "Variable" },
  { role: "Further PhD Study", share: 5, salary: "Stipend" },
];

export const compareProgrammes = [
  {
    name: "MSc DFT (NUS)",
    focus: "AI + Finance + Systems",
    duration: "1.5-2 yrs",
    capstone: true,
    industry: "FinTech-first",
    score: 9.2,
  },
  {
    name: "MSc Financial Engineering (NUS RM)",
    focus: "Quant + Derivatives",
    duration: "1.5 yrs",
    capstone: true,
    industry: "Banking/Trading",
    score: 8.9,
  },
  {
    name: "MSc Computer Science (NUS)",
    focus: "General Computing",
    duration: "1.5 yrs",
    capstone: false,
    industry: "Broad Tech",
    score: 9.0,
  },
  {
    name: "MSc FinTech (NTU)",
    focus: "Finance + Analytics",
    duration: "1 yr",
    capstone: true,
    industry: "FinTech",
    score: 8.5,
  },
];

export const faqs = [
  {
    q: "What is the minimum academic requirement?",
    a: "A Bachelor's degree in a relevant discipline with at least a B+ average (CAP 4.0+). Relevant disciplines include Computing, Finance, Engineering, Statistics, and Mathematics.",
  },
  {
    q: "Is work experience required?",
    a: "Work experience is not mandatory but is viewed favourably, especially for applicants whose prior degree is not in a quantitative field.",
  },
  {
    q: "Do I need to submit GRE or GMAT scores?",
    a: "GRE/GMAT is recommended but not mandatory. Strong quantitative scores can strengthen your application.",
  },
  {
    q: "What is the English language requirement?",
    a: "Applicants from non-English medium institutions need TOEFL iBT 90+ or IELTS 6.5+. Waivers apply for degrees from English-medium universities.",
  },
  {
    q: "Can I study part-time?",
    a: "Yes, a part-time option is available for local students, extending the programme to 2.5-3 years.",
  },
  {
    q: "Are scholarships available?",
    a: "Yes. NUS Graduate Scholarship, ASEAN Scholarship, and industry-sponsored FinTech scholarships are available on a competitive basis.",
  },
  {
    q: "What is the programme fee?",
    a: "Approximately S$58,860 for the full programme, inclusive of GST. Fees are payable per semester.",
  },
  {
    q: "Is the capstone project mandatory?",
    a: "Yes, the 8-credit FinTech Capstone Project is a compulsory component, typically completed with an industry partner.",
  },
];

export const tracks = [
  {
    name: "AI & Machine Learning",
    color: "brand",
    courses: ["CS5345", "CS6202", "IS5153"],
    desc: "Build intelligent systems for credit, fraud, and trading.",
  },
  {
    name: "Blockchain & Digital Assets",
    color: "royal",
    courses: ["CS6204", "IS5451"],
    desc: "Design programmable money, DeFi, and CBDC infrastructure.",
  },
  {
    name: "Systems & Cloud",
    color: "cyan2",
    courses: ["CS5242", "CS5344", "CS5424"],
    desc: "Engineer scalable, resilient FinTech platforms.",
  },
  {
    name: "Quantitative Finance",
    color: "emerald2",
    courses: ["BT5211", "FE5216"],
    desc: "Apply advanced mathematics to pricing and risk.",
  },
];
