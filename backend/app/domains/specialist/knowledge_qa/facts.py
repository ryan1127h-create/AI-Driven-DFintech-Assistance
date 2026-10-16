"""
The programme's current key facts as a reference block for the answer
prompt: fees, application period, requirements and funding for the intake
applicants are applying for now, taken from the programme catalogue's
checked MSc DFT record (the caller passes that record in; this domain
reads no data itself).

These are the facts that change every year. The retrieved reference
material may still hold an earlier intake's figures, so this block is
given first and governs where they differ (see qa_agent's rules).
"""

from __future__ import annotations

import datetime as dt

ENQUIRY_URL = ("https://cloud.hello.nus.edu.sg/pg-enquiry?programme_code=0300DFTCWK"
               "&acquisition_source_id=B2C_WEBFORM_PG_SOC")

_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]
_GMAT = {
    "required": "required", "required_waivable": "required unless waived",
    "recommended": "not mandatory, but a good score strengthens the application",
    "optional": "optional", "not_considered": "not considered",
}
_WORK = {"required": "required", "preferred": "preferred, not required", "not_required": "not required"}
_PROGRAMMING = {
    "required": "required", "recommended": "recommended",
    "conditional": "required for some applicants", "not_required": "not required",
}
_ELIGIBLE = {
    "all": "all students", "sg_citizen": "Singapore Citizens", "sg_pr": "Singapore PRs",
    "domestic": "local students", "international": "international students", "alumni": "NUS alumni",
}


def _date(value) -> str:
    d = value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _money(amount, currency: str) -> str:
    prefix = "S$" if currency == "SGD" else f"{currency} "
    text = f"{float(amount):,.2f}"
    return prefix + (text[:-3] if text.endswith(".00") else text)


def _months(n) -> str:
    n = float(n)
    return f"{n / 12:g} years" if n % 6 == 0 else f"{n:g} months"


def _funding_line(f: dict) -> str:
    if f["amount_kind"] == "percent_tuition" and f.get("percent") is not None:
        amount = f"{float(f['percent']):g}% of tuition"
    elif f["amount_kind"] == "fixed" and f.get("amount") is not None:
        amount = _money(f["amount"], f.get("currency") or "SGD")
    elif f["amount_kind"] == "full_tuition":
        amount = "full tuition"
    else:
        amount = "amount varies"
    who = ", ".join(_ELIGIBLE.get(c, c) for c in f["eligible_categories"]) if f.get("eligible_categories") else None
    how = "given automatically to those eligible" if f["kind"] in ("rebate", "grant") else "applied for separately"
    parts = [f"{f['name']} ({f['kind']}): {amount}", f"for {who}" if who else None, how,
             "with a service bond" if f.get("bond_required") else None, f.get("conditions")]
    return "; ".join(p.rstrip(".") for p in parts if p) + "."


def current_facts(program: dict) -> str:
    """The reference block for one catalogue programme record (see
    program_catalog.interface for its shape)."""
    facts, year = program["facts"], program["intake_year"]
    lines = [
        f"CURRENT PROGRAMME FACTS — {program['name']} ({program['short_name']}), "
        f"August {year} intake, the intake applicants are applying for now. Checked against the official "
        f"pages on {_date(program['verified_at'])}. Where other reference material gives different figures "
        "(an earlier intake's), these govern.",
    ]
    for fee in program["fees"]:
        tax = ", including GST" if fee.get("includes_tax") else ""
        lines.append(f"- Tuition fee: {_money(fee['amount'], fee['currency'])} for the whole programme{tax}. "
                     f"{fee.get('note') or ''} Official wording: \"{fee['quote']}\"".rstrip())
    for d in program["deadlines"]:
        opens = f"opens {_date(d['opens_on'])}, " if d.get("opens_on") else ""
        lines.append(f"- Application period ({d['round_label']}, {year}): {opens}closes {_date(d['closes_on'])}.")
    if facts.get("application_fee") is not None:
        lines.append(f"- Application fee: {_money(facts['application_fee'], facts.get('application_fee_currency') or 'SGD')}.")
    if facts.get("intake_months"):
        lines.append("- Intakes: " + ", ".join(_MONTHS[m - 1] for m in facts["intake_months"]) + " only, once a year.")
    durations = [f"full-time {_months(facts['duration_ft_months'])}" if facts.get("duration_ft_months") else None,
                 f"part-time {_months(facts['duration_pt_months'])}" if facts.get("duration_pt_months") else None,
                 f"maximum candidature {_months(facts['max_candidature_months'])}"
                 if facts.get("max_candidature_months") else None]
    if any(durations):
        lines.append("- Duration: " + ", ".join(d for d in durations if d) + ".")
    if facts.get("total_credits"):
        lines.append(f"- Total requirement: {float(facts['total_credits']):g} {facts.get('credit_unit') or 'units'}.")
    english = [f"TOEFL iBT {facts['toefl_ibt_min']}" if facts.get("toefl_ibt_min") else None,
               f"{float(facts['toefl_ibt_band_min']):g} on the TOEFL 1-6 band scale" if facts.get("toefl_ibt_band_min") else None,
               f"IELTS {float(facts['ielts_min']):g}" if facts.get("ielts_min") else None]
    if any(english):
        waiver = f" {facts['english_waiver']}" if facts.get("english_waiver") else ""
        lines.append("- English minimum: " + " / ".join(e for e in english if e) + "." + waiver)
    if facts.get("gmat_gre_policy"):
        note = f" {facts['gmat_gre_note']}" if facts.get("gmat_gre_note") else ""
        lines.append(f"- GMAT/GRE: {_GMAT.get(facts['gmat_gre_policy'], facts['gmat_gre_policy'])}.{note}")
    if facts.get("work_exp_policy"):
        lines.append(f"- Work experience: {_WORK.get(facts['work_exp_policy'], facts['work_exp_policy'])}.")
    if facts.get("background_requirement"):
        lines.append(f"- Academic background: {facts['background_requirement']}")
    if facts.get("programming_prereq"):
        note = f" {facts['notes']}" if facts.get("notes") else ""
        lines.append(f"- Programming: {_PROGRAMMING.get(facts['programming_prereq'], facts['programming_prereq'])}.{note}")
    lines += [f"- Funding: {_funding_line(f)}" for f in program["funding"]]
    lines.append(f"- Programme page: {program['official_url']}  Enquiries: {ENQUIRY_URL}")
    return "\n".join(lines)


def source_urls(program: dict) -> list[str]:
    """The official pages the block's facts come from, for the reply's sources."""
    urls = [program["official_url"]]
    urls += [row["source_url"] for key in ("fees", "deadlines") for row in program[key]]
    return list(dict.fromkeys(u for u in urls if u))
