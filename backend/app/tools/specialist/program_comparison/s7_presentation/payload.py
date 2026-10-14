"""
S7 — the render view: the part of the domain result the reply is written
from, every fact in display form. The domain result also carries audit
data (stage results, diagnostics, raw rule outputs) meant for logs and
API callers; that stays out of the view.

Money reads "SGD 76,409", always with its currency and never converted;
lengths in months; skills by their English names; the differences from
MSc DFT as plain statements. Facts an official page states otherwise go
into `caveats`, which the reply must mention. Pure.
"""

from __future__ import annotations

SKILL_NAMES = {
    "ai_ml": "machine learning & AI",
    "data_analytics": "data analytics",
    "data_engineering": "data engineering",
    "finance": "finance",
    "payments_systems": "payments & blockchain systems",
    "product": "product & business",
    "programming": "programming",
    "regulation": "regulation & compliance",
    "risk_modeling": "risk modelling",
    "security": "security",
}
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")
_MODES = {"full_time": "full-time", "part_time": "part-time", "online": "online / distance"}
_CATEGORY = {"all": "all students", "domestic": "local students", "international": "international students"}
_ELIGIBLE = {"all": "everyone", "sg_citizen": "Singapore citizens", "sg_pr": "Singapore PRs",
             "domestic": "local students", "international": "international students", "alumni": "alumni"}
_BASIS = {"programme": "for the whole programme", "per_year": "per year", "per_credit": "per credit"}
_FIELD_NAMES = {
    "gmat_gre_policy": "GMAT/GRE", "internship": "internship", "duration_ft_months": "full-time length",
    "duration_pt_months": "part-time length", "ielts_min": "IELTS minimum",
}


def money(amount, currency: str | None) -> str:
    text = f"{amount:,.0f}" if float(amount).is_integer() else f"{amount:,.2f}"
    return f"{currency} {text}" if currency else text


def _months(n) -> str:
    return f"{n:g} months"


def _skills(names) -> list[str]:
    return [SKILL_NAMES.get(s, s) for s in names]


def _label(p: dict) -> str:
    return f"{p['university_short']} {p['short_name']}"


# ── facts ─────────────────────────────────────────────────────────────────

def _fee_line(f: dict) -> str:
    line = f"{money(f['amount'], f['currency'])} {_BASIS.get(f.get('basis'), '')}".strip()
    if f.get("student_category", "all") != "all":
        line += f" ({_CATEGORY[f['student_category']]})"
    if f.get("includes_tax"):
        line += ", including tax"
    return line + (f" — {f['note']}" if f.get("note") else "")


def _funding_line(item: dict) -> str:
    amount = {
        "fixed": lambda: money(item.get("amount"), item.get("currency")),
        "percent_tuition": lambda: f"{item.get('percent'):g}% of tuition",
        "full_tuition": lambda: "up to full tuition",
        "varies": lambda: "amount varies",
    }[item["amount_kind"]]()
    who = item.get("eligible_categories")
    line = f"{item['name']} ({item['kind']}): {amount}; for " + (
        ", ".join(_ELIGIBLE.get(c, c) for c in who) if who else "eligibility not stated by the source")
    if item.get("bond_required"):
        line += "; comes with a service bond"
    return line + (f". {item['conditions']}" if item.get("conditions") else "")


def _facts(facts: dict) -> dict:
    view = {}
    if c := facts.get("cost"):
        view["cost"] = {"tuition": [_fee_line(f) for f in c.get("fees", [])]}
        if fee := c.get("application_fee"):
            view["cost"]["application_fee"] = money(fee["amount"], fee.get("currency"))
    if d := facts.get("duration"):
        view["duration"] = {k: v for k, v in {
            "full_time": _months(d["full_time_months"]) if "full_time_months" in d else None,
            "part_time": _months(d["part_time_months"]) if "part_time_months" in d else None,
            "longest_allowed": _months(d["max_months"]) if "max_months" in d else None,
            "courses": d.get("courses"),
            "credits": f"{d['credits']:g} {d.get('credit_unit', '')}".strip() if "credits" in d else None,
        }.items() if v is not None}
    if c := facts.get("curriculum"):
        areas = c.get("areas", [])
        by = {level: [f"{SKILL_NAMES.get(a['skill'], a['skill'])} ({'; '.join(a.get('courses', []))})"
                      for a in areas if a["coverage"] == level]
              for level in ("required", "core_option", "elective")}
        view["curriculum"] = {k: v for k, v in {
            "everyone_takes": by["required"], "choose_from_core_list": by["core_option"],
            "electives": by["elective"],
            "not_taught": _skills(a["skill"] for a in areas if a["coverage"] == "none"),
            "capstone": c.get("capstone"), "internship": c.get("internship"),
            "programming_background": c.get("programming_prereq"),
        }.items() if v}
    if a := facts.get("admission"):
        english = []
        if "toefl_ibt_min" in a or "toefl_ibt_band_min" in a:
            english.append("TOEFL iBT " + " or ".join(filter(None, (
                f"{a['toefl_ibt_min']} (0-120 scale)" if "toefl_ibt_min" in a else None,
                f"{a['toefl_ibt_band_min']:g} (1-6 scale, tests from 21 Jan 2026)" if "toefl_ibt_band_min" in a else None))))
        if "ielts_min" in a:
            english.append(f"IELTS {a['ielts_min']:g}" + (f", every band {a['ielts_sub_min']:g}" if "ielts_sub_min" in a else ""))
        view["admission"] = {k: v for k, v in {
            "background": a.get("background_requirement"), "gmat_gre": a.get("gmat_gre_policy"),
            "gmat_gre_note": a.get("gmat_gre_note"), "english_minimum": english,
            "english_waived_when": a.get("english_waiver"),
            "work_experience": a.get("work_exp_policy") + (f" ({a['work_exp_min_years']:g}+ years)" if "work_exp_min_years" in a else "")
            if a.get("work_exp_policy") else None,
        }.items() if v}
    if f := facts.get("flexibility"):
        view["flexibility"] = {k: v for k, v in {
            "study_modes": [_MODES.get(m, m) for m in f.get("study_modes", [])],
            "intakes": [_MONTHS[m - 1] for m in f.get("intake_months", [])],
            "notes": f.get("notes"),
        }.items() if v}
    if f := facts.get("funding"):
        view["funding"] = [_funding_line(item) for item in f.get("items", [])]
    if d := facts.get("deadlines"):
        view["deadlines"] = [
            f"{r.get('round_label') or 'Round ' + str(r['round_no'])}"
            + (f" ({_CATEGORY[r['applicant_category']]})" if r.get("applicant_category", "all") != "all" else "")
            + (f": opens {r['opens_on']}," if r.get("opens_on") else ":") + f" closes {r['closes_on']}"
            for r in d.get("rounds", [])
        ]
    if loc := facts.get("location"):
        view["location"] = f"{loc['city']}, {loc['country']}" if loc.get("city") != loc.get("country") else loc["country"]
    return view


# ── fit ───────────────────────────────────────────────────────────────────

_ENGLISH = {
    "met": "meets the English minimum", "not_met": "below the English minimum", "waived": "English test waived",
    "missing": "no valid English test on file", "no_data": "no English minimum published",
}
_GMAT = {
    "have_score": "has a valid score", "not_needed": "not needed", "recommended": "recommended but not required",
    "required": "required", "required_waivable": "required unless waived", "no_data": "not stated",
}


def _reduction_status(r: dict) -> str:
    """How sure a reduction other than the one deducted is. Never phrased
    as something the user has done (they haven't applied for anything)."""
    automatic_kind = r["kind"] in ("rebate", "grant")
    if r.get("eligible") is None:
        if automatic_kind:
            return "given without applying to those who qualify; your profile doesn't show whether you do"
        return "would need a separate application and isn't guaranteed; your profile doesn't show whether you qualify"
    if automatic_kind:
        return "you qualify, but only one reduction is counted above, as they may not combine"
    return "you could apply for it; not guaranteed"


def _fit(fit: dict) -> dict:
    view = {}
    if c := fit.get("cost"):
        cost = {}
        if c.get("applicant_category"):
            cost["rate_for_you"] = _CATEGORY[c["applicant_category"]]
        if "net_amount" in c:
            d = c["deduction"]
            how = f"{d['percent']:g}% of tuition" if d.get("percent") else money(d.get("amount"), d.get("currency"))
            cost["after_automatic_reduction"] = (
                f"{money(c['net_amount'], c['currency'])} after {d['name']} ({how}, "
                f"{money(c['deduction_amount'], c['currency'])}), given automatically")
        others = [f"{r['name']} — {_reduction_status(r)}" for r in c.get("other_reductions", [])]
        if others:
            cost["may_also_apply"] = others
        if cost:
            view["cost"] = cost
    if a := fit.get("admission"):
        adm = {}
        if e := a.get("english"):
            line = _ENGLISH[e["status"]]
            if e.get("test"):
                line += f": your {e['test']} {e['score']:g} vs minimum {e['minimum']:g}"
            if e.get("sub_scores_unchecked"):
                line += " (band scores not on file, not checked)"
            adm["english"] = line
        if g := a.get("gmat_gre"):
            line = f"GMAT/GRE {_GMAT[g['status']]}"
            if g.get("test"):
                line += f" ({g['test']} {g['score']:g})" if g.get("score") is not None else f" ({g['test']})"
            adm["gmat_gre"] = line
        if w := a.get("work"):
            adm["work_experience"] = f"{w['status']}" + (
                f": about {w['applicant_years']} year(s) vs {w['minimum_years']:g} wanted" if w.get("minimum_years") is not None
                and w.get("applicant_years") is not None else "")
        view["admission"] = adm
    if c := fit.get("curriculum"):
        cur = {}
        if t := c.get("target"):
            cur["for_your_target_role"] = {
                "role": t["role"], "everyone_takes": _skills(t["guaranteed"]), "can_choose": _skills(t["available"]),
                "not_taught": _skills(t["not_taught"]), "unknown": _skills(t["unknown"]),
            }
        for side in ("tech", "finance"):
            if d := c.get(f"{side}_depth"):
                cur[f"{side}_depth"] = {"everyone_takes": _skills(d["guaranteed"]), "can_choose": _skills(d["available"])}
        view["curriculum"] = cur
    if d := fit.get("deadlines"):
        if d.get("next_round"):
            r = d["next_round"]
            name = r.get("label") or f"Round {r['round_no']}"
            view["deadlines"] = (f"{name} is open, closes {r['closes_on']} ({r['days_left']} days left)"
                                 if r["status"] == "open" else f"{name} opens {r['opens_on']}, closes {r['closes_on']}")
        elif d.get("all_closed"):
            view["deadlines"] = "every round for this intake has closed"
    if f := fit.get("flexibility"):
        if "part_time_available" in f:
            view["flexibility"] = "part-time study available" if f["part_time_available"] else "no part-time study"
    return view


def _programme(p: dict) -> dict:
    view = {
        "programme": f"{_label(p)} — {p['name']}",
        "location": f"{p['city']}, {p['country']}" if p["city"] != p["country"] else p["country"],
        "intake": f"AY{p['intake_year']}/{(p['intake_year'] + 1) % 100:02d}",
        "facts": _facts(p["facts"]),
    }
    if p["is_target"]:
        view["this_is_msc_dft"] = True
    if p.get("summary"):
        view["about"] = p["summary"]
    if p["fit"]:
        view["for_you"] = _fit(p["fit"])
    return view


# ── differences and caveats ───────────────────────────────────────────────

def _difference(c: dict, names: dict[str, str]) -> str | None:
    other, d = names[c["program_id"]], c["detail"]
    kind = c["kind"]
    if kind == "fee_difference":
        rel = "less" if d["difference"] < 0 else "more"
        return (f"Tuition: {other} costs {money(abs(d['difference']), d['currency'])} {rel} than MSc DFT "
                f"({money(d['other'], d['currency'])} vs {money(d['dft'], d['currency'])})")
    if kind == "different_currency":
        return (f"Tuition: MSc DFT {money(d['dft']['amount'], d['dft']['currency'])} vs {other} "
                f"{money(d['other']['amount'], d['other']['currency'])} — different currencies, not converted")
    if kind == "net_difference":
        return (f"What you would pay after reductions given automatically: MSc DFT {money(d['dft'], d['currency'])}"
                f"{'' if d['dft_reduced'] else ' (no automatic reduction)'} vs {other} {money(d['other'], d['currency'])}"
                f"{'' if d['other_reduced'] else ' (no automatic reduction)'}")
    if kind in ("duration_ft_months", "duration_pt_months"):
        mode = "Full-time" if kind == "duration_ft_months" else "Part-time"
        return f"{mode} length: {other} {_months(d['other'])} vs MSc DFT {_months(d['dft'])}"
    if kind == "study_modes":
        return (f"Study modes: MSc DFT {', '.join(_MODES.get(m, m) for m in d['dft'])}; "
                f"{other} {', '.join(_MODES.get(m, m) for m in d['other'])}")
    if kind == "intake_months":
        return (f"Intakes: MSc DFT {', '.join(_MONTHS[m - 1] for m in d['dft'])}; "
                f"{other} {', '.join(_MONTHS[m - 1] for m in d['other'])}")
    if kind in ("gmat_gre_policy", "work_exp_policy"):
        label = "GMAT/GRE" if kind == "gmat_gre_policy" else "Work experience"
        return f"{label}: MSc DFT {d['dft']}; {other} {d['other']}"
    if kind == "ielts_min":
        return f"IELTS minimum: MSc DFT {d['dft']:g}; {other} {d['other']:g}"
    if kind == "toefl_ibt_band_min":
        return f"TOEFL minimum (1-6 scale): MSc DFT {d['dft']:g}; {other} {d['other']:g}"
    if kind == "english_fit":
        return f"Your English score: {_ENGLISH[d['dft']]} at MSc DFT; {_ENGLISH[d['other']]} at {other}"
    if kind in ("target_skills_required", "required_skills"):
        what = "your target role's skills that everyone takes" if kind == "target_skills_required" else "skills everyone takes"
        parts = []
        if d["only_dft"]:
            parts.append(f"only at MSc DFT: {', '.join(_skills(d['only_dft']))}")
        if d["only_other"]:
            parts.append(f"only at {other}: {', '.join(_skills(d['only_other']))}")
        if d["both"]:
            parts.append(f"both: {', '.join(_skills(d['both']))}")
        return f"Curriculum, {what} — " + "; ".join(parts)
    if kind == "next_close":
        return (f"Next application deadline open to you: MSc DFT {d['dft'] or 'none open'}; "
                f"{other} {d['other'] or 'none open'}")
    if kind == "country":
        return f"Location: MSc DFT in {d['dft']}; {other} in {d['other']}"
    return None


def _caveats(programmes: list[dict]) -> list[str]:
    lines = []
    for p in programmes:
        for c in p["conflicts"]:
            field = _FIELD_NAMES.get(c["field"], c["field"].replace("_", " "))
            quote = f' (it says: "{c["other_quote"]}")' if c.get("other_quote") else ""
            lines.append(f"{_label(p)} {field}: another official page states this differently{quote}. {c['note']}")
    return lines


def to_render_view(result: dict) -> dict:
    programmes = [p for p in (result["baseline"], *result["subjects"], *result["matches"]) if p]
    names = {p["program_id"]: _label(p) for p in programmes}
    view = {
        "mode": result["mode"],
        "aspects": result["dimensions"],
        "personalised": result["personalised"],
    }
    if result["mode"] == "detail":
        view["programme"] = _programme(result["baseline"])
    else:
        view["msc_dft"] = _programme(result["baseline"])
    if result["subjects"]:
        view["compared_with"] = [_programme(p) for p in result["subjects"]]
        view["differences_from_msc_dft"] = [line for c in result["contrasts"] if (line := _difference(c, names))]
    if result["mode"] == "explore":
        view["how_many_match"] = len(result["matches"])
        view["matching_programmes"] = [_programme(p) for p in result["matches"]]
    caveats = _caveats(programmes)
    if caveats:
        view["caveats"] = caveats
    view["notes"] = list(result.get("notes") or [])
    view["sources"] = list(dict.fromkeys(url for p in programmes for url in p["sources"]))
    return view
