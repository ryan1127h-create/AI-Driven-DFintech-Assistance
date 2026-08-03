"""Pluggable skill/module matcher (design doc 13 §4).

SkillMatcher is the seam: an embedding backend (semantic) and a rule backend
(the existing deterministic logic, offline fallback). Both return explainable
hits (id/label/score/source).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from common.profile import UserProfile
from common import config, embeddings

_RM_PATH = Path(__file__).resolve().parents[1] / "data" / "role_module_map.json"


@dataclass(frozen=True)
class SkillHit:
    id: str
    label: str
    score: float
    source: str  # "rule" | "embedding"


@dataclass(frozen=True)
class ModuleHit:
    code: str
    name: str
    score: float
    source: str


class SkillMatcher(Protocol):
    def infer_user_skills(self, profile: UserProfile) -> list[SkillHit]: ...
    def recommend_modules(self, role: str, user_skills: set[str]) -> list[ModuleHit]: ...


def background_text(profile: UserProfile) -> str:
    """Capability-only text for embedding. EXCLUDES country (fairness, doc 13 §6)."""
    parts: list[str] = []
    ab = profile.academic_background
    if ab:
        parts.append(f"degree {ab.degree_level.value} in {ab.field_of_study.value}")
    if profile.work_domain:
        parts.append(f"work domain {profile.work_domain.value}")
    if profile.work_years is not None:
        parts.append(f"{profile.work_years} years experience")
    if profile.technical_proficiency:
        parts.append(f"technical {profile.technical_proficiency.value}")
    if profile.finance_knowledge:
        parts.append(f"finance knowledge {profile.finance_knowledge.value}")
    if profile.completed_modules:
        parts.append("completed " + ", ".join(profile.completed_modules))
    return "; ".join(parts)


def _load_rm() -> dict:
    return json.loads(_RM_PATH.read_text(encoding="utf-8"))


class RuleSkillMatcher:
    """Deterministic offline backend: reuses the existing rule logic."""

    def infer_user_skills(self, profile: UserProfile) -> list[SkillHit]:
        from app.agents.navigator.engine import derive_user_skills
        from common.skill_taxonomy import load_taxonomy

        labels = {s.id: s.label for s in load_taxonomy()}
        return [SkillHit(id=s, label=labels.get(s, s), score=1.0, source="rule")
                for s in sorted(derive_user_skills(profile))]

    def recommend_modules(self, role: str, user_skills: set[str]) -> list[ModuleHit]:
        role_def = _load_rm()["roles"][role]
        return [ModuleHit(code=m["code"], name=m["name"], score=1.0, source="rule")
                for m in role_def["recommended_modules"]]


_THRESHOLDS_PATH = Path(__file__).resolve().parents[1] / "data" / "match_thresholds.json"


def _match_thresholds(backend: str) -> dict:
    defaults = {"skill_threshold": 0.5}
    try:
        data = json.loads(_THRESHOLDS_PATH.read_text(encoding="utf-8"))
        section = data.get(backend, {})
        return {k: float(section.get(k, defaults[k])) for k in defaults}
    except (OSError, ValueError):
        return defaults


def get_skill_matcher() -> SkillMatcher:
    """Embedding backend when available, else the offline rule backend."""
    try:
        from common.embeddings import embedding_available

        if embedding_available():
            t = _match_thresholds("embedding")
            return EmbeddingSkillMatcher(skill_threshold=t["skill_threshold"])
    except Exception:
        pass
    return RuleSkillMatcher()


_VEC_DIR = Path(__file__).resolve().parents[1] / "data"


def _skill_cache_path() -> Path:
    return _VEC_DIR / "_skill_vectors.json"


def _cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, num / (na * nb)))


class EmbeddingSkillMatcher:
    """Semantic backend over the taxonomy + module_catalog, fingerprinted cache."""

    def __init__(self, skill_threshold: float = 0.5) -> None:
        from common.skill_taxonomy import load_taxonomy

        self.skill_threshold = skill_threshold
        self._skills = load_taxonomy()
        self._model = config.get_embedding_model()
        self._skill_vecs = self._load_or_build_cache()

    def _load_or_build_cache(self) -> dict[str, list[float]]:
        path = _skill_cache_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("model") == self._model:
                    return data.get("vectors", {})
            except (json.JSONDecodeError, OSError):
                pass
        texts = [f"{s.label}. {s.description}. {', '.join(s.aliases)}" for s in self._skills]
        try:
            vecs = embeddings.embed_texts(texts)
        except Exception:
            return {}  # endpoint unreachable -> empty cache; inference degrades to rule
        vectors = {s.id: v for s, v in zip(self._skills, vecs)}
        try:
            path.write_text(json.dumps({"model": self._model, "vectors": vectors}),
                            encoding="utf-8")
        except OSError:
            pass
        return vectors

    def infer_user_skills(self, profile: UserProfile) -> list[SkillHit]:
        if not self._skill_vecs:
            return RuleSkillMatcher().infer_user_skills(profile)  # no cache -> degrade
        try:
            qv = embeddings.embed_texts([background_text(profile)])[0]
        except Exception:
            return RuleSkillMatcher().infer_user_skills(profile)  # endpoint down -> degrade
        labels = {s.id: s.label for s in self._skills}
        scored = [(sid, _cosine(qv, vec)) for sid, vec in self._skill_vecs.items()]
        scored = [(sid, sc) for sid, sc in scored if sc >= self.skill_threshold]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [SkillHit(id=sid, label=labels.get(sid, sid), score=round(sc, 4),
                         source="embedding") for sid, sc in scored]

    def recommend_modules(self, role: str, user_skills: set[str]) -> list[ModuleHit]:
        from common.skill_taxonomy import load_taxonomy

        defs = {s.id: s for s in load_taxonomy()}
        skill_text = ". ".join(defs[s].description for s in user_skills if s in defs) or role
        pool = RuleSkillMatcher().recommend_modules(role, user_skills)
        try:
            qv = embeddings.embed_texts([skill_text])[0]
            mod_texts = [f"{m.name}" for m in pool]
            mvecs = embeddings.embed_texts(mod_texts) if mod_texts else []
        except Exception:
            return pool  # endpoint down -> deterministic rule ordering
        ranked = sorted(
            ((m, _cosine(qv, mv)) for m, mv in zip(pool, mvecs)),
            key=lambda x: x[1], reverse=True,
        )
        return [ModuleHit(code=m.code, name=m.name, score=round(sc, 4),
                          source="embedding") for m, sc in ranked]
