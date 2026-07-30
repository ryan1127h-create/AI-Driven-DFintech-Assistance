"""Tests for common.skill_matcher (rule backend + factory)."""
from __future__ import annotations

from common.mock_data import get_profile
from common.skill_matcher import RuleSkillMatcher, SkillHit, get_skill_matcher, background_text


def test_background_text_excludes_country():
    p = get_profile("1")  # country=IN
    txt = background_text(p)
    assert "IN" not in txt and "India" not in txt
    assert "banking" in txt  # work_domain IS included (capability signal)


def test_rule_infer_user_skills_matches_legacy():
    # RuleSkillMatcher reproduces derive_user_skills exactly.
    from app.agents.navigator.engine import derive_user_skills
    p = get_profile("5")
    hits = RuleSkillMatcher().infer_user_skills(p)
    assert {h.id for h in hits} == derive_user_skills(p)
    assert all(isinstance(h, SkillHit) for h in hits)


def test_rule_recommend_modules_for_role():
    p = get_profile("1")
    hits = RuleSkillMatcher().recommend_modules("fintech_pm", {"product", "finance"})
    codes = {h.code for h in hits}
    assert "BMS5312" in codes  # from role_module_map fintech_pm


def test_factory_returns_rule_when_embedding_unavailable(monkeypatch):
    from common import skill_matcher
    monkeypatch.setattr("common.embeddings.embedding_available", lambda: False)
    assert isinstance(get_skill_matcher(), RuleSkillMatcher)


def test_embedding_infer_ranks_by_cosine(monkeypatch, tmp_path):
    from common import skill_matcher as M

    def fake_embed(texts):
        out = []
        for t in texts:
            tl = t.lower()
            if "risk" in tl or "quantitative" in tl:
                out.append([1.0, 0.0])
            elif "payment" in tl or "blockchain" in tl:
                out.append([0.0, 1.0])
            else:
                out.append([0.4, 0.4])
        return out

    monkeypatch.setattr(M, "_skill_cache_path", lambda: tmp_path / "_sv.json")
    monkeypatch.setattr("common.embeddings.embed_texts", fake_embed)
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "stub")

    em = M.EmbeddingSkillMatcher(skill_threshold=0.8)
    from common.mock_data import get_profile
    p = get_profile("3")
    monkeypatch.setattr(M, "background_text", lambda _p: "quantitative risk modelling")
    hits = em.infer_user_skills(p)
    assert hits and hits[0].id == "risk_modeling"
    assert hits[0].source == "embedding"


def test_embedding_cache_rebuilds_on_model_change(monkeypatch, tmp_path):
    from common import skill_matcher as M

    calls = {"n": 0}

    def fake_embed(texts):
        calls["n"] += 1
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(M, "_skill_cache_path", lambda: tmp_path / "_sv.json")
    monkeypatch.setattr("common.embeddings.embed_texts", fake_embed)
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "model-A")
    M.EmbeddingSkillMatcher()
    n_a = calls["n"]
    M.EmbeddingSkillMatcher()
    assert calls["n"] == n_a
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "model-B")
    M.EmbeddingSkillMatcher()
    assert calls["n"] > n_a


def test_factory_applies_embedding_thresholds(monkeypatch, tmp_path):
    from common import skill_matcher as M
    import json
    f = tmp_path / "mt.json"
    f.write_text(json.dumps({"embedding": {"skill_threshold": 0.61, "module_threshold": 0.62}}),
                 encoding="utf-8")
    monkeypatch.setattr(M, "_THRESHOLDS_PATH", f)
    monkeypatch.setattr("common.embeddings.embedding_available", lambda: True)
    monkeypatch.setattr(M, "_skill_cache_path", lambda: tmp_path / "_sv.json")
    monkeypatch.setattr("common.embeddings.embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])
    monkeypatch.setattr("common.config.get_embedding_model", lambda: "stub")
    m = M.get_skill_matcher()
    assert m.skill_threshold == 0.61


# ---------- graceful degrade when embedding endpoint is unreachable ----------
def test_embedding_matcher_degrades_to_rule_on_failure(monkeypatch):
    from common import skill_matcher as sm
    from common import embeddings, mock_data

    def _boom(texts):
        raise RuntimeError("embedding endpoint down")

    monkeypatch.setattr(embeddings, "embed_texts", _boom)
    m = sm.EmbeddingSkillMatcher()  # cache build fails -> empty -> inference degrades
    hits = m.infer_user_skills(mock_data.get_profile("1"))
    assert hits and all(h.source == "rule" for h in hits)
