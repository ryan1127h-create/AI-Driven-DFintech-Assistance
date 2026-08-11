"""Unit tests for program_comparison's pure-code parts: competitor chunk
parsing, programme/dimension selection, and the match scorer. No database
or LLM involved."""

from __future__ import annotations

from app.modules.program_comparison import repository, service
from app.modules.program_comparison.agents import match_scorer
from app.modules.program_comparison.models import ProgramFacts


def make_program(
    name: str = "Test University MSc",
    curriculum: str = "",
    fees: str = "",
    admission: str = "",
) -> ProgramFacts:
    return ProgramFacts(
        name=name, is_nus=False,
        dimension_text={"curriculum": curriculum, "fees": fees, "admission": admission},
        source_urls=("https://example.edu/msc",),
    )


class TestParseCompetitor:
    CHUNK = {
        "chunk_key": "competitor:NTU MSc in Financial Technology",
        "content": (
            "NTU MSc in Financial Technology. "
            "Fees: S$65,748.80 tuition fee; application fee S$50. "
            "Format: Coursework programme. "
            "Intake: August 2026 intake. "
            "Duration: 1 year full-time; 2 years part-time. "
            "GMAT/GRE: Not compulsory. "
            "Curriculum focus: Financial technology and machine learning."
        ),
        "metadata": {"source_url": "https://ntu.example/msc"},
    }

    def test_labels_regrouped_into_dimensions(self):
        program = repository._parse_competitor(self.CHUNK)

        assert program.name == "NTU MSc in Financial Technology"
        assert "S$65,748.80" in program.dimension_text["fees"]
        assert "August 2026" in program.dimension_text["admission"]
        assert "Not compulsory" in program.dimension_text["admission"]
        assert "machine learning" in program.dimension_text["curriculum"]
        assert "part-time" in program.dimension_text["curriculum"]  # Duration folds in
        assert program.source_urls == ("https://ntu.example/msc",)


class TestSelectDimensions:
    def test_empty_request_gives_all_supported(self):
        assert service._select_dimensions([], []) == list(service.SUPPORTED_DIMENSIONS)

    def test_career_gets_a_no_data_note(self):
        notes: list[str] = []
        dims = service._select_dimensions(["career", "fees"], notes)

        assert dims == ["fees"]
        assert any("career" in n.lower() for n in notes)


class TestListOptions:
    def test_returns_all_program_names_and_dimensions(self, monkeypatch):
        nus = ProgramFacts("NUS MSc DFT", True, {}, ())
        ntu = ProgramFacts("NTU MSc in Financial Technology", False, {}, ())
        monkeypatch.setattr(repository, "load_nus", lambda: nus)
        monkeypatch.setattr(repository, "load_competitors", lambda: [ntu])

        options = service.list_options()
        assert options["programs"] == ["NUS MSc DFT", "NTU MSc in Financial Technology"]
        assert options["dimensions"] == list(service.SUPPORTED_DIMENSIONS)


class TestSelectPrograms:
    def fake_known(self, monkeypatch):
        nus = ProgramFacts("NUS MSc DFT", True, {}, ())
        ntu = ProgramFacts("NTU MSc in Financial Technology", False, {}, ())
        monkeypatch.setattr(repository, "load_nus", lambda: nus)
        monkeypatch.setattr(repository, "load_competitors", lambda: [ntu])
        return nus, ntu

    def test_empty_request_selects_everything(self, monkeypatch):
        nus, ntu = self.fake_known(monkeypatch)
        assert service._select_programs([], []) == [nus, ntu]

    def test_substring_match_is_case_insensitive(self, monkeypatch):
        nus, ntu = self.fake_known(monkeypatch)
        selected = service._select_programs(["ntu msc"], [])

        assert selected == [nus, ntu]  # NUS baseline always included

    def test_unknown_program_is_noted_not_invented(self, monkeypatch):
        nus, _ = self.fake_known(monkeypatch)
        notes: list[str] = []
        selected = service._select_programs(["Hogwarts"], notes)

        assert selected == [nus]
        assert any("Hogwarts" in n for n in notes)


class TestMatchScorer:
    ROLE_SKILLS = ["ai_ml", "finance"]

    def test_skill_focus_counts_keyword_hits(self):
        program = make_program(curriculum="Covers machine learning and financial markets.")
        match = match_scorer._score_one(program, self.ROLE_SKILLS, {})

        skill = match.subscores[0]
        assert skill.included and skill.score == 100

    def test_no_role_skills_excludes_skill_component(self):
        match = match_scorer._score_one(make_program(curriculum="anything"), [], {})

        assert match.subscores[0].included is False

    def test_existing_test_score_gives_full_marks(self):
        match = match_scorer._score_one(make_program(), [], {"gmat": 700})

        tests = match.subscores[1]
        assert tests.included and tests.score == 100

    def test_optional_gmat_beats_required_gmat_when_user_has_none(self):
        optional = make_program(admission="GMAT/GRE: recommended but not compulsory.")
        required = make_program(admission="GMAT/GRE: a GMAT score is required.")

        s_optional = match_scorer._score_one(optional, [], {}).subscores[1]
        s_required = match_scorer._score_one(required, [], {}).subscores[1]
        assert s_optional.score > s_required.score

    def test_no_admission_data_excludes_test_component(self):
        match = match_scorer._score_one(make_program(admission="August intake."), [], {})

        assert match.subscores[1].included is False

    def test_part_time_matters_only_with_work_experience(self):
        program = make_program(curriculum="1 year full-time; 2 years part-time.")

        experienced = match_scorer._score_one(program, [], {"work_years": 5}).subscores[2]
        fresh = match_scorer._score_one(program, [], {"work_years": 0}).subscores[2]
        assert experienced.included and experienced.score == 100
        assert fresh.included is False

    def test_total_reweights_over_included_components_only(self):
        # Only the skill component has data -> total equals its score.
        program = make_program(curriculum="Covers machine learning and financial markets.")
        match = match_scorer._score_one(program, self.ROLE_SKILLS, {})

        assert match.total == 100

    def test_no_data_at_all_gives_none_total(self):
        match = match_scorer._score_one(make_program(), [], {})

        assert match.total is None
