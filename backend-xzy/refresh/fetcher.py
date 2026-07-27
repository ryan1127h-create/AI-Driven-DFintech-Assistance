"""Pluggable fetchers. A real web scraper is a future plug-in implementing the
same interface; SampleFetcher reads a local file so the pipeline is testable
offline.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import date
from pathlib import Path
from typing import Protocol, runtime_checkable

_NUSMODS_BASE = "https://api.nusmods.com/v2"


def _candidate_acad_years(today: date | None = None) -> list[str]:
    """Most-recent-first candidate academic years (NUS year starts ~August)."""
    today = today or date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return [f"{start - i}-{start - i + 1}" for i in range(0, 4)]


def _year_available(acad_year: str, base: str = _NUSMODS_BASE, timeout: int = 10) -> bool:
    url = f"{base}/{acad_year}/moduleList.json"
    try:
        # Open the connection and check status without downloading the body.
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def resolve_acad_year(*, probe: bool = True, base: str = _NUSMODS_BASE) -> str:
    """Pick the NUSMods academic year.

    Priority: NUSMODS_ACAD_YEAR env override > the latest year that the API
    actually serves (probed) > the computed current year (offline fallback).
    """
    override = os.getenv("NUSMODS_ACAD_YEAR")
    if override:
        return override
    candidates = _candidate_acad_years()
    if not probe:
        return candidates[0]
    for ay in candidates:
        if _year_available(ay, base):
            return ay
    return candidates[-1]  # offline fallback


@runtime_checkable
class Fetcher(Protocol):
    def fetch(self) -> dict | str:
        """Return fetched content: a structured dict (clean source) or raw text."""
        ...


class SampleFetcher:
    """Simulates a scrape by reading a local structured JSON file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def fetch(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))


class StaticFetcher:
    """Returns a pre-built dict (handy for tests)."""

    def __init__(self, data: dict):
        self.data = data

    def fetch(self) -> dict:
        return self.data


def map_nusmods_module(raw: dict) -> dict:
    """Map a raw NUSMods module-detail JSON to our module_catalog record.

    Pure function (no network) so it can be unit-tested with a static fixture.
    """
    code = raw["moduleCode"]
    credit = raw.get("moduleCredit")
    try:
        credit = int(float(credit)) if credit is not None else None
    except (TypeError, ValueError):
        credit = None
    semesters = sorted(
        {sd.get("semester") for sd in raw.get("semesterData", []) if sd.get("semester")}
    )
    workload = raw.get("workload")
    workload_hours = (
        float(sum(workload)) if isinstance(workload, list)
        and all(isinstance(x, (int, float)) for x in workload) else None
    )
    return {
        "code": code,
        "name": raw.get("title", "").strip(),
        "credits": credit,
        "description": (raw.get("description") or "").strip() or None,
        "source_url": f"https://nusmods.com/courses/{code}",
        "semesters": semesters,
        "prereq_tree": raw.get("prereqTree"),
        "workload_hours": workload_hours,
    }


class NusmodsFetcher:
    """Real fetcher: pulls module details from the public NUSMods API.

    https://api.nusmods.com/v2/<acadYear>/modules/<code>.json — first-party NUS
    course data (real titles, credits, descriptions). One GET per code.
    """

    def __init__(self, codes: list[str], acad_year: str | None = None,
                 base: str = _NUSMODS_BASE, timeout: int = 20):
        self.codes = codes
        # None -> resolve (env override or latest available year).
        self.acad_year = acad_year or resolve_acad_year(base=base)
        self.base = base
        self.timeout = timeout

    def _fetch_one(self, code: str) -> dict:
        # Try the chosen year first, then fall back through recent years so a
        # module not offered in the newest year is still resolvable.
        years = [self.acad_year] + [y for y in _candidate_acad_years() if y != self.acad_year]
        last_err: Exception | None = None
        for ay in years:
            url = f"{self.base}/{ay}/modules/{code}.json"
            try:
                with urllib.request.urlopen(url, timeout=self.timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except Exception as e:  # noqa: BLE001
                last_err = e
        raise RuntimeError(f"module {code} not found in years {years}: {last_err}")

    def fetch(self) -> dict:
        modules = [map_nusmods_module(self._fetch_one(c)) for c in self.codes]
        return {
            "source_url": f"{self.base}/{self.acad_year}/modules",
            "fetched_at": date.today().isoformat(),
            "modules": modules,
        }
