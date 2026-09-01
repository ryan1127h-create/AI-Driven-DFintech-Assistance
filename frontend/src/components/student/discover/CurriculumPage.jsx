import { useEffect, useState, useMemo } from 'react';
import { BookOpen, Layers, CalendarDays, Award, Building2 } from "lucide-react";
import { curriculum, tracks } from "../../../data/programme";
import { PageHeader, LoadingState } from "../PageParts";
import { Card, Badge } from "../../ui";
import { cn } from "../../../utils/cn";
import { getCourses } from "../../../../api";
import CourseModal from "../CourseModal";

const sectionAccent = {
  "Core Courses": {
    color: "brand",
    bar: "bg-brand-500",
    bg: "bg-brand-500/10",
    text: "text-brand-300"
  },

  "Vertical #1": {
    color: "royal",
    bar: "bg-royal-500",
    bg: "bg-royal-500/10",
    text: "text-royal-300"
  },

  "Vertical #2": {
    color: "cyan2",
    bar: "bg-cyan2-500",
    bg: "bg-cyan2-500/10",
    text: "text-cyan2-400"
  },

  "Vertical #3": {
    color: "emerald2",
    bar: "bg-emerald2-500",
    bg: "bg-emerald2-500/10",
    text: "text-emerald2-400"
  }
};

function getAccent(section) {
  if (section === "Core Courses")
    return sectionAccent["Core Courses"];

  if (section.startsWith("Vertical #1"))
    return sectionAccent["Vertical #1"];

  if (section.startsWith("Vertical #2"))
    return sectionAccent["Vertical #2"];

  if (section.startsWith("Vertical #3"))
    return sectionAccent["Vertical #3"];

  return sectionAccent["Core Courses"];
}

export function CurriculumPage() {
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");

  const programmeInfo = {
    totalUnits: 52,
    coreUnits: 28,
    electiveUnits: 12,
    capstoneUnits: 12,
    coreCourses: 7,
    electiveCourses: 3,
    capstoneProjects: 1
  };

  useEffect(() => {
    loadCourses();
  }, []);

  const loadCourses = async () => {
    try {
      const data = await getCourses();      
      setCourses(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const filteredCourses = useMemo(() => {
    if (!searchTerm.trim()) {
      return courses;
    }

    const keyword = searchTerm.toLowerCase();

    return courses.filter(
      (course) =>
        course.course_code?.toLowerCase().includes(keyword) ||
        course.title?.toLowerCase().includes(keyword) ||
        course.faculty?.toLowerCase().includes(keyword) ||
        course.department?.toLowerCase().includes(keyword)
    );
  }, [courses, searchTerm]);

  const groupedCourses = useMemo(() => {
    return filteredCourses.reduce((acc, course) => {
      const section = course.annex_section?.trim() || "Others";

      if (!acc[section]) {
        acc[section] = [];
      }

      acc[section].push(course);

      return acc;
    }, {});
  }, [filteredCourses]);

  const getOrder = (section) => {
    if (section === "Core Courses") return 1;
    if (section.startsWith("Vertical #1")) return 2;
    if (section.startsWith("Vertical #2")) return 3;
    if (section.startsWith("Vertical #3")) return 4;
    if (section === "Others") return 5;
    if (section.includes("Capstone")) return 6;

    return 999;
  };

  const sortedSections = Object.entries(groupedCourses).sort(
    ([a], [b]) => getOrder(a) - getOrder(b)
  );

  const summary = useMemo(() => {
    const totalUnits = filteredCourses.reduce(
      (sum, c) => sum + Number(c.module_credit || 0),
      0
    );

    const coreCourses = courses.filter(
      c => c.annex_section === "Core Courses"
    );

    const capstoneCourses = courses.filter(
      c => c.annex_section?.toLowerCase().includes("capstone")
    );

    const electiveCourses = courses.filter(
      c =>
        c.annex_section?.startsWith("Vertical #1") ||
        c.annex_section?.startsWith("Vertical #2") ||
        c.annex_section?.startsWith("Vertical #3")
    );

    return {
      totalUnits,
      coreCount: coreCourses.length,
      electiveCount: electiveCourses.length,
      capstoneCount: capstoneCourses.length
    };
  }, [courses]);

  if (loading) {
    return <div><LoadingState /></div>;
  }

  return (
    <div>
      <PageHeader
        icon={BookOpen}
        title="Courses"
        subtitle={`Total 52 Units • 28 Units Core Courses + 12 Units Electives + 12 Units Capstone Project`}
      />
     
      <div className="grid grid-cols-3 gap-3 mb-5">
        {[
          { label: "Core", value: 28, color: "bg-brand-500" },
          { label: "Electives", value: 12, color: "bg-royal-500" },
          { label: "Capstone", value: 12, color: "bg-emerald2-500" }
        ].map((s) => (
          <div
            key={s.label}
            className="relative overflow-hidden rounded-xl border border-app-soft p-4"
          >
            <div
              className={`absolute left-0 top-0 h-full w-1 ${s.color}`}
            />

            <p className="font-display text-2xl font-bold">
              {s.value}
            </p>

            <p className="text-xs text-app-muted">
              {s.label} Units
            </p>
          </div>
        ))}
      </div>

      <div className="mb-5">
        <div className="relative">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search course code, title, faculty or department..."
            className="
              w-full
              rounded-xl
              border border-app-soft
              bg-app-hover
              px-4 py-3
              text-app-primary
              placeholder:text-app-muted
              focus:outline-none
              focus:border-brand-500/50
              focus:ring-2 focus:ring-brand-500/20
              transition-all
            "
          />
        </div>
      </div>

      <div className="space-y-6">
        
        {/* {Object.entries(groupedCourses).map( */}
        {sortedSections.map(([section, sectionCourses]) => {
          const acc = getAccent(section);

          return (
            <Card
              key={section}
              className="relative overflow-hidden"
            >
              <div
                className={`absolute left-0 top-0 h-full w-1 ${acc.bar}`}
              />

              <div className="pl-3">
                <div className="flex items-center justify-between mb-3">
                  <h3
                    className={`font-display text-lg font-semibold ${acc.text}`}
                  >
                    {section}
                  </h3>

                  <Badge color="ink">
                    {sectionCourses.length} Modules
                  </Badge>
                </div>

                <div className="space-y-2">
                  {sectionCourses.map((course) => (
                    <div
                      key={course.course_code}
                      onClick={() => setSelectedCourse(course)}
                      className="cursor-pointer rounded-xl bg-app-hover px-3 py-3 hover:bg-app-soft transition"
                    >
                      <div className="flex items-center justify-between gap-3">

                        <div className="min-w-0 flex-1">

                          <div className="flex items-center gap-2">
                            <span
                              className={`font-mono text-xs ${acc.text}`}
                            >
                              {course.course_code}
                            </span>
                          </div>

                          <h4 className="mt-1 text-sm text-app-primary">
                            {course.title}
                          </h4>

                          <p className="mt-1 text-xs text-app-muted">
                            {course.faculty}
                          </p>

                        </div>

                        <Badge color="ink">
                          {course.module_credit} Units
                        </Badge>

                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Modal */}
      <CourseModal
        course={selectedCourse}
        onClose={() => setSelectedCourse(null)}
      />

    </div>
  );
}

// export function CurriculumPage() {
//   const [loading, setLoading] = useState(true);

//   useEffect(() => {
//     const t = setTimeout(() => setLoading(false), 1400);
//     return () => clearTimeout(t);
//   }, []);

//   if (loading) {
//     return (
//       <LoadingState
//         icon={BookOpen}
//         title="Loading Curriculum"
//         subtitle="Fetching programme modules from database…"
//         variant="skeleton"
//         rows={6}
//       />
//     );
//   }

//   return (
//     <div>
//       <PageHeader icon={BookOpen} title="Curriculum" subtitle={`${curriculum.totalCredits} credits · ${curriculum.breakdown}`} />

//       {/* Credit breakdown summary */}
//       <div className="grid grid-cols-3 gap-3 mb-5">
//         {[
//           { label: "Core", value: 16, color: "brand" },
//           { label: "Electives", value: 16, color: "royal" },
//           { label: "Capstone", value: 8, color: "emerald2" },
//         ].map((s) => {
//           const acc = trackAccent[s.color];
//           return (
//             <div key={s.label} className={cn("relative overflow-hidden rounded-xl p-4 border border-app-soft", acc.bg)}>
//               <div className={cn("absolute top-0 left-0 h-full w-1", acc.bar)} />
//               <p className={cn("font-display text-2xl font-bold", acc.text)}>{s.value}</p>
//               <p className="text-xs text-app-muted mt-0.5">{s.label} credits</p>
//             </div>
//           );
//         })}
//       </div>

//       {/* Specialisation tracks */}
//       <div className="mb-3">
//         <h3 className="font-display text-base font-semibold text-app-primary">Specialisation Tracks</h3>
//         <p className="text-sm text-app-muted mt-0.5">Choose electives aligned to a track — or mix across tracks.</p>
//       </div>
//       <div className="grid lg:grid-cols-2 gap-4 mb-5">
//         {tracks.map((t) => {
//           const acc = trackAccent[t.color] || trackAccent.brand;
//           return (
//             <Card key={t.name} className={cn("relative overflow-hidden group hover:border-app-input transition-all")}>
//               <div className={cn("absolute top-0 left-0 h-full w-1", acc.bar)} />
//               <div className="pl-3">
//                 <div className="flex items-center justify-between mb-2">
//                   <div className="flex items-center gap-2.5">
//                     <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", acc.bg, acc.text)}>
//                       <Layers size={16} />
//                     </div>
//                     <h4 className="font-display text-base font-semibold text-app-primary">{t.name}</h4>
//                   </div>
//                   <Badge color={t.color}>{t.courses.length} modules</Badge>
//                 </div>
//                 <p className="text-sm text-app-muted mb-3">{t.desc}</p>
//                 <div className="space-y-1.5">
//                   {t.courses.map((c) => {
//                     const mod = curriculum.electives.find((e) => e.code === c);
//                     return (
//                       <div key={c} className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 bg-app-hover hover:bg-app-soft transition group/course">
//                         <span className={cn("font-mono text-[11px] font-medium", acc.text)}>{c}</span>
//                         <span className="text-sm text-app-primary flex-1">{mod?.name}</span>
//                         <Badge color="ink" variant="soft">{mod?.credits || 4} cr</Badge>
//                       </div>
//                     );
//                   })}
//                 </div>
//               </div>
//             </Card>
//           );
//         })}
//       </div>

//       {/* Core modules */}
//       <div className="mb-3">
//         <h3 className="font-display text-base font-semibold text-app-primary">Core Modules</h3>
//         <p className="text-sm text-app-muted mt-0.5">All four core modules are compulsory for every student.</p>
//       </div>
//       <Card className="mb-5">
//         <div className="space-y-2">
//           {curriculum.core.map((m, i) => (
//             <div key={m.code} className="flex items-center gap-3 p-3.5 rounded-xl bg-app-hover hover:bg-app-soft transition group">
//               <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300 font-display text-sm font-bold flex-shrink-0">
//                 {i + 1}
//               </div>
//               <div className="flex-1 min-w-0">
//                 <div className="flex items-center gap-2">
//                   <span className="font-mono text-xs text-brand-300">{m.code}</span>
//                   <span className="text-app-faint text-xs">·</span>
//                   <span className="text-sm text-app-primary">{m.name}</span>
//                 </div>
//               </div>
//               <Badge color="ink">{m.credits} cr</Badge>
//               <div className="flex items-center gap-1.5 text-xs text-app-muted">
//                 <CalendarDays size={13} className="text-royal-300" />
//                 Semester {m.sem}
//               </div>
//             </div>
//           ))}
//         </div>
//       </Card>

//       {/* Capstone */}
//       <div className="mb-3">
//         <h3 className="font-display text-base font-semibold text-app-primary">Capstone Project</h3>
//         <p className="text-sm text-app-muted mt-0.5">A compulsory industry-sponsored project.</p>
//       </div>
//       <Card className="relative overflow-hidden border-royal-400/20">
//         <div className="absolute top-0 left-0 h-full w-1 bg-gradient-to-b from-royal-500 to-brand-500" />
//         <div className="pl-3">
//           <div className="flex items-start gap-4">
//             <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-royal-500/20 to-brand-500/20 text-royal-300 flex-shrink-0">
//               <Award size={24} />
//             </div>
//             <div className="flex-1">
//               <div className="flex items-center gap-2 mb-1">
//                 <h4 className="font-display text-lg font-semibold text-app-primary">{curriculum.capstone.name}</h4>
//                 <Badge color="royal">{curriculum.capstone.credits} credits</Badge>
//               </div>
//               <p className="text-sm text-app-secondary leading-relaxed">{curriculum.capstone.description}</p>
//             </div>
//           </div>
//           <div className="flex items-center gap-2 mt-4 pt-3 border-t border-app-subtle">
//             <Building2 size={14} className="text-royal-300" />
//             <span className="text-xs text-app-muted">Industry-partnered · Typically completed in final semester</span>
//           </div>
//         </div>
//       </Card>
//     </div>
//   );
// }
