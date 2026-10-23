"""
Stage policy — what the chat assistant does for each lifecycle stage. The
one place the stage rules live: the orchestrator applies them to every
turn, and the auth domain hands the user's policy stage to the client,
which picks its suggested prompts by it.

A stage never just switches a specialist off. Each intent, per stage, is
one of:

    full      — the matched tool runs, limited to `modes` when given
    reroute   — another intent's tool answers instead, told the user's
                situation by `note` (e.g. an alumnus' course question goes
                to programme knowledge, not to study planning)
    redirect  — no tool runs; the fixed `reply` says why and what to ask
                instead

Data permissions are not decided here: every tool and domain reads by the
caller's own user_id, and the pages and endpoints check the stage
themselves (lifecycle, alumni, checklist binding).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Policy stages: the profile's lifecycle_stage, except that an applicant
# whose latest application was rejected is served as a prospect again
# ("rejected": they may reassess and prepare to reapply) while keeping
# their own record. "guest" (not signed in) is reserved; the chat needs an
# account for now.
STAGES = ("prospect", "rejected", "applicant", "admitted", "current", "graduating", "alumni")
DEFAULT_STAGE = "prospect"


def policy_stage(lifecycle_stage: str | None, sub_stage: str | None = None) -> str:
    if lifecycle_stage == "applicant" and sub_stage == "REJECTED":
        return "rejected"
    return lifecycle_stage if lifecycle_stage in STAGES else DEFAULT_STAGE


@dataclass(frozen=True)
class Rule:
    action: str = "full"  # full / reroute / redirect
    modes: frozenset[str] | None = None  # allowed modes (full); None: all
    default_mode: str | None = None  # used when the asked-for mode isn't allowed
    to: str | None = None  # reroute: the intent that answers instead
    note: str | None = None  # reroute/full: the situation the answering tool is told
    search_hint: str | None = None  # reroute: words added to the answering tool's retrieval query
    reply: str | None = None  # redirect: the fixed reply


FULL = Rule()

# --- notes and replies ------------------------------------------------------------

_PRE_ENROLMENT_COURSES = (
    "The user has not enrolled in the programme yet. Explain how the curriculum is structured "
    "(core courses, electives, tracks, capstone) at the level they asked about and, if their "
    "background is known, which foundations to strengthen before starting (for example "
    "programming, statistics or finance). Do not plan their enrolment: no semester plans and "
    "nothing about units or courses they 'still need'."
)
_ALUMNUS_COURSES = (
    "The user is an alumnus of the programme. Answer about the courses' content as asked; do not "
    "make a study plan or talk about requirements they still need to meet."
)
_ALUMNUS_CAREER = (
    "The user is an alumnus already working after graduating. Do not assess their fit for roles "
    "or ask about job markets. Answer what they asked about career services and alumni life from "
    "the material, and where it fits mention that they can support current students as a "
    "mentor, speaker or ambassador and answer students' requests on the Alumni Match page."
)
_PROSPECT_ADMISSIONS = (
    "The user has no application bound to their account. If they say they have already applied, "
    "tell them they can link it on the Checklist page with their application number to see its "
    "status here."
)
_ADMITTED_ASSESSMENT = (
    "You have already received an offer, so an application assessment no longer applies to you. "
    "I can help with accepting the offer, getting ready to join, or planning your first semester "
    "— just ask."
)
_ENROLLED_ASSESSMENT = (
    "You're already studying in the programme, so an application assessment doesn't apply. If "
    "you'd like, I can plan your courses for next semester or check your progress towards "
    "graduation instead."
)
_ALUMNUS_ASSESSMENT = (
    "As a graduate of the programme, an application assessment doesn't apply to you. I can tell "
    "you about alumni career services, or how to support current students through Alumni Match."
)

# "Which courses should I take?" alone doesn't retrieve the curriculum rules
# the overview rests on.
_CURRICULUM_SEARCH = "MSc DFT curriculum structure: core courses, electives, verticals, capstone, units"
_PRE_ENROLMENT_COURSE_RULE = Rule("reroute", to="academic", note=_PRE_ENROLMENT_COURSES,
                                  search_hint=_CURRICULUM_SEARCH)
_PROSPECT_ADMISSIONS_RULE = Rule(note=_PROSPECT_ADMISSIONS)

# --- the table ---------------------------------------------------------------------
# Intents not listed for a stage are answered in full.

_POLICY: dict[str, dict[str, Rule]] = {
    "prospect": {
        "course_recommendation": _PRE_ENROLMENT_COURSE_RULE,
        "admissions": _PROSPECT_ADMISSIONS_RULE,
    },
    "rejected": {
        "course_recommendation": _PRE_ENROLMENT_COURSE_RULE,
    },
    "applicant": {
        "course_recommendation": _PRE_ENROLMENT_COURSE_RULE,
    },
    "admitted": {
        "assessment": Rule("redirect", reply=_ADMITTED_ASSESSMENT),
        "course_recommendation": Rule(modes=frozenset({"semester_plan", "ad_hoc"}), default_mode="semester_plan"),
    },
    "current": {
        "assessment": Rule("redirect", reply=_ENROLLED_ASSESSMENT),
    },
    "graduating": {
        "assessment": Rule("redirect", reply=_ENROLLED_ASSESSMENT),
    },
    "alumni": {
        "assessment": Rule("redirect", reply=_ALUMNUS_ASSESSMENT),
        "course_recommendation": Rule("reroute", to="academic", note=_ALUMNUS_COURSES),
        "career": Rule("reroute", to="faq", note=_ALUMNUS_CAREER),
    },
}


def rule_for(stage: str, intent: str) -> Rule:
    return _POLICY.get(stage, {}).get(intent, FULL)


@dataclass(frozen=True)
class TurnPlan:
    """How one turn's intents are served at a stage: the intents whose tools
    run (in order, deduplicated), the situation notes for them (by intent),
    the words added to their retrieval query (by intent), the mode each moded
    intent is limited to, and the fixed replies of the redirected ones."""
    intents: list[str]
    notes: dict[str, str] = field(default_factory=dict)
    search_hints: dict[str, str] = field(default_factory=dict)
    modes: dict[str, str | None] = field(default_factory=dict)
    replies: list[str] = field(default_factory=list)


def plan_turn(stage: str, intents: list[str], mode_hints: dict[str, str | None]) -> TurnPlan:
    """Applies the stage's rules to classified intents. `mode_hints`: the
    classifier's mode per moded intent (course_recommendation, career,
    comparison); the plan's `modes` keeps a hint the stage allows and swaps
    a disallowed one for the rule's default."""
    run: list[str] = []
    notes: dict[str, str] = {}
    search_hints: dict[str, str] = {}
    modes: dict[str, str | None] = {}
    replies: list[str] = []
    for intent in intents:
        rule = rule_for(stage, intent)
        if rule.action == "redirect":
            if rule.reply not in replies:
                replies.append(rule.reply)
            continue
        target = rule.to if rule.action == "reroute" else intent
        if target not in run:
            run.append(target)
        if rule.note:
            notes[target] = f"{notes[target]}\n{rule.note}" if target in notes else rule.note
        if rule.search_hint:
            search_hints[target] = rule.search_hint
        if rule.action == "full" and intent in mode_hints:
            hint = mode_hints[intent]
            modes[intent] = hint if rule.modes is None or hint in rule.modes else rule.default_mode
    return TurnPlan(intents=run, notes=notes, search_hints=search_hints, modes=modes, replies=replies)
