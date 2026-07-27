"""Registry of refreshable data sources.

Add a new source by: defining its schema (admin/schemas.py), an anomaly
function (anomaly.py), and registering an entry here. The pipeline needs no
changes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from admin import schemas

from . import anomaly
from .fetcher import Fetcher, NusmodsFetcher, SampleFetcher

_DATA = Path(__file__).resolve().parents[1] / "data"
_SAMPLES = Path(__file__).resolve().parent / "samples"


@dataclass(frozen=True)
class RefreshSource:
    name: str
    file_path: Path
    schema: type
    trusted: bool  # first-party / authoritative source -> eligible for auto-publish
    anomaly_fn: Callable[[dict, dict], list[str]]
    default_fetcher: Fetcher


_SOURCES: dict[str, RefreshSource] = {
    "module_catalog": RefreshSource(
        name="module_catalog",
        file_path=_DATA / "module_catalog.json",
        schema=schemas.ModuleCatalog,
        trusted=True,  # NUS first-party catalog
        anomaly_fn=anomaly.detect_catalog_anomalies,
        default_fetcher=SampleFetcher(_SAMPLES / "module_catalog_fetched.json"),
    ),
    "programs_dataset": RefreshSource(
        name="programs_dataset",
        file_path=_DATA / "programs_dataset.json",
        schema=schemas.ProgramsDataset,
        trusted=False,  # third-party competitor data -> ALWAYS human review
        anomaly_fn=anomaly.detect_programs_anomalies,
        default_fetcher=SampleFetcher(_SAMPLES / "programs_dataset_researched.json"),
    ),
}


def get_source(name: str) -> RefreshSource:
    if name not in _SOURCES:
        raise KeyError(f"unknown source {name!r}; available: {list(_SOURCES)}")
    return _SOURCES[name]


def all_source_names() -> list[str]:
    return list(_SOURCES)


def catalog_target_codes() -> list[str]:
    """Union of module codes referenced by role_module_map.json (sorted, unique)."""
    path = _DATA / "role_module_map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    codes: set[str] = set()
    for role in data["roles"].values():
        for m in role["recommended_modules"]:
            codes.add(m["code"])
    return sorted(codes)


def live_fetcher_for(name: str) -> Fetcher:
    """Return a real (network) fetcher for a source. Used by `--live`."""
    if name == "module_catalog":
        return NusmodsFetcher(codes=catalog_target_codes())
    raise KeyError(f"no live fetcher configured for {name!r}")
