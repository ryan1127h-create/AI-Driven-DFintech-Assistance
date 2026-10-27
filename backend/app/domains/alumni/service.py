"""
Alumni matching rules.

Who's who: an alumnus is a user whose profile lifecycle_stage is "alumni";
their directory entry (alumni.profiles) is created and edited by staff, but
only the alumnus can make it visible (listed). Enrolled students (stage
"current" or "graduating") browse the listed alumni and send requests;
anyone else is refused.

Privacy: a student sees an alumnus's name, position, company, class year,
expertise and bio — contact details only after the alumnus accepts, and only
the ones the alumnus chose to share. An alumnus sees a requesting student's
name, stage and note — their email only after accepting, so they can reply.
Sending a request needs the student's consent_alumni_matching.

Ranking: listed alumni are ordered by how many of the student's role
interests (target_role_families, main_target_role) their expertise covers,
the main target role counting double. Those interests are read under the
student's personalisation consent; without it the list is alphabetical.
"""

from __future__ import annotations

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.domains.alumni import repository
from app.domains.auth import interface as auth_interface
from app.domains.knowledge_retrieval import interface as knowledge_interface
from app.domains.profile import interface as profile_interface

STUDENT_STAGES = ("current", "graduating")
ALUMNI_STAGE = "alumni"
MATCHING_CONSENT = "consent_alumni_matching"
MAX_PENDING_SENT = 5
SHAREABLE = {"email": "contact_email", "phone": "contact_phone", "linkedin": "linkedin_url"}
_STAGE_LABELS = {"current": "Current student", "graduating": "Graduating student"}


# --- who is asking ---------------------------------------------------------------

def viewer_kind(user_id: str) -> str:
    """"alumni" or "student"; ForbiddenError for anyone else."""
    stage = profile_interface.get_profile_field(user_id, "lifecycle_stage")
    if stage == ALUMNI_STAGE:
        return "alumni"
    if stage in STUDENT_STAGES:
        return "student"
    raise ForbiddenError("Alumni Match is for enrolled students and alumni.")


def _require(user_id: str, kind: str) -> None:
    if viewer_kind(user_id) != kind:
        raise ForbiddenError(f"Only {'alumni' if kind == 'alumni' else 'enrolled students'} can do this.")


# --- expertise tags --------------------------------------------------------------

def expertise_options() -> list[dict]:
    """[{tag, label}] — the role tags alumni expertise is chosen from."""
    return [{"tag": t["tag"], "label": t["name_en"]} for t in knowledge_interface.list_role_tags()]


def _labels() -> dict[str, str]:
    return {t["tag"]: t["label"] for t in expertise_options()}


def validate_expertise(tags) -> list[str]:
    known = _labels()
    tags = list(dict.fromkeys(tags or []))
    unknown = [t for t in tags if t not in known]
    if unknown:
        raise ValidationError(f"Unknown expertise: {', '.join(unknown)}.")
    return tags


# --- views -----------------------------------------------------------------------

def _public_alumnus(profile: dict, names: dict, labels: dict) -> dict:
    """What any enrolled student may see of a listed alumnus."""
    return {
        "id": profile["user_id"], "name": names.get(profile["user_id"], {}).get("full_name") or "Alumnus",
        "position": profile["position"], "company": profile["company"], "class_year": profile["class_year"],
        "expertise": [{"tag": t, "label": labels.get(t, t)} for t in profile["expertise"]],
        "bio": profile["bio"], "photo_url": profile["photo_url"],
    }


def _student_interests(student_id: str) -> tuple[set[str], str | None]:
    facts = profile_interface.get_profile_for_purpose(student_id, "career")
    return set(facts.get("target_role_families") or []), facts.get("main_target_role")


# What an alumnus sees about a requesting student, beyond name and stage:
# only fields tagged with purpose "alumni", read under the student's
# consent_alumni_matching (profile.fields_for_purpose enforces both), in
# this order. The role fields feed the match instead of the background.
_BACKGROUND_FIELDS = ("graduation_term", "degree_discipline_category", "total_work_years",
                      "target_markets", "job_search_timeline")


def _student_card(student_id: str, alumni_expertise: list[str], labels: dict) -> dict:
    """{"match": {shared, main_role, other}, "background": [{label, value}],
    "mentor_seeking"} for one requesting student."""
    facts = profile_interface.get_profile_for_purpose(student_id, "alumni")
    families = list(facts.get("target_role_families") or [])
    main_role = facts.get("main_target_role")
    interests = list(dict.fromkeys(([main_role] if main_role else []) + families))
    field_labels = profile_interface.field_labels(_BACKGROUND_FIELDS)
    return {
        "match": {
            "shared": [labels.get(t, t) for t in interests if t in alumni_expertise],
            "main_role": labels.get(main_role, main_role) if main_role else None,
            "main_role_shared": bool(main_role and main_role in alumni_expertise),
            "other": [labels.get(t, t) for t in interests if t not in alumni_expertise],
        },
        "background": [
            {"label": field_labels.get(key, key), "value": profile_interface.describe_value(key, facts[key])}
            for key in _BACKGROUND_FIELDS if facts.get(key) not in (None, [], "")
        ],
        "mentor_seeking": facts.get("mentor_seeking") is True,
    }


def _request_view(request: dict) -> dict:
    return {
        "id": request["id"], "status": request["status"], "note": request["note"],
        "reply_note": request["reply_note"] if request["status"] == "accepted" else None,
        "created_at": request["created_at"], "responded_at": request["responded_at"],
    }


# --- students --------------------------------------------------------------------

def list_matches(student_id: str, search: str = "", expertise: list[str] | None = None) -> dict:
    _require(student_id, "student")
    labels = _labels()
    profiles = [p for p in repository.list_profiles(listed_only=True) if p["user_id"] != student_id]
    names = auth_interface.get_account_names([p["user_id"] for p in profiles])
    families, main_role = _student_interests(student_id)
    interests = families | ({main_role} if main_role else set())
    open_requests = {
        r["alumni_id"]: r for r in repository.requests_for_student(student_id) if r["status"] in ("pending", "accepted")
    }
    wanted = set(expertise or [])
    query = search.strip().lower()
    items = []
    for profile in profiles:
        person = _public_alumnus(profile, names, labels)
        if query and query not in f"{person['name']} {person['position']} {person['company']}".lower():
            continue
        if wanted and not wanted & set(profile["expertise"]):
            continue
        matched = [t for t in profile["expertise"] if t in interests]
        request = open_requests.get(profile["user_id"])
        items.append({
            **person,
            "matched": [labels.get(t, t) for t in matched],
            "score": len(matched) + (1 if main_role in profile["expertise"] else 0),
            "request": _request_view(request) if request else None,
        })
    items.sort(key=lambda item: (-item["score"], item["name"].lower()))
    return {
        "items": items, "total": len(items), "expertise_options": expertise_options(),
        "ranked_by_interests": bool(interests),
        "can_send_requests": profile_interface.has_consent(student_id, MATCHING_CONSENT),
    }


def send_request(student_id: str, alumni_id: str, note: str | None) -> dict:
    _require(student_id, "student")
    if not profile_interface.has_consent(student_id, MATCHING_CONSENT):
        raise ValidationError("Turn on alumni matching in your profile's privacy settings before contacting alumni.")
    profile = repository.get_profile(alumni_id)
    if profile is None or not profile["listed"] or alumni_id == student_id:
        raise NotFoundError("Alumnus not found.")
    note = (note or "").strip() or None
    if note and len(note) > 300:
        raise ValidationError("The note can be at most 300 characters.")
    if repository.count_pending_sent(student_id) >= MAX_PENDING_SENT:
        raise ValidationError(f"You can have at most {MAX_PENDING_SENT} requests waiting for a reply.")
    request = repository.insert_request(student_id, alumni_id, note)
    if request is None:
        raise ConflictError("You already have an open request with this alumnus.")
    return _request_view(request)


def cancel_request(student_id: str, request_id: str) -> dict:
    request = repository.get_request(request_id)
    if request is None or request["student_id"] != student_id:
        raise NotFoundError("Request not found.")
    updated = repository.set_request_status(request_id, "pending", "cancelled")
    if updated is None:
        raise ConflictError("Only a request still waiting for a reply can be withdrawn.")
    return _request_view(updated)


# --- both sides: the requests page -----------------------------------------------

def list_requests(user_id: str) -> dict:
    kind = viewer_kind(user_id)
    labels = _labels()
    if kind == "student":
        requests = [r for r in repository.requests_for_student(user_id) if r["status"] != "cancelled"]
        profiles = {r["alumni_id"]: repository.get_profile(r["alumni_id"]) for r in requests}
        names = auth_interface.get_account_names(list(profiles))
        sent = []
        for r in requests:
            profile = profiles.get(r["alumni_id"])
            if profile is None:
                continue
            sent.append({
                **_request_view(r), "alumnus": _public_alumnus(profile, names, labels),
                "contact": dict(r["shared_contact"]) if r["status"] == "accepted" else None,
            })
        return {"role": "student", "sent": sent}

    requests = repository.requests_for_alumnus(user_id)
    names = auth_interface.get_account_names([r["student_id"] for r in requests])
    expertise = (repository.get_profile(user_id) or {}).get("expertise") or []
    incoming = []
    for r in requests:
        account = names.get(r["student_id"], {})
        stage = profile_interface.get_profile_field(r["student_id"], "lifecycle_stage")
        incoming.append({
            **_request_view(r),
            "student": {
                "id": r["student_id"], "name": account.get("full_name") or "Student",
                "stage": _STAGE_LABELS.get(stage, "Student"),
                "email": account.get("email") if r["status"] == "accepted" else None,
                **_student_card(r["student_id"], expertise, labels),
            },
            "shared_contact": dict(r["shared_contact"]) if r["status"] == "accepted" else None,
        })
    return {"role": "alumni", "incoming": incoming, "profile": get_my_profile(user_id)}


# --- alumni ----------------------------------------------------------------------

def respond(alumni_id: str, request_id: str, action: str, share: list[str], reply_note: str | None) -> dict:
    _require(alumni_id, "alumni")
    request = repository.get_request(request_id)
    if request is None or request["alumni_id"] != alumni_id:
        raise NotFoundError("Request not found.")
    reply_note = (reply_note or "").strip() or None
    if reply_note and len(reply_note) > 300:
        raise ValidationError("The note can be at most 300 characters.")
    if action == "decline":
        updated = repository.set_request_status(request_id, "pending", "declined")
    elif action == "accept":
        profile = repository.get_profile(alumni_id) or {}
        unknown = [s for s in share if s not in SHAREABLE]
        if unknown:
            raise ValidationError(f"Unknown contact detail: {', '.join(unknown)}.")
        contact = {s: profile.get(SHAREABLE[s]) for s in share}
        if s := next((s for s, v in contact.items() if not v), None):
            raise ValidationError(f"Your directory entry has no {s} to share.")
        updated = repository.set_request_status(request_id, "pending", "accepted", contact, reply_note)
    else:
        raise ValidationError("Unknown action.")
    if updated is None:
        raise ConflictError("This request has already been answered or withdrawn.")
    return _request_view(updated)


def get_my_profile(alumni_id: str) -> dict | None:
    """The alumnus's own directory entry (contact details included), or None
    while staff haven't created it."""
    profile = repository.get_profile(alumni_id)
    if profile is None:
        return None
    labels = _labels()
    return {
        **{k: profile[k] for k in ("position", "company", "class_year", "bio", "photo_url",
                                   "contact_email", "contact_phone", "linkedin_url", "listed")},
        **{k: bool(profile.get(k)) for k in STORY_FLAGS},
        "expertise": [{"tag": t, "label": labels.get(t, t)} for t in profile["expertise"]],
    }


# The alumnus's own consent choices: being listed (findable and contactable
# by enrolled students) and sharing their story with each audience.
VISIBILITY_FLAGS = ("listed", "story_for_applicants", "story_for_students")
STORY_FLAGS = ("story_for_applicants", "story_for_students")


def set_visibility(alumni_id: str, changes: dict) -> dict:
    _require(alumni_id, "alumni")
    fields = {k: bool(v) for k, v in changes.items() if k in VISIBILITY_FLAGS and v is not None}
    if not fields:
        raise ValidationError("Nothing to change.")
    if not repository.update_profile(alumni_id, fields):
        raise NotFoundError("Your directory entry hasn't been set up yet. Please contact the programme office.")
    return get_my_profile(alumni_id)


def set_listed(alumni_id: str, listed: bool) -> dict:
    return set_visibility(alumni_id, {"listed": listed})


# --- alumni stories ----------------------------------------------------------------

# Who a story is shown to -> the alumnus's consent for that audience.
STORY_AUDIENCES = {"applicants": "story_for_applicants", "students": "story_for_students"}


def stories(audience: str, interests: list[str], limit: int = 2) -> list[dict]:
    """Up to `limit` alumni stories for `audience` ("applicants" or
    "students"), from alumni who chose to share with it, whose expertise
    covers the most of `interests` (role tags, most important first). None
    without interests: a story is shown because it matches the reader's
    goals. Never contact details — only what the alumnus wrote about their
    path."""
    if not interests:
        return []
    column = STORY_AUDIENCES[audience]
    labels = _labels()
    ranked = []
    for profile in repository.list_profiles():
        if not profile.get(column):
            continue
        matched = [t for t in interests if t in profile["expertise"]]
        if matched:
            # The first interest (the main target role) counts double.
            ranked.append((len(matched) + (interests[0] in matched), profile, matched))
    ranked.sort(key=lambda item: (-item[0], -(item[1]["class_year"] or 0)))
    names = auth_interface.get_account_names([p["user_id"] for _, p, _ in ranked[:limit]])
    return [
        {
            "name": names.get(p["user_id"], {}).get("full_name") or "An alumnus",
            "position": p["position"], "company": p["company"], "class_year": p["class_year"],
            "bio": p["bio"], "matched": [labels.get(t, t) for t in matched],
        }
        for _, p, matched in ranked[:limit]
    ]



def showcase_stories(limit: int = 6) -> list[dict]:
    """Stories for the public programme page: every alumnus who chose to
    share with prospective students (story_for_applicants) and wrote a
    bio, most recent class first. The name is included; the caller drops
    it for visitors who aren't signed in. Never contact details."""
    labels = _labels()
    shared = [p for p in repository.list_profiles() if p.get("story_for_applicants") and (p.get("bio") or "").strip()]
    shared.sort(key=lambda p: -(p["class_year"] or 0))
    shared = shared[:limit]
    names = auth_interface.get_account_names([p["user_id"] for p in shared])
    return [
        {
            "name": names.get(p["user_id"], {}).get("full_name") or None,
            "position": p["position"], "company": p["company"], "class_year": p["class_year"],
            "bio": p["bio"], "expertise": [labels.get(t, t) for t in p["expertise"]],
        }
        for p in shared
    ]

# --- staff -----------------------------------------------------------------------

_STAFF_FIELDS = ("position", "company", "class_year", "expertise", "bio", "photo_url",
                 "contact_email", "contact_phone", "linkedin_url")


def _clean_staff_fields(fields: dict) -> dict:
    cleaned = {k: v for k, v in fields.items() if k in _STAFF_FIELDS}
    for key, value in list(cleaned.items()):
        if isinstance(value, str):
            cleaned[key] = value.strip() or None
    for required in ("position", "company"):
        if required in cleaned and not cleaned[required]:
            raise ValidationError(f"{required} can't be blank.")
    if "expertise" in cleaned:
        cleaned["expertise"] = validate_expertise(cleaned["expertise"])
    return cleaned


def staff_list() -> list[dict]:
    profiles = repository.list_profiles()
    names = auth_interface.get_account_names([p["user_id"] for p in profiles])
    labels = _labels()
    return [{
        **p, "name": names.get(p["user_id"], {}).get("full_name") or "",
        "email": names.get(p["user_id"], {}).get("email"),
        "expertise": [{"tag": t, "label": labels.get(t, t)} for t in p["expertise"]],
    } for p in profiles]


def staff_create(admin_id: str, email: str, fields: dict) -> dict:
    """Makes an existing account an alumnus: sets their lifecycle stage and
    creates an unlisted directory entry (they list themself)."""
    user_id = auth_interface.find_user_id_by_email(email)
    if user_id is None:
        raise NotFoundError("No account uses that email.")
    if repository.get_profile(user_id) is not None:
        raise ConflictError("This person is already in the alumni directory.")
    cleaned = _clean_staff_fields(fields)
    if not cleaned.get("position") or not cleaned.get("company"):
        raise ValidationError("Position and company are required.")
    repository.insert_profile(user_id, {**cleaned, "listed": False})
    try:
        profile_interface.set_lifecycle_stage(user_id, ALUMNI_STAGE, source="DB", actor=f"admin:{admin_id}")
    except Exception:
        repository.delete_profile(user_id)  # no directory entry for someone who isn't an alumnus
        raise
    return next(p for p in staff_list() if p["user_id"] == user_id)


def staff_update(user_id: str, fields: dict) -> dict:
    cleaned = _clean_staff_fields(fields)
    # Consent is the alumnus's to give: staff may only withdraw it (e.g. on request).
    if fields.get("listed") is True:
        raise ValidationError("Only the alumnus can list themself in the directory.")
    if any(fields.get(flag) is True for flag in STORY_FLAGS):
        raise ValidationError("Only the alumnus can choose to share their story.")
    for flag in VISIBILITY_FLAGS:
        if fields.get(flag) is False:
            cleaned[flag] = False
    if not repository.update_profile(user_id, cleaned):
        raise NotFoundError("Alumnus not found.")
    return next(p for p in staff_list() if p["user_id"] == user_id)


def staff_delete(user_id: str) -> None:
    """Removes the directory entry (and its requests). The lifecycle stage
    stays "alumni": they are still a graduate."""
    if not repository.delete_profile(user_id):
        raise NotFoundError("Alumnus not found.")
