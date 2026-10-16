"""
S5 — lays the student's gaps for one role onto dated phases. Pure code,
no LLM, no I/O.

Phases, each only when it still lies ahead:

    before_programme       today -> programme start (not yet enrolled)
    build_up               -> Capstone applications open
    capstone_applications  applications open -> close (no internship secured yet)
    capstone_internship    internship start -> end (after applications, or secured)
    job_search             by the job-search timeline, around graduation

Capstone phases only appear for a student doing (or undecided about) the
internship Capstone who hasn't completed it. The gaps are worked on
earliest first: readiness areas and unknown-skill evidence in the first
phase, then up to policy.tuning.MAX_GAPS_PER_PHASE skill gaps per phase
(missing before partial, the weakest first); any left over join the
first phase rather than being dropped.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.domains.specialist.career_planning.models import (
    Action,
    Milestone,
    Phase,
    ReadinessGap,
    Roadmap,
    RoadmapContext,
    SkillAssessment,
)
from app.domains.specialist.career_planning.policy import actions as wording
from app.domains.specialist.career_planning.policy import calendar, tuning
from app.domains.specialist.career_planning.stages.s5_roadmap.anchors import Anchors, resolve

_NO_INTERNSHIP_INTENTS = frozenset({"electives_instead", "capstone_research"})
_ANY_MARKET = "ANY"

_PHASE_NAMES = {
    "before_programme": "Before the programme",
    "build_up": "Build role evidence",
    "capstone_applications": "Capstone internship applications",
    "capstone_internship": "Capstone internship",
    "job_search": "Job search",
}

_NOTES = {
    "projected": (
        "The {year} Capstone dates repeat the {reference} cycle's published dates; the school publishes each "
        "year's dates, so check them when they come out."
    ),
    "graduation_estimated": (
        "Your expected graduation term isn't on file, so the roadmap assumes full-time study ending {term}; "
        "part-time study takes longer."
    ),
    "electives_instead": (
        "You plan to take electives instead of the Capstone, so the roadmap has no internship phase; "
        "internships can still be found through NUS TalentConnect."
    ),
    "capstone_research": (
        "Your Capstone is a research project, whose dates follow your supervisor's plan; it isn't laid out "
        "here, but it is a strong source of role evidence."
    ),
    "capstone_completed": "Your Capstone internship is completed, so the roadmap starts from the job search.",
    "capstone_in_singapore": (
        "The Capstone internship must be located in Singapore, which isn't among your preferred job markets."
    ),
    "no_market_data": (
        "The programme's information covers the Singapore Capstone and NUS career channels; it has no "
        "job-market data for {markets}."
    ),
    "later_search": "You plan to look for work a year or more after graduating, so the roadmap stops at graduation.",
    "not_job_seeking": "You aren't looking for work, so the roadmap has no job-search phase.",
    "during_programme": (
        "Taking on part-time work during a full-time programme is generally not encouraged, and Student's Pass "
        "holders must follow ICA's rules for working."
    ),
}


def _add_months(day: date, months: int) -> date:
    """The first of the month `months` after `day`'s month."""
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _milestone(kind, on: date, label: str, projected: bool = False) -> Milestone:
    return Milestone(kind=kind, on=on, label=label, projected=projected)


class _GapQueue:
    """Hands out the gap actions, earliest phase first."""

    def __init__(self, gaps: tuple[SkillAssessment, ...], readiness: tuple[ReadinessGap, ...], pre: bool):
        order = {"missing": 0, "partial": 1}
        work = sorted((g for g in gaps if g.status in order), key=lambda g: (order[g.status], g.points))
        self.skills = [Action("skill", wording.SKILL_ACTIONS[g.skill], (g.skill,)) for g in work]
        self.first: list[Action] = []
        # Readiness areas matter before the programme starts; once in it,
        # the role's own gaps say what's still needed.
        if pre:
            self.first += [
                Action("readiness", wording.READINESS_ACTIONS[r.area].format(required=r.required), (r.area,))
                for r in readiness
            ]
        unknown = tuple(g.skill for g in gaps if g.status == "unknown")
        if unknown:
            names = ", ".join(s.replace("_", " ") for s in unknown)
            self.first.append(Action("evidence", wording.EVIDENCE_ACTION.format(skills=names), unknown))
        self.started = False

    def take(self) -> list[Action]:
        taken = self.skills[: tuning.MAX_GAPS_PER_PHASE]
        self.skills = self.skills[tuning.MAX_GAPS_PER_PHASE:]
        if not self.started:
            self.started = True
            taken = self.first + taken
        return taken

    def has_work(self) -> bool:
        return bool(self.skills or (not self.started and self.first))

    def leftover(self) -> list[Action]:
        rest = ([] if self.started else self.first) + self.skills
        self.skills, self.started = [], True
        return rest


def _phase(kind, start: date, end: date, actions, milestones=()) -> Phase:
    return Phase(kind=kind, name=_PHASE_NAMES[kind], start=start, end=end,
                 actions=tuple(actions), milestones=tuple(milestones))


def _capstone_phases(ctx: RoadmapContext, anchors: Anchors, queue: _GapQueue, cursor: date) -> list[Phase]:
    cycle = anchors.cycle
    projected = cycle.projected
    phases = []
    if ctx.internship_status != "secured" and cursor <= cycle.applications_close:
        milestones = [
            _milestone("capstone_applications_open", cycle.applications_open,
                       "Capstone internship applications open", projected),
            _milestone("capstone_applications_close", cycle.applications_close,
                       "Capstone internship applications close", projected),
            _milestone("capstone_offers_by", cycle.offers_by, "Companies make Capstone offers by", projected),
        ]
        milestones = [m for m in milestones if m.on >= cursor]
        actions = [Action("capstone", wording.CAPSTONE_APPLICATION_ACTION), *queue.take()]
        phases.append(_phase("capstone_applications", max(cursor, cycle.applications_open),
                             cycle.applications_close, actions, milestones))
    # Once applications have closed, an internship is only planned for
    # when the student says one is secured.
    if cursor <= cycle.internship_end and (phases or ctx.internship_status == "secured"):
        milestones = [
            _milestone("internship_start", cycle.internship_start, "Capstone internship starts", projected),
            _milestone("internship_end", cycle.internship_end, "Capstone internship ends", projected),
        ]
        actions = [Action("capstone", wording.CAPSTONE_INTERNSHIP_ACTION), *queue.take()]
        phases.append(_phase("capstone_internship", max(cursor, cycle.internship_start), cycle.internship_end,
                             actions, [m for m in milestones if m.on >= cursor]))
    return phases


def _job_search_phase(ctx: RoadmapContext, anchors: Anchors, queue: _GapQueue, cursor: date) -> Phase | None:
    graduation_end = anchors.graduation.end
    if ctx.job_search_timeline == "during_program":
        start, end = cursor, graduation_end
    else:
        start = max(cursor, _add_months(graduation_end, -tuning.JOB_SEARCH_LEAD_MONTHS + 1))
        end = _add_months(graduation_end, tuning.JOB_SEARCH_TAIL_MONTHS + 1) - timedelta(days=1)
    actions = [Action("job_search", text) for text in wording.JOB_SEARCH_ACTIONS] + queue.take()
    graduation = _milestone("graduation", graduation_end, f"Graduation ({anchors.graduation.label})")
    return _phase("job_search", start, end, actions, [graduation] if graduation_end >= cursor else [])


def _market_notes(ctx: RoadmapContext, with_capstone: bool) -> list[str]:
    markets = [m for m in ctx.target_markets if m != _ANY_MARKET]
    if not markets or _ANY_MARKET in ctx.target_markets:
        return []
    notes = []
    if with_capstone and calendar.CAPSTONE_LOCATION not in markets:
        notes.append(_NOTES["capstone_in_singapore"])
    others = [m for m in markets if m != calendar.CAPSTONE_LOCATION]
    if others:
        notes.append(_NOTES["no_market_data"].format(markets=", ".join(others)))
    return notes


def build_roadmap(
    ctx: RoadmapContext,
    gaps: tuple[SkillAssessment, ...],
    readiness: tuple[ReadinessGap, ...] = (),
) -> Roadmap:
    """`gaps`: the target role's graded skills (met ones are skipped)."""
    anchors = resolve(ctx)
    queue = _GapQueue(gaps, readiness, anchors.pre_programme)
    notes: list[str] = []
    phases: list[Phase] = []
    cursor = ctx.today

    if anchors.pre_programme:
        start = anchors.programme_start
        phases.append(_phase("before_programme", cursor, start - timedelta(days=1), queue.take(),
                             [_milestone("programme_start", start, "Programme starts")]))
        cursor = start

    with_capstone = ctx.capstone_intent not in _NO_INTERNSHIP_INTENTS and ctx.internship_status != "completed"
    cycle = anchors.cycle
    if with_capstone and cursor < cycle.applications_open and queue.has_work():
        phases.append(_phase("build_up", cursor, cycle.applications_open - timedelta(days=1), queue.take()))
    if with_capstone:
        capstone = _capstone_phases(ctx, anchors, queue, cursor)
        phases += capstone
        if capstone and cycle.projected:
            notes.append(_NOTES["projected"].format(year=cycle.year, reference=calendar.REFERENCE_CYCLE_YEAR))
    elif ctx.capstone_intent in _NO_INTERNSHIP_INTENTS:
        notes.append(_NOTES[ctx.capstone_intent])
    else:
        notes.append(_NOTES["capstone_completed"])

    if ctx.job_search_timeline in ("1yr_plus_later", "not_job_seeking"):
        notes.append(_NOTES["later_search" if ctx.job_search_timeline == "1yr_plus_later" else "not_job_seeking"])
    else:
        phases.append(_job_search_phase(ctx, anchors, queue, cursor))
        if ctx.job_search_timeline == "during_program":
            notes.append(_NOTES["during_programme"])

    leftover = queue.leftover()
    if leftover:
        if phases:
            first = phases[0]
            phases[0] = _phase(first.kind, first.start, first.end, [*first.actions, *leftover], first.milestones)
        else:
            phases.append(_phase("build_up", cursor, anchors.graduation.end, leftover))

    if anchors.graduation_estimated:
        notes.append(_NOTES["graduation_estimated"].format(term=anchors.graduation.label))
    notes += _market_notes(ctx, with_capstone)
    return Roadmap(
        phases=tuple(sorted(phases, key=lambda p: (p.start, p.end))),
        graduation_term=anchors.graduation.label,
        graduation_estimated=anchors.graduation_estimated,
        capstone_cycle_year=cycle.year if with_capstone else None,
        notes=tuple(notes),
    )
