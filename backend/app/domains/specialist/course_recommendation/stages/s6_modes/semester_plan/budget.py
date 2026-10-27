"""
S6 semester_plan — how many units the semester can hold.

The units the student asked for, kept within the programme's load for
their study mode (full-time 12-20, part-time 4-12); without a request, the
usual load (16 full-time, 8 part-time). Never more than they still need to
graduate. An unknown or undecided study mode is planned as full-time, and
the reply says so.

Pure function, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.specialist.course_recommendation.policy import curriculum as cs


@dataclass(frozen=True)
class Budget:
    units: int
    source: str  # "requested" | "default"
    study_mode: str  # the mode the load was taken from
    notes: tuple[str, ...] = ()


def unit_budget(requested: int | None, study_mode: str | None, units_remaining: int) -> Budget:
    notes: list[str] = []
    mode = study_mode if study_mode in cs.UNIT_LOAD else "full_time"
    if study_mode not in cs.UNIT_LOAD:
        notes.append("Your study mode isn't set, so this is planned at a full-time load.")
    load = cs.UNIT_LOAD[mode]
    label = "full-time" if mode == "full_time" else "part-time"

    if requested is not None:
        units, source = requested, "requested"
        if units > load["max"]:
            notes.append(f"A {label} semester holds at most {load['max']} units, so this plans {load['max']}.")
            units = load["max"]
        elif units < load["min"]:
            notes.append(f"{units} units is below the {load['min']}-unit minimum for a {label} semester.")
    else:
        units, source = load["default"], "default"

    if units > units_remaining:
        notes.append(f"Only {units_remaining} units remain to graduate, so the plan stops there.")
        units = max(units_remaining, 0)
    return Budget(units=units, source=source, study_mode=mode, notes=tuple(notes))
