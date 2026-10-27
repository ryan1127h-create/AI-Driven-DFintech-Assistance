/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft, BookOpen, Briefcase, ChevronDown, ExternalLink, GraduationCap, LogIn, MessageSquare, Quote, Sparkles,
  UserPlus, Wallet,
} from "lucide-react";
import { getProgrammeOverview } from "../../api";
import ThemeToggle from "../components/ThemeToggle";
import { Badge, Card } from "../components/ui";
import { useRole } from "../context/RoleContext";
import { formatDate } from "../utils/format";
import nusLogo from "../assets/nus_logo.png";

// The public programme page (backend app/domains/programme_page): for
// visitors and for prospective and applying students. Everything shown comes
// from the curated catalogue the assistant answers from; each section links
// its official sources. "Ask" buttons open the chat with the question filled
// in (signed in) or ask the visitor to sign in first.

const SECTIONS = [
  ["overview", "Overview"], ["curriculum", "Curriculum"], ["admissions", "Admissions"], ["fees", "Fees"],
  ["careers", "Careers"], ["alumni", "Alumni"],
];

function Section({ id, icon: Icon, title, subtitle, children, sources, ask, onAsk }) {
  return (
    <section id={id} className="scroll-mt-24 py-8 border-t border-app-subtle first:border-t-0">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-display text-xl font-semibold text-app-primary">
            <Icon size={18} className="text-brand-300" aria-hidden="true" /> {title}
          </h2>
          {subtitle && <p className="mt-1 text-sm text-app-secondary">{subtitle}</p>}
        </div>
        {ask && (
          <button type="button" className="btn-outline text-xs" onClick={() => onAsk(ask)}>
            <MessageSquare size={14} /> {ask}
          </button>
        )}
      </div>
      <div className="mt-5">{children}</div>
      {sources?.length > 0 && <Sources urls={sources} />}
    </section>
  );
}

function Sources({ urls }) {
  return (
    <p className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-app-muted">
      <span>Official sources:</span>
      {urls.map((url) => (
        <a key={url} href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline-offset-2 hover:underline hover:text-app-secondary">
          {new URL(url).pathname.replace(/\/$/, "").split("/").pop() || new URL(url).hostname}
          <ExternalLink size={11} aria-hidden="true" />
        </a>
      ))}
    </p>
  );
}

function CourseList({ courses }) {
  return (
    <ul className="divide-y divide-app-subtle rounded-xl border border-app-subtle">
      {courses.map((course) => (
        <li key={course.code}>
          <details className="group px-4 py-3">
            <summary className="flex cursor-pointer list-none items-center gap-3 text-sm">
              <span className="w-20 flex-shrink-0 font-mono text-xs text-app-muted">{course.code}</span>
              <span className="flex-1 text-app-primary">{course.title}</span>
              <span className="text-xs text-app-muted">{course.units} Units</span>
              {course.description && (
                <ChevronDown size={14} className="text-app-muted transition group-open:rotate-180" aria-hidden="true" />
              )}
            </summary>
            {course.description && <p className="mt-2 pl-[92px] text-xs leading-relaxed text-app-secondary">{course.description}</p>}
          </details>
        </li>
      ))}
    </ul>
  );
}

function Curriculum({ curriculum }) {
  const [vertical, setVertical] = useState(0);
  const chosen = curriculum.verticals[vertical];
  return (
    <div className="space-y-6">
      <div className="grid gap-3 md:grid-cols-3">
        {[
          ["28 Units", "Core courses", `All ${curriculum.core_mandatory.length} foundation courses, plus any 3 of ${curriculum.core_choice.length} FinTech core options`],
          ["12 Units", "Capstone", "A two-semester capstone project or internship — or three more electives instead"],
          ["12 Units", "Electives", `From ${curriculum.verticals.length} verticals, at level 4000 or 5000`],
        ].map(([units, label, text]) => (
          <Card key={label} className="!p-4">
            <p className="font-display text-2xl font-bold text-app-primary">{units}</p>
            <p className="text-sm font-medium text-app-primary">{label}</p>
            <p className="mt-1 text-xs text-app-secondary">{text}</p>
          </Card>
        ))}
      </div>

      <div>
        <h3 className="text-sm font-semibold text-app-primary">Foundation courses — take all</h3>
        <div className="mt-2"><CourseList courses={curriculum.core_mandatory} /></div>
      </div>
      <div>
        <h3 className="text-sm font-semibold text-app-primary">FinTech core options — choose any 3</h3>
        <div className="mt-2"><CourseList courses={curriculum.core_choice} /></div>
      </div>
      {curriculum.verticals.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-app-primary">Electives by vertical</h3>
          <div className="mt-2 flex flex-wrap gap-2" role="tablist" aria-label="Elective verticals">
            {curriculum.verticals.map((item, index) => (
              <button
                key={item.name} type="button" role="tab" aria-selected={index === vertical}
                onClick={() => setVertical(index)}
                className={`rounded-full border px-3 py-1 text-xs transition ${index === vertical ? "border-brand-400/40 bg-brand-500/15 text-app-primary" : "border-app-subtle text-app-secondary hover:text-app-primary"}`}
              >
                {item.name.replace(/^Vertical #\d+\.\s*/, "")} ({item.courses.length})
              </button>
            ))}
          </div>
          <div className="mt-3"><CourseList courses={chosen.courses} /></div>
        </div>
      )}
      {curriculum.skill_areas.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-app-primary">What you build</h3>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {curriculum.skill_areas.map((area) => (
              <div key={area.skill} className="rounded-xl border border-app-subtle px-4 py-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-app-primary">{area.skill}</span>
                  <Badge color={area.coverage === "Required core" ? "brand" : "ink"}>{area.coverage}</Badge>
                </div>
                <p className="mt-1 text-xs text-app-secondary">{area.courses.join(" · ")}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      <details className="rounded-xl border border-app-subtle px-4 py-3">
        <summary className="cursor-pointer text-sm font-medium text-app-primary">Graduation rules in full</summary>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-xs leading-relaxed text-app-secondary">
          {curriculum.rules.map((rule) => <li key={rule}>{rule}</li>)}
        </ul>
      </details>
    </div>
  );
}

export default function ProgrammePage() {
  const { user } = useRole();
  const navigate = useNavigate();
  const [page, setPage] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getProgrammeOverview().then(setPage).catch((err) => setError(err.message || "Unable to load the programme."));
  }, []);

  // Signed-in students get the question filled in on the chat; visitors sign up first.
  const ask = (question) => {
    if (user && user.role !== "admin") navigate(`/app?prompt=${encodeURIComponent(question)}`);
    else navigate("/register");
  };
  const studentSignedIn = user && user.role !== "admin";

  const programme = page?.programme;
  return (
    <div className="aurora-bg min-h-screen">
      <header className="sticky top-0 z-20 border-b border-app-subtle bg-app-glass backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 lg:px-8">
          <Link to={studentSignedIn ? "/app" : "/"} className="flex items-center gap-3">
            <img src={nusLogo} alt="NUS" className="h-9 w-auto rounded-lg" />
            <span className="hidden font-display font-bold text-app-primary sm:inline">MSc DFinTech</span>
          </Link>
          <nav className="hidden flex-1 justify-center gap-5 text-sm text-app-secondary md:flex" aria-label="Sections">
            {SECTIONS.map(([id, label]) => <a key={id} href={`#${id}`} className="hover:text-app-primary">{label}</a>)}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            {studentSignedIn ? (
              <button type="button" className="btn-outline text-xs" onClick={() => navigate("/app")}>
                <ArrowLeft size={14} /> Back to assistant
              </button>
            ) : (
              <>
                <button type="button" className="btn-outline text-xs" onClick={() => navigate("/login")}><LogIn size={14} /> Log in</button>
                <button type="button" className="btn-primary text-xs" onClick={() => navigate("/register")}><UserPlus size={14} /> Register</button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pb-16 lg:px-8">
        {error && <Card className="mt-8 border border-red-400/30 bg-red-500/10"><p className="text-sm text-red-300">{error}</p></Card>}
        {!page && !error && <p className="py-20 text-center text-sm text-app-muted">Loading the programme…</p>}

        {page && (
          <>
            <section id="overview" className="scroll-mt-24 pt-10 pb-8">
              <p className="text-xs font-medium uppercase tracking-wider text-brand-300">NUS School of Computing · {programme.intake_year} intake</p>
              <h1 className="mt-2 font-display text-3xl font-bold leading-tight text-app-primary lg:text-4xl">{programme.name}</h1>
              <p className="mt-3 max-w-3xl text-base text-app-secondary">{programme.summary}</p>
              <dl className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-3">
                {programme.key_facts.map((fact) => (
                  <div key={fact.label} className="rounded-xl border border-app-subtle bg-app-glass px-4 py-3">
                    <dt className="text-xs text-app-muted">{fact.label}</dt>
                    <dd className="mt-1 text-sm font-semibold text-app-primary">{fact.value}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-6 flex flex-wrap gap-2">
                <button type="button" className="btn-primary" onClick={() => ask("Am I eligible for MSc DFT?")}>
                  <Sparkles size={16} /> {studentSignedIn ? "Check my fit with the assistant" : "Create an account to check your fit"}
                </button>
                <a href={programme.official_url} target="_blank" rel="noreferrer" className="btn-outline">
                  Official programme page <ExternalLink size={14} />
                </a>
              </div>
              <p className="mt-4 text-xs text-app-muted">
                Facts verified against the official pages on {formatDate(programme.verified_at)}. The official pages always take precedence.
              </p>
            </section>

            <Section id="curriculum" icon={BookOpen} title="What you'll study" subtitle="52 Units: core courses, a capstone and electives."
              sources={page.curriculum.sources} ask="Which courses suit my career goal?" onAsk={ask}>
              <Curriculum curriculum={page.curriculum} />
            </Section>

            <Section id="admissions" icon={GraduationCap} title="Who can apply" sources={page.admissions.sources}
              subtitle={page.admissions.application_window
                ? `${page.admissions.application_window.label}: applications open ${formatDate(page.admissions.application_window.opens_on)} and close ${formatDate(page.admissions.application_window.closes_on)}.`
                : null}
              ask="Am I eligible for MSc DFT?" onAsk={ask}>
              <div className="grid gap-6 lg:grid-cols-2">
                <dl className="space-y-3">
                  {page.admissions.requirements.map((item) => (
                    <div key={item.label} className="rounded-xl border border-app-subtle px-4 py-3">
                      <dt className="text-xs text-app-muted">{item.label}</dt>
                      <dd className="mt-1 text-sm text-app-primary">{item.value}</dd>
                    </div>
                  ))}
                </dl>
                <div>
                  <h3 className="text-sm font-semibold text-app-primary">Documents you&apos;ll submit</h3>
                  <ul className="mt-2 space-y-2">
                    {page.admissions.documents.map((doc) => (
                      <li key={doc.label} className="rounded-xl border border-app-subtle px-4 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm text-app-primary">{doc.label}</span>
                          <Badge color={doc.required ? "brand" : "ink"}>{doc.required ? "Required" : "If applicable"}</Badge>
                        </div>
                        {doc.description && <p className="mt-1 text-xs text-app-secondary">{doc.description}</p>}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </Section>

            <Section id="fees" icon={Wallet} title="Fees and funding" sources={page.fees.sources}
              ask="How much are the fees, and what scholarships are there?" onAsk={ask}>
              <div className="grid gap-3 md:grid-cols-3">
                {page.fees.tuition.map((fee) => (
                  <Card key={fee.label} className="!p-4">
                    <p className="text-xs text-app-muted">{fee.label}{fee.includes_tax ? " (incl. GST)" : ""}</p>
                    <p className="mt-1 font-display text-2xl font-bold text-app-primary">{fee.amount}</p>
                    {fee.note && <p className="mt-1 text-xs text-app-secondary">{fee.note}</p>}
                  </Card>
                ))}
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {page.fees.funding.map((item) => (
                  <div key={item.name} className="rounded-xl border border-app-subtle px-4 py-3">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-sm font-medium text-app-primary">{item.name}</span>
                      <Badge color="ink">{item.kind}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-app-secondary">
                      {[item.amount, item.for && `for ${item.for}`].filter(Boolean).join(" · ") || "See the official page for the amount"}
                    </p>
                    {item.conditions && <p className="mt-1 text-xs text-app-muted">{item.conditions}</p>}
                  </div>
                ))}
              </div>
            </Section>

            <Section id="careers" icon={Briefcase} title="Where graduates go" subtitle="Role families the curriculum prepares you for, with the skills and courses behind each."
              ask="What jobs can I get after this programme?" onAsk={ask}>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {page.careers.map((role) => (
                  <Card key={role.name} className="!p-4">
                    <p className="text-sm font-semibold text-app-primary">{role.name}</p>
                    <p className="mt-1 text-xs text-app-secondary">{role.description}</p>
                    {role.skills.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {role.skills.map((skill) => <Badge key={skill} color="ink">{skill}</Badge>)}
                      </div>
                    )}
                    {role.courses.length > 0 && (
                      <p className="mt-2 text-xs text-app-muted">
                        Related courses: {role.courses.slice(0, 4).map((c) => c.code).join(", ")}{role.courses.length > 4 ? ` +${role.courses.length - 4} more` : ""}
                      </p>
                    )}
                  </Card>
                ))}
              </div>
            </Section>

            {page.stories.length > 0 && (
              <Section id="alumni" icon={Quote} title="Alumni stories"
                subtitle={studentSignedIn ? "Shared by alumni for prospective students." : "Shared by alumni for prospective students. Sign in to see who they are."}
                ask="Show me alumni with a path like mine" onAsk={ask}>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {page.stories.map((story) => (
                    <Card key={`${story.position}-${story.company}-${story.class_year}`} className="!p-4">
                      <p className="text-sm font-semibold text-app-primary">{story.name || story.position}</p>
                      <p className="text-xs text-app-secondary">
                        {[story.name ? story.position : null, story.company, story.class_year && `Class of ${story.class_year}`].filter(Boolean).join(" · ")}
                      </p>
                      <p className="mt-2 text-xs leading-relaxed text-app-secondary">{story.bio}</p>
                      {story.expertise.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">{story.expertise.map((e) => <Badge key={e} color="ink">{e}</Badge>)}</div>
                      )}
                    </Card>
                  ))}
                </div>
              </Section>
            )}
          </>
        )}
      </main>

      <footer className="px-6 py-5 text-center text-xs text-app-faint">
        NUS School of Computing · MSc in Digital Financial Technology
      </footer>
    </div>
  );
}
