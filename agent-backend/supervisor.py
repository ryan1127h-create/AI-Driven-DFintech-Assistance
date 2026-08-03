"""Supervisor router for lifecycle-aware agent orchestration.

The teammate-owned dialogue module can still call a concrete intent directly,
but this layer now guards two things:
  1) lifecycle stage: applicant flow and current-student flow are separated;
  2) optional RAG confidence gate: low official-source similarity escalates.
"""
from __future__ import annotations

from common.confidence import decide as confidence_decide, response_from_decision
from common.envelope import AgentResponse
from common.profile import LifecycleStage, UserProfile

# intent -> (module path, callable name). Imported lazily so a half-built repo
# still runs the agents that exist.
_ROUTES: dict[str, tuple[str, str]] = {
    "generate_application_checklist": ("app.agents.checklist.agent", "handle"),
    "check_missing_documents": ("app.agents.checklist.agent", "handle"),
    "get_application_status": ("app.agents.tracker.agent", "handle"),
    "configure_reminders": ("app.agents.tracker.agent", "configure"),
    "compare_programs": ("app.agents.comparator.agent", "handle"),
    "recommend_courses": ("app.agents.navigator.agent", "handle"),
    "recommend_career_path": ("app.agents.navigator.agent", "career"),
}

_APPLICANT_STAGES = {
    LifecycleStage.prospect,
    LifecycleStage.applicant,
    LifecycleStage.admitted,
}
_STUDENT_STAGES = {
    LifecycleStage.current,
    LifecycleStage.graduating,
}

_INTENT_FLOWS: dict[str, tuple[str, ...]] = {
    "generate_application_checklist": ("applicant",),
    "check_missing_documents": ("applicant",),
    "get_application_status": ("applicant",),
    "configure_reminders": ("applicant",),
    "compare_programs": ("applicant",),
    # #7 is useful for both applicants (early planning) and current students.
    "recommend_courses": ("applicant", "student"),
    "recommend_career_path": ("applicant", "student"),
}

_FLOW_INTENTS: dict[str, tuple[str, ...]] = {
    "applicant": (
        "generate_application_checklist",
        "get_application_status",
        "compare_programs",
        "recommend_courses",
        "recommend_career_path",
    ),
    "student": (
        "recommend_courses",
        "recommend_career_path",
    ),
    "alumni": (),
}

_SOURCE_AGENT: dict[str, str] = {
    "generate_application_checklist": "checklist",
    "check_missing_documents": "checklist",
    "get_application_status": "tracker",
    "configure_reminders": "tracker",
    "compare_programs": "comparator",
    "recommend_courses": "navigator",
    "recommend_career_path": "navigator",
}

_OFFICIAL_INTENTS = {
    "generate_application_checklist",
    "check_missing_documents",
    "get_application_status",
    "configure_reminders",
}

_ROUTING_TEAM = {
    "checklist": "admissions_office",
    "tracker": "admissions_office",
    "comparator": "programme_office",
    "navigator": "academic_advising_team",
}


def lifecycle_flow(profile: UserProfile) -> str:
    """Return the high-level flow name for this user's lifecycle stage."""
    if profile.lifecycle_stage in _APPLICANT_STAGES:
        return "applicant"
    if profile.lifecycle_stage in _STUDENT_STAGES:
        return "student"
    return "alumni" if profile.lifecycle_stage == LifecycleStage.alumni else "unknown"


def default_intents_for(profile: UserProfile) -> tuple[str, ...]:
    """Default agent sequence for the student web app / demo UI."""
    return _FLOW_INTENTS.get(lifecycle_flow(profile), ())


def route(intent: str, profile: UserProfile, slots: dict | None = None) -> AgentResponse:
    slots = slots or {}
    if intent not in _ROUTES:
        return AgentResponse(
            status="error",
            speakable=f"Unknown intent: {intent}",
        )

    flow_error = _check_lifecycle_compatibility(intent, profile)
    if flow_error is not None:
        return flow_error

    gated = _maybe_apply_confidence_gate(intent, profile, slots)
    if gated is not None:
        return gated

    import importlib

    module_path, func_name = _ROUTES[intent]
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        return AgentResponse(
            status="error",
            speakable=f"This feature is not implemented yet: {intent}",
        )
    handler = getattr(module, func_name)
    return handler(profile, slots) if _takes_slots(handler) else handler(profile)


def _check_lifecycle_compatibility(intent: str, profile: UserProfile) -> AgentResponse | None:
    allowed = _INTENT_FLOWS.get(intent)
    current = lifecycle_flow(profile)
    if allowed is None or current in allowed:
        return None

    if "applicant" in allowed and current == "student":
        msg = ("You are on the current-student flow, so the application checklist, "
               "application status tracking and programme comparison do not apply. "
               "I will focus on course selection, skill directions and career paths.")
    elif allowed == ("student",) and current == "applicant":
        msg = "You are on the applicant flow; this feature only applies to current students."
    elif current == "alumni":
        msg = "You are on the alumni flow; this intent does not apply to the alumni stage."
    else:
        msg = ("Your current lifecycle stage does not match this feature; "
               "please confirm the user's stage first.")

    return AgentResponse(
        status="need_clarification",
        answer_type="advisory",
        speakable=msg,
        data={
            "requested_intent": intent,
            "required_flow": list(allowed),
            "current_flow": current,
            "allowed_intents": list(_FLOW_INTENTS.get(current, ())),
        },
        missing_fields=["lifecycle_stage"],
    )


def _maybe_apply_confidence_gate(
    intent: str, profile: UserProfile, slots: dict
) -> AgentResponse | None:
    """Gate answers when upstream RAG results are provided.

    Expected optional slot shapes:
      {"user_query": "...", "rag_chunks": [{"text": "...", "score": 0.83,
        "source_id": "admissions#p2"}]}

    If no query/chunks are supplied, the existing deterministic agents run as
    before. This keeps the local mock demo independent from the RAG teammate's
    module while still enforcing the interface when RAG is connected.
    """
    query = slots.get("user_query") or slots.get("query") or slots.get("question")
    chunks = slots.get("rag_chunks") or slots.get("retrieval_chunks")
    if query is None and chunks is None:
        return None
    if query is None:
        query = ""
    backend = "bm25"  # default for externally-supplied RAG chunks
    if chunks is None:
        # No external RAG chunks: retrieve locally (design doc 12 §3.6). Pick the
        # threshold set matching the active backend (embedding vs lexical).
        from common.retriever import EmbeddingRetriever, get_retriever

        retriever = get_retriever()
        backend = "embedding" if isinstance(retriever, EmbeddingRetriever) else "bm25"
        namespace = slots.get("namespace")
        retrieved = retriever.retrieve(str(query), namespace)
        chunks = [
            {"text": c.text, "source_id": c.source_id, "score": c.score}
            for c in retrieved
        ]

    source_agent = _SOURCE_AGENT[intent]
    # answer_type is source-driven: an official top source keeps it official.
    intent_default = "official" if intent in _OFFICIAL_INTENTS else "advisory"
    answer_type = intent_default
    high_risk = bool(slots.get("high_risk")) or intent in _OFFICIAL_INTENTS
    decision = confidence_decide(
        str(query), list(chunks), answer_type=answer_type, high_risk=high_risk,
        backend=backend,
    )
    return response_from_decision(
        decision, profile=profile, source_agent=source_agent,
        query=str(query),
        suggested_routing=_ROUTING_TEAM.get(source_agent, "programme_office"),
    )


def _takes_slots(handler) -> bool:
    import inspect

    return len(inspect.signature(handler).parameters) >= 2
