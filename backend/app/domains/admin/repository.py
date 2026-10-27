from __future__ import annotations

import json

import psycopg

from app.adapters.admin_reporting_db_adapter import reporting_db


def _short_case_id(case_id) -> str:
    """The last 8 hex digits: ids written by hand or by scripts often share
    their first segment, the tail is what tells them apart."""
    return str(case_id).replace("-", "")[-8:].upper()


def _escalation_row(row: dict) -> dict:
    name = row.get("full_name") or row.get("email") or "Unknown user"
    return {
        "id": str(row["id"]), "shortId": _short_case_id(row["id"]),
        "user_id": str(row["user_id"]) if row.get("user_id") else None,
        # The conversation the case was raised from (null once that
        # conversation is deleted: the FK is ON DELETE SET NULL).
        "conversationId": str(row["conversation_id"]) if row.get("conversation_id") else None,
        "name": name, "email": row.get("email"),
        "initials": "".join(part[0] for part in name.split()[:2]).upper() or "?",
        "trigger": (row.get("trigger_source") or "").title(),
        "origin": row.get("origin_specialist") or "Other",
        "category": (row.get("category") or "").replace("_", " ").title(),
        "priority": (row.get("priority") or "normal").title(),
        "summary": row.get("summary") or "",
        "status": (row.get("status") or "open").title(),
        "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
        "createdDate": row["created_at"].strftime("%d %b %Y") if row.get("created_at") else "—",
        "createdTime": row["created_at"].strftime("%H:%M") if row.get("created_at") else "—",
        "resolvedAt": row["resolved_at"].isoformat() if row.get("resolved_at") else None,
        "resolvedBy": row.get("resolved_by_name") or (str(row["resolved_by"]) if row.get("resolved_by") else None),
        "resolutionNotes": row.get("resolution_notes"),
        "conversation_id": row.get("conversation_id"),
    }


def list_escalations() -> dict:
    rows = reporting_db.fetch_all_dict("""
        select c.*, a.email, a.full_name,
               coalesce(ra.full_name, ra.email) as resolved_by_name,
               c.conversation_id::text as conversation_id
          from chat.cases c left join account.accounts a on a.user_id = c.user_id
          left join account.accounts ra on ra.user_id = c.resolved_by
         order by c.created_at desc
    """)
    stats = reporting_db.fetch_one_dict("""
        select
            count(*) filter (where status = 'open')::int as open_cases,
            count(*) filter (where status = 'open' and priority = 'urgent')::int as urgent_cases,
            count(*) filter (where status = 'resolved' and resolved_at >= current_date)::int as resolved_today,
            coalesce(round(avg(extract(epoch from (resolved_at - created_at)) / 3600)
                filter (where status = 'resolved' and resolved_at is not null), 1), 0)::numeric as avg_resolution_hours
          from chat.cases
    """) or {}
    hours = float(stats.get("avg_resolution_hours") or 0)
    whole_hours = int(hours)
    minutes = round((hours - whole_hours) * 60)
    if minutes == 60:
        whole_hours += 1
        minutes = 0
    return {
        "items": [_escalation_row(row) for row in rows],
        "total": len(rows),
        "stats": {
            "open_cases": stats.get("open_cases", 0),
            "urgent_cases": stats.get("urgent_cases", 0),
            "resolved_today": stats.get("resolved_today", 0),
            "avg_resolution_time": f"{whole_hours}h {minutes:02d}m",
        },
    }


def get_escalation(case_id: str) -> dict | None:
    row = reporting_db.fetch_one_dict("""
        select c.*, a.email, a.full_name,
               coalesce(ra.full_name, ra.email) as resolved_by_name,
               c.conversation_id::text as conversation_id
          from chat.cases c left join account.accounts a on a.user_id = c.user_id
          left join account.accounts ra on ra.user_id = c.resolved_by
         where c.id = %s
    """, (case_id,))
    return _escalation_row(row) if row else None


def resolve_escalation(case_id: str, resolved_by: str, notes: str | None) -> dict | None:
    """Resolving an already-resolved case keeps its original resolver, time
    and notes."""
    reporting_db.execute(
        "update chat.cases set status = 'resolved', resolved_at = now(), resolved_by = %s, resolution_notes = %s"
        " where id = %s and status <> 'resolved'",
        (resolved_by, notes, case_id),
    )
    return get_escalation(case_id)


def list_users(search: str = "", stage: str = "") -> dict:
    """Accounts with their lifecycle stage and sub-stage (e.g. applicant /
    DOCS_REQUIRED); `stage` narrows to one lifecycle stage, or "staff" to
    admins."""
    term = f"%{search.strip()}%"
    items = reporting_db.fetch_all_dict(
        """
        select a.user_id::text, a.email, coalesce(a.full_name, '') as full_name,
               a.account_status, a.role, a.is_anonymous, a.last_login_at, a.created_at,
               p.lifecycle_stage, p.sub_stage,
               coalesce(enrollments.items, '[]'::json) as course_enrollments
          from account.accounts a
          left join profile.v_profile_flat p on p.user_id = a.user_id
          left join lateral (
            select json_agg(json_build_object(
                     'id', ce.id, 'course_code', ce.course_code, 'term', ce.term,
                     'status', ce.status, 'grade_band', ce.grade_band,
                     'credits', ce.credits, 'source', ce.source, 'updated_at', ce.updated_at
                   ) order by ce.term nulls first, ce.course_code) as items
              from sis.course_enrollments ce
             where ce.user_id = a.user_id
          ) enrollments on true
         where (%s = '%%' or a.email ilike %s or a.full_name ilike %s)
           and (%s = '' or (%s = 'staff' and a.role = 'admin')
                or (a.role <> 'admin' and p.lifecycle_stage = %s))
         order by a.created_at desc
        """,
        (term, term, term, stage, stage, stage),
    )
    return {"items": items, "total": len(items)}


def get_user(user_id: str) -> dict | None:
    user = reporting_db.fetch_one_dict(
        """
        select a.user_id::text, a.email, coalesce(a.full_name, '') as full_name,
               a.account_status, a.role, a.is_anonymous, a.last_login_at, a.created_at,
               stage.value as lifecycle_stage
          from account.accounts a
          left join profile.v_profile stage
            on stage.user_id = a.user_id and stage.field_key = 'lifecycle_stage'
         where a.user_id = %s
        """,
        (user_id,),
    )
    if user:
        user["profile"] = reporting_db.fetch_all_dict(
            """
            select p.field_key, p.value, d.module, d.label
              from profile.v_profile p
              left join profile.field_definitions d on d.field_key = p.field_key
             where p.user_id = %s
             order by d.module nulls last, p.field_key
            """,
            (user_id,),
        )
        user["conversations"] = reporting_db.fetch_all_dict(
            "select conversation_id::text, turn_count, total_messages, status, status_updated_at from chat.conversations where user_id::text = %s::text order by status_updated_at desc nulls last",
            (user_id,),
        )
        user["applications"] = reporting_db.fetch_all_dict(
            """
            select application_id::text, application_no, admission_term, status,
                   final_decision, submission_date, updated_at
              from sis.applications
             where user_id = %s
             order by updated_at desc nulls last
            """,
            (user_id,),
        )
        user["course_enrollments"] = reporting_db.fetch_all_dict(
            """
            select id::text, course_code, term, status, grade_band, credits, source, updated_at
              from sis.course_enrollments
             where user_id = %s
             order by term nulls first, course_code
            """,
            (user_id,),
        )
    return user


def update_user(user_id: str, changes: dict) -> dict | None:
    assignments = []
    values = []
    for column in ("role",):
        if column in changes:
            assignments.append(f"{column} = %s")
            values.append(changes[column])
    if not assignments:
        return get_user(user_id)
    values.append(user_id)
    return reporting_db.fetch_one_dict(
        f"""
        update account.accounts set {', '.join(assignments)}, updated_at = now()
         where user_id = %s
         returning user_id::text, email, coalesce(full_name, '') as full_name,
                   account_status, role, is_anonymous, last_login_at, created_at
        """,
        values,
    )


def list_applications() -> dict:
    items = reporting_db.fetch_all_dict("""
        select a.application_id::text, a.application_no, a.applicant_email,
               u.user_id::text as user_id, coalesce(nullif(u.full_name, ''), a.applicant_email) as user_name,
               a.application_type, a.admission_term, a.submission_date,
               a.status, a.final_decision, a.updated_at,
               count(c.id)::int as checklist_total,
               count(c.id) filter (where c.submitted)::int as checklist_submitted
          from sis.applications a
          left join account.accounts u on u.user_id = a.user_id
          left join sis.application_checklist_items c on c.application_id = a.application_id
         group by a.application_id, a.application_no, a.applicant_email, u.user_id, u.full_name, u.email,
                  a.application_type, a.admission_term, a.submission_date, a.status, a.final_decision, a.updated_at
         order by a.updated_at desc nulls last
    """)
    return {"items": items, "total": len(items)}


def get_application(application_id: str) -> dict | None:
    app = reporting_db.fetch_one_dict("select a.application_id::text, a.application_no, a.applicant_email, u.user_id::text as user_id, coalesce(nullif(u.full_name, ''), a.applicant_email) as user_name, a.application_type, a.admission_term, a.submission_date, a.status, a.final_decision, a.updated_at from sis.applications a left join account.accounts u on u.user_id = a.user_id where a.application_id = %s", (application_id,))
    if not app:
        return None
    app["checklist"] = reporting_db.fetch_all_dict("select id::text, item_key, submitted, updated_at from sis.application_checklist_items where application_id = %s order by item_key", (application_id,))
    return app


def update_application(application_id: str, changes: dict, changed_by: str) -> dict | None:
    """A status change also appends to the status history the student's
    application tracker shows, in the same transaction."""
    assignments, values = [], []
    for column in ("status", "final_decision"):
        if column in changes:
            assignments.append(f"{column} = %s"); values.append(changes[column])
    with reporting_db.transaction() as tx:
        current = tx.fetch_one_dict(
            "select status from sis.applications where application_id = %s for update", (application_id,)
        )
        if current is None:
            return None
        if assignments:
            tx.execute(
                f"update sis.applications set {', '.join(assignments)}, updated_at = now() where application_id = %s",
                [*values, application_id],
            )
        if "status" in changes and changes["status"] != current["status"]:
            tx.execute(
                "insert into sis.application_status_history (application_id, old_status, new_status, changed_by)"
                " values (%s, %s, %s, %s)",
                (application_id, current["status"], changes["status"], changed_by),
            )
    return get_application(application_id)


def update_checklist_item(item_id: str, submitted: bool) -> dict | None:
    return reporting_db.fetch_one_dict("update sis.application_checklist_items set submitted = %s, updated_at = now() where id = %s returning id::text, item_key, submitted, updated_at", (submitted, item_id))


def delete_application(application_id: str) -> bool:
    row = reporting_db.execute_returning("delete from sis.applications where application_id = %s returning application_id", (application_id,))
    return row is not None


def list_conversations() -> dict:
    items = reporting_db.fetch_all_dict("select c.conversation_id::text, c.user_id::text, coalesce(nullif(a.full_name, ''), a.email, c.user_id::text) as user_name, a.email as user_email, c.turn_count, c.total_messages, c.status, c.status_updated_at from chat.conversations c left join account.accounts a on a.user_id = c.user_id order by c.status_updated_at desc nulls last")
    return {"items": items, "total": len(items)}


def get_conversation(conversation_id: str) -> dict | None:
    row = reporting_db.fetch_one_dict("select c.conversation_id::text, c.user_id::text, coalesce(nullif(a.full_name, ''), a.email, c.user_id::text) as user_name, a.email as user_email, c.turn_count, c.total_messages, c.status, c.status_updated_at, c.raw_tail, c.history_summaries from chat.conversations c left join account.accounts a on a.user_id = c.user_id where c.conversation_id = %s", (conversation_id,))
    if not row: return None
    row["cases"] = [
        {"id": str(case["id"]), "shortId": _short_case_id(case["id"]), "status": case["status"].title(),
         "category": case["category"].replace("_", " ").title(), "createdAt": case["created_at"].isoformat()}
        for case in reporting_db.fetch_all_dict(
            "select id, status, category, created_at from chat.cases where conversation_id = %s order by created_at desc",
            (conversation_id,),
        )
    ]
    archived = reporting_db.fetch_one_dict("select archived_blocks from chat.messages where conversation_id = %s", (conversation_id,))
    row["archived_blocks"] = archived.get("archived_blocks", []) if archived else []
    return row


def list_knowledge(search: str = "", main_table: str = "all") -> dict:
    term = f"%{search.strip()}%"
    admissions = reporting_db.fetch_all_dict(
        "select key as id, 'admission_requirement' as category, label as title, why as description, required as published from knowledge.admissions_items where (%s = '%%' or key ilike %s or label ilike %s or why ilike %s) order by key",
        (term, term, term, term),
    )
    statuses = reporting_db.fetch_all_dict(
        "select status_code as id, 'application_status' as category, human_status as title, next_step as description, true as published from knowledge.application_status_translations where (%s = '%%' or status_code ilike %s or human_status ilike %s or next_step ilike %s) order by status_code",
        (term, term, term, term),
    )
    programs = reporting_db.fetch_all_dict(
        "select p.program_id as id, 'programs' as category, coalesce(p.short_name, p.name) as title, coalesce(u.name, '') || case when p.faculty is not null then ' · ' || p.faculty else '' end as description, p.status, p.category as program_category, p.delivery, p.summary, (p.status = 'active') as published from program.programs p left join program.universities u on u.university_id = p.university_id where (%s = '%%' or p.program_id ilike %s or p.name ilike %s or p.short_name ilike %s) order by title",
        (term, term, term, term),
    )
    courses = reporting_db.fetch_all_dict(
        "select course_code as id, 'courses' as category, course_code || ' — ' || title as title, coalesce(annex_section, '') as description, annex_section, department, status, (status = 'active') as published from knowledge.courses where (%s = '%%' or course_code ilike %s or title ilike %s) order by course_code",
        (term, term, term),
    )
    groups = {
        "courses": {"label": "Courses", "items": courses, "related": [{"name": "course_descriptions", "count": reporting_db.fetch_one_dict("select count(*)::int as value from knowledge.course_descriptions")["value"]}, {"name": "course_requirements", "count": reporting_db.fetch_one_dict("select count(*)::int as value from knowledge.course_requirements")["value"]}, {"name": "course_rules", "count": reporting_db.fetch_one_dict("select count(*)::int as value from knowledge.course_rules")["value"]}, {"name": "course_schedule", "count": reporting_db.fetch_one_dict("select count(*)::int as value from knowledge.course_schedule")["value"]}, {"name": "course_tags", "count": reporting_db.fetch_one_dict("select count(*)::int as value from knowledge.course_tags")["value"]}]},
        "admissions_items": {"label": "Admission requirements", "items": admissions, "related": []},
        "application_status_translations": {"label": "Application statuses", "items": statuses, "related": []},
        "programs": {"label": "Programs", "items": programs, "related": []},
    }
    counts = reporting_db.fetch_one_dict("select (select count(*)::int from knowledge.courses) as courses, (select count(*)::int from knowledge.document_chunks) as sources") or {}
    selected = groups.get(main_table)
    return {"items": (selected or {}).get("items", admissions + statuses), "total": len((selected or {}).get("items", admissions + statuses)), "counts": counts, "groups": [{"id": key, "label": value["label"], "count": len(value["items"]), "related": value["related"]} for key, value in groups.items()]}


def update_knowledge(item_id: str, category: str, changes: dict) -> dict | None:
    if category == "admission_requirement":
        row = reporting_db.fetch_one_dict(
            "update knowledge.admissions_items set label = coalesce(%s, label), why = coalesce(%s, why), required = coalesce(%s, required) where key = %s returning key as id, 'admission_requirement' as category, label as title, why as description, required as published",
            (changes.get("label"), changes.get("why"), changes.get("required"), item_id),
        )
        return row
    if category == "application_status":
        return reporting_db.fetch_one_dict(
            "update knowledge.application_status_translations set human_status = coalesce(%s, human_status), next_step = coalesce(%s, next_step) where status_code = %s returning status_code as id, 'application_status' as category, human_status as title, next_step as description, true as published",
            (changes.get("human_status"), changes.get("next_step"), item_id),
        )
    return None


def get_knowledge_course(course_code: str) -> dict | None:
    course = reporting_db.fetch_one_dict("select course_code, title, annex_section, annex_intake, module_credit, status from knowledge.courses where course_code = %s", (course_code,))
    if not course:
        return None
    course["related"] = {}
    for name, query in {
        "description": "select * from knowledge.course_descriptions where course_code = %s",
        "requirements": "select * from knowledge.course_requirements where course_code = %s",
        "schedule": "select * from knowledge.course_schedule where course_code = %s order by ay desc, semester",
        "tags": "select * from knowledge.course_tags where course_code = %s order by tag",
        "electives": "select * from knowledge.course_electives where course_code = %s",
        "metadata": "select * from knowledge.course_meta where course_code = %s",
        "workload": "select * from knowledge.course_workload where course_code = %s",
    }.items():
        course["related"][name] = reporting_db.fetch_all_dict(query, (course_code,))
    return course


def get_knowledge_program(program_id: str) -> dict | None:
    program = reporting_db.fetch_one_dict("""
        select p.*, row_to_json(u) as university, row_to_json(d) as destination,
               row_to_json(f) as facts
          from program.programs p
          left join program.universities u using (university_id)
          left join program.destinations d using (country_code)
          left join lateral (select * from program.facts f where f.program_id = p.program_id order by f.intake_year desc limit 1) f on true
         where p.program_id = %s
    """, (program_id,))
    if not program:
        return None
    program["related"] = {}
    queries = {
        "fees": ("select * from program.fees where program_id = %s order by intake_year desc, student_category", (program_id,)),
        "deadlines": ("select * from program.deadlines where program_id = %s order by intake_year desc, round_no", (program_id,)),
        "fact_sources": ("select * from program.fact_sources where program_id = %s order by field_key, role desc", (program_id,)),
        "funding": ("select * from program.funding where program_id = %s or university_id = %s order by funding_id", (program_id, program.get("university_id"))),
        "curriculum": ("select * from program.curriculum_areas where program_id = %s order by skill_id", (program_id,)),
    }
    for name, (query, params) in queries.items():
        program["related"][name] = reporting_db.fetch_all_dict(query, params)
    return program


def update_knowledge_program(program_id: str, changes: dict) -> dict | None:
    allowed = {"name", "short_name", "faculty", "degree_type", "category", "delivery", "summary", "official_url", "status"}
    changes = {key: value for key, value in changes.items() if key in allowed}
    if changes:
        assignments = ", ".join(f"{key} = %s" for key in changes)
        reporting_db.execute(f"update program.programs set {assignments}, updated_at = now() where program_id = %s", [*changes.values(), program_id])
    return get_knowledge_program(program_id)


def update_knowledge_course(course_code: str, changes: dict) -> dict | None:
    assignments = []
    values = []
    for column in ("title", "annex_section", "annex_intake", "module_credit", "status"):
        if column in changes:
            assignments.append(f"{column} = %s")
            values.append(changes[column])
    if assignments:
        values.append(course_code)
        reporting_db.execute(f"update knowledge.courses set {', '.join(assignments)} where course_code = %s", values)
    return get_knowledge_course(course_code)


# Relations the course editor may change, keyed by the name the course page
# uses. course_tags and course_electives are left out: every column there is
# part of the primary key, so a row can only be added or removed, not edited.
# course_rules is per intake, not per course, so it isn't edited from a course.
EDITABLE_COURSE_RELATIONS = {
    "description": "course_descriptions", "requirements": "course_requirements", "schedule": "course_schedule",
    "metadata": "course_meta", "workload": "course_workload",
}
_AUDIT_COLUMNS = {"created_at", "updated_at"}


def update_knowledge_course_related(course_code: str, relation: str, row: dict) -> dict | None:
    table = EDITABLE_COURSE_RELATIONS.get(relation)
    if not table:
        return None
    columns = reporting_db.fetch_all_dict("select column_name from information_schema.columns where table_schema = 'knowledge' and table_name = %s", (table,))
    valid = {item["column_name"] for item in columns}
    key_rows = reporting_db.fetch_all_dict("select kcu.column_name, tc.constraint_type from information_schema.table_constraints tc join information_schema.key_column_usage kcu on kcu.constraint_name = tc.constraint_name and kcu.table_schema = tc.table_schema where tc.table_schema = 'knowledge' and tc.table_name = %s and tc.constraint_type in ('PRIMARY KEY', 'FOREIGN KEY')", (table,))
    protected = {item["column_name"] for item in key_rows}
    editable = [column for column in row if column in valid and column not in protected and column not in _AUDIT_COLUMNS]
    assignments = [f"{column} = %s" for column in editable]
    # The editor's inputs send "" for a cleared field; store that as null
    # (an empty string is not a valid numeric for the workload columns).
    values = [None if row[column] == "" else row[column] for column in editable]
    if not assignments:
        return None
    if "updated_at" in valid:
        assignments.append("updated_at = now()")
    where_columns = [column for column in protected if column in row]
    if "course_code" in valid and "course_code" not in where_columns:
        where_columns.append("course_code")
        row["course_code"] = course_code
    if not where_columns:
        return None
    where = " and ".join(f"{column} = %s" for column in where_columns)
    values.extend(row[column] for column in where_columns)
    reporting_db.execute(f"update knowledge.{table} set {', '.join(assignments)} where {where}", values)
    return get_knowledge_course(course_code)


def fetch_chunk_source(source_table: str, source_id: str) -> dict | None:
    """The rows a structured retrieval chunk is built from:
    {"row": ..., "tags": [...], "previous_metadata": ...}, or None if the
    row is gone. previous_metadata is the current chunk's (courses keep
    fields there that no table has)."""
    queries = {
        "admissions_items": "select key, label, why, required, deadline_key from knowledge.admissions_items where key = %s",
        "application_status_translations": "select status_code, human_status, next_step, eta_days"
                                           " from knowledge.application_status_translations where status_code = %s",
        "courses": """select c.course_code, c.title, c.module_credit, c.department, c.annex_section, c.annex_intake,
                             c.status, cd.description, cr.prerequisite, cr.preclusion
                        from knowledge.courses c
                        left join knowledge.course_descriptions cd using (course_code)
                        left join knowledge.course_requirements cr using (course_code)
                       where c.course_code = %s""",
    }
    row = reporting_db.fetch_one_dict(queries[source_table], (source_id,))
    if row is None:
        return None
    tags = []
    if source_table == "courses":
        tags = reporting_db.fetch_all_dict(
            "select ct.tag, td.name_zh from knowledge.course_tags ct join knowledge.tags_definition td using (tag)"
            " where ct.course_code = %s",
            (source_id,),
        )
    previous = reporting_db.fetch_one_dict(
        "select metadata from knowledge.document_chunks where source_table = %s and source_id = %s",
        (source_table, source_id),
    )
    return {"row": row, "tags": tags, "previous_metadata": previous["metadata"] if previous else None}


def store_chunk(chunk, embedding: list[float]) -> bool:
    """Overwrites the chunk's text, metadata and embedding in place. Returns
    False when there is no chunk with that key to update."""
    row = reporting_db.execute_returning(
        """update knowledge.document_chunks
              set content = %s, context = %s, metadata = %s::jsonb, token_count = %s, embedding = %s::vector
            where chunk_key = %s and source_table = %s
        returning id""",
        (chunk.content, chunk.context, json.dumps(chunk.metadata, ensure_ascii=False), chunk.token_count,
         "[" + ",".join(f"{x:.7f}" for x in embedding) + "]", chunk.chunk_key, chunk.source_table),
    )
    return row is not None

def fetch_overview(days: int = 7) -> dict:
    users = reporting_db.fetch_one_dict(
        """
        select count(*)::int as total,
               count(*) filter (where account_status = 'active')::int as active,
               count(*) filter (where account_status = 'active' and role = 'admin')::int as admins
          from account.accounts
        """
    )
    lifecycle_counts = reporting_db.fetch_all_dict(
        """
        select coalesce(v.value #>> '{}', 'unknown') as stage, count(*)::int as total
          from account.accounts a
          left join profile.v_profile v on v.user_id = a.user_id and v.field_key = 'lifecycle_stage'
         where a.account_status = 'active' and a.role = 'user'
         group by coalesce(v.value #>> '{}', 'unknown')
         order by stage
        """
    )
    users["by_lifecycle_stage"] = {row["stage"]: row["total"] for row in lifecycle_counts}
    conversations = reporting_db.fetch_one_dict(
        "select count(*)::int as total, count(*) filter (where status = 'normal')::int as active from chat.conversations",
    )
    applications = reporting_db.fetch_all_dict(
        "select coalesce(status, '<unknown>') as status, count(*)::int as total from sis.applications group by status order by status",
    )
    checklist = reporting_db.fetch_one_dict(
        """
        with latest_term as (
            select admission_term
              from sis.applications
             where admission_term is not null
             order by submission_date desc nulls last, updated_at desc nulls last
             limit 1
        )
        select
            count(*)::int as total,
            count(*) filter (where c.submitted)::int as submitted,
            count(*) filter (where not c.submitted)::int as outstanding,
            (select admission_term from latest_term) as latest_admission_term,
            count(*) filter (where not c.submitted and a.admission_term = (select admission_term from latest_term))::int
                as latest_term_outstanding
          from sis.application_checklist_items c
          left join sis.applications a on a.application_id = c.application_id
        """
    )
    processing = reporting_db.fetch_one_dict(
        "select round(avg(extract(epoch from (changed_at - a.submission_date)) / 86400)::numeric, 1) as value from sis.application_status_history h join sis.applications a on a.application_id = h.application_id where a.submission_date is not null and h.new_status in ('ACCEPTED', 'REJECTED')"
    ) or {}
    application_insights = {
        "by_term": reporting_db.fetch_all_dict(
            "select coalesce(admission_term, '<unknown>') as label, count(*)::int as total from sis.applications group by admission_term order by total desc"
        ),
        "by_term_status": reporting_db.fetch_all_dict(
            "select coalesce(admission_term, '<unknown>') as term, coalesce(status, '<unknown>') as status, count(*)::int as total from sis.applications group by admission_term, status order by term, total desc"
        ),
        "monthly": reporting_db.fetch_all_dict(
            "select to_char(date_trunc('month', submission_date), 'Mon YYYY') as label, count(*)::int as total from sis.applications where submission_date is not null and submission_date >= now() - interval '12 months' group by date_trunc('month', submission_date) order by date_trunc('month', submission_date)"
        ),
        "average_processing_days": processing.get("value") or 0,
    }
    cases = reporting_db.fetch_one_dict(
        """
        select count(*)::int as total,
               count(*) filter (where status not in ('resolved', 'closed'))::int as open,
               count(*) filter (where status not in ('resolved', 'closed') and priority = 'urgent')::int as urgent,
               count(*) filter (where status not in ('resolved', 'closed') and coalesce(priority, 'normal') = 'normal')::int as normal
          from chat.cases
        """,
    )
    catalogue = reporting_db.fetch_one_dict(
        "select (select count(*)::int from program.universities) as universities, (select count(*)::int from program.programs) as programs, (select count(*)::int from knowledge.courses) as courses"
    )
    activity = reporting_db.fetch_all_dict(
        """
        select 'application' as type, application_id::text as id,
               status as detail, updated_at
          from sis.applications
         order by updated_at desc nulls last
         limit 5
        """
    )
    return {
        "users": users or {"total": 0, "active": 0},
        "conversations": conversations or {"total": 0, "active": 0},
        "applications": {row["status"]: row["total"] for row in applications},
        "checklist": checklist or {"total": 0, "submitted": 0, "outstanding": 0, "latest_admission_term": None, "latest_term_outstanding": 0},
        "application_insights": application_insights,
        "cases": cases or {"total": 0, "open": 0, "urgent": 0, "normal": 0},
        "catalogue": catalogue or {"universities": 0, "programs": 0, "courses": 0},
        "recent_activity": activity,
        "usage": fetch_usage(days),
    }


def fetch_usage(days: int) -> dict:
    """Question topics and per-agent counts from chat.turn_metrics over the
    last `days`: {"available", "topics": [{audience, intent, total}],
    "agents": [{agent, requests, failed, avg_latency_ms}]}. "available" is
    False while the table doesn't exist yet."""
    try:
        topics = reporting_db.fetch_all_dict(
            """select audience, intent, count(*)::int as total
                 from chat.turn_metrics, unnest(intents) as intent
                where created_at >= now() - (%s * interval '1 day') and intent <> 'off_topic'
                group by audience, intent""",
            (days,),
        )
        agents = reporting_db.fetch_all_dict(
            """select agent, count(*)::int as requests,
                      count(*) filter (where agent = any(failed_agents))::int as failed,
                      round(avg(latency_ms))::int as avg_latency_ms
                 from chat.turn_metrics, unnest(agents) as agent
                where created_at >= now() - (%s * interval '1 day')
                group by agent
                order by requests desc, agent""",
            (days,),
        )
    except psycopg.errors.UndefinedTable:
        return {"available": False, "topics": [], "agents": []}
    return {"available": True, "topics": topics, "agents": agents}



# --- insights: how well the assistant answers, and who asks what ---

# A turn's stage as recorded when it was asked; turns recorded before the
# column existed fall back to the user's stage now.
_TURN_STAGE = "coalesce(m.stage, p.lifecycle_stage, 'unknown')"
_TURNS_SINCE = """
    from chat.turn_metrics m
    left join profile.v_profile_flat p on p.user_id = m.user_id
   where m.created_at >= now() - (%s * interval '1 day')"""
_GAP_LIMIT = 20


def fetch_insights(days: int) -> dict:
    """Raw counts for the staff insights over the last `days` (the funnel
    and alumni sharing are as of now): {"available", "resolution",
    "stage_turns", "stage_topics", "gaps", "funnel", "alumni"}. "available"
    is False while the metrics table doesn't exist yet."""
    try:
        resolution = reporting_db.fetch_one_dict(
            f"""select count(*)::int as turns,
                       count(*) filter (where m.outcome in ('fallback', 'error'))::int as unresolved_turns
                {_TURNS_SINCE}""",
            (days,),
        )
        stage_turns = reporting_db.fetch_all_dict(
            f"select {_TURN_STAGE} as stage, count(*)::int as total {_TURNS_SINCE} group by 1",
            (days,),
        )
        stage_topics = reporting_db.fetch_all_dict(
            f"""select {_TURN_STAGE} as stage, intent, count(*)::int as total
                  from chat.turn_metrics m
                 cross join unnest(m.intents) as intent
                  left join profile.v_profile_flat p on p.user_id = m.user_id
                 where m.created_at >= now() - (%s * interval '1 day') and intent <> 'off_topic'
                 group by 1, 2""",
            (days,),
        )
        # A handover offered on a turn is the first case of that conversation
        # opened at or after it.
        gaps = reporting_db.fetch_all_dict(
            f"""select m.created_at, {_TURN_STAGE} as stage, m.intents, m.failed_agents, m.outcome,
                       m.conversation_id::text as conversation_id,
                       (select c.summary from chat.cases c
                         where c.conversation_id = m.conversation_id and c.created_at >= m.created_at
                         order by c.created_at limit 1) as case_summary
                {_TURNS_SINCE} and m.outcome in ('fallback', 'error')
                order by m.created_at desc limit {_GAP_LIMIT}""",
            (days,),
        )
        alumni_questions = reporting_db.fetch_one_dict(
            f"select count(*) filter (where 'alumni' = any(m.intents))::int as total {_TURNS_SINCE}",
            (days,),
        )
    except psycopg.errors.UndefinedTable:
        return {"available": False}
    # Low-confidence cases come from fallback answers, already counted above.
    cases = reporting_db.fetch_one_dict(
        """select count(*) filter (where category <> 'low_confidence')::int as escalated
             from chat.cases where created_at >= now() - (%s * interval '1 day')""",
        (days,),
    )
    funnel = reporting_db.fetch_all_dict(
        """select p.lifecycle_stage as stage, p.sub_stage, count(*)::int as total
             from account.accounts a join profile.v_profile_flat p on p.user_id = a.user_id
            where a.role <> 'admin' and p.lifecycle_stage is not null
            group by 1, 2""",
    )
    requests = reporting_db.fetch_all_dict(
        """select status, count(*)::int as total from alumni.requests
            where created_at >= now() - (%s * interval '1 day') group by status""",
        (days,),
    )
    sharing = reporting_db.fetch_one_dict(
        """select count(*)::int as alumni,
                  count(*) filter (where listed)::int as listed,
                  count(*) filter (where story_for_applicants)::int as story_for_applicants,
                  count(*) filter (where story_for_students)::int as story_for_students
             from alumni.profiles""",
    )
    return {
        "available": True,
        "resolution": {**resolution, "escalated": cases["escalated"]},
        "stage_turns": stage_turns,
        "stage_topics": stage_topics,
        "gaps": gaps,
        "funnel": funnel,
        "alumni": {"questions": alumni_questions["total"], "requests": requests, "sharing": sharing},
    }
