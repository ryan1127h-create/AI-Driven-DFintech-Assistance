from __future__ import annotations

from app.adapters.postgres_pool import SchemaDB, pool

# Reporting queries intentionally span schemas. This adapter is read-only and
# keeps the admin dashboard independent from the ownership adapters used by
# transactional domains.
reporting_db = SchemaDB("admin_reporting", pool)


def _escalation_row(row: dict) -> dict:
    name = row.get("full_name") or row.get("email") or "Unknown user"
    return {
        "id": str(row["id"]), "shortId": str(row["id"]).split("-")[0].upper(),
        "user_id": str(row["user_id"]) if row.get("user_id") else None,
        "name": name, "email": row.get("email"),
        "initials": "".join(part[0] for part in name.split()[:2]).upper() or "?",
        "trigger": (row.get("trigger_source") or "").title(),
        "origin": row.get("origin_specialist") or "Other",
        "category": (row.get("category") or "").replace("_", " ").title(),
        "priority": (row.get("priority") or "normal").title(),
        "summary": row.get("summary") or "",
        "status": (row.get("status") or "open").title(),
        "createdDate": row["created_at"].strftime("%d %b %Y") if row.get("created_at") else "—",
        "createdTime": row["created_at"].strftime("%H:%M") if row.get("created_at") else "—",
        "resolvedAt": row["resolved_at"].isoformat() if row.get("resolved_at") else None,
        "resolvedBy": row.get("resolved_by_name") or (str(row["resolved_by"]) if row.get("resolved_by") else None),
        "resolutionNotes": None,
    }


def list_escalations() -> dict:
    rows = reporting_db.fetch_all_dict("""
        select c.*, a.email, a.full_name, coalesce(ra.full_name, ra.email) as resolved_by_name
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
        select c.*, a.email, a.full_name, coalesce(ra.full_name, ra.email) as resolved_by_name
          from chat.cases c left join account.accounts a on a.user_id = c.user_id
          left join account.accounts ra on ra.user_id = c.resolved_by
         where c.id = %s
    """, (case_id,))
    return _escalation_row(row) if row else None


def update_escalation(case_id: str, changes: dict, resolved_by: str) -> dict | None:
    if changes.get("status") == "Resolved":
        reporting_db.execute("update chat.cases set status = 'resolved', resolved_at = now(), resolved_by = %s where id = %s", (resolved_by, case_id))
    return get_escalation(case_id)


def list_users(search: str = "") -> dict:
    term = f"%{search.strip()}%"
    items = reporting_db.fetch_all_dict(
        """
        select user_id::text, email, coalesce(full_name, '') as full_name,
               account_status, role, is_anonymous, last_login_at, created_at
          from account.accounts
         where (%s = '%%' or email ilike %s or full_name ilike %s)
         order by created_at desc
        """,
        (term, term, term),
    )
    return {"items": items, "total": len(items)}


def get_user(user_id: str) -> dict | None:
    user = reporting_db.fetch_one_dict(
        """
        select user_id::text, email, coalesce(full_name, '') as full_name,
               account_status, role, is_anonymous, last_login_at, created_at
          from account.accounts where user_id = %s
        """,
        (user_id,),
    )
    if user:
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
    return user


def update_user(user_id: str, changes: dict) -> dict | None:
    assignments = []
    values = []
    for column in ("full_name", "account_status", "role"):
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


def delete_user(user_id: str) -> bool:
    row = reporting_db.execute_returning(
        "delete from account.accounts where user_id = %s returning user_id", (user_id,)
    )
    return row is not None


def list_applications() -> dict:
    items = reporting_db.fetch_all_dict("""
        select a.application_id::text, a.application_no, a.applicant_email,
               u.user_id::text as user_id, coalesce(nullif(u.full_name, ''), a.applicant_email) as user_name,
               a.application_type, a.admission_term, a.submission_date,
               a.status, a.final_decision, a.updated_at,
               count(c.id)::int as checklist_total,
               count(c.id) filter (where c.submitted)::int as checklist_submitted
          from sis.applications a
          left join account.accounts u on lower(u.email) = lower(a.applicant_email)
          left join sis.application_checklist_items c on c.application_id = a.application_id
         group by a.application_id, a.application_no, a.applicant_email, u.user_id, u.full_name, u.email,
                  a.application_type, a.admission_term, a.submission_date, a.status, a.final_decision, a.updated_at
         order by a.updated_at desc nulls last
    """)
    return {"items": items, "total": len(items)}


def get_application(application_id: str) -> dict | None:
    app = reporting_db.fetch_one_dict("select a.application_id::text, a.application_no, a.applicant_email, u.user_id::text as user_id, coalesce(nullif(u.full_name, ''), a.applicant_email) as user_name, a.application_type, a.admission_term, a.submission_date, a.status, a.final_decision, a.updated_at from sis.applications a left join account.accounts u on lower(u.email) = lower(a.applicant_email) where a.application_id = %s", (application_id,))
    if not app:
        return None
    app["checklist"] = reporting_db.fetch_all_dict("select id::text, item_key, submitted, updated_at from sis.application_checklist_items where application_id = %s order by item_key", (application_id,))
    return app


def update_application(application_id: str, changes: dict) -> dict | None:
    assignments, values = [], []
    for column in ("status", "final_decision"):
        if column in changes:
            assignments.append(f"{column} = %s"); values.append(changes[column])
    if not assignments:
        return get_application(application_id)
    values.append(application_id)
    reporting_db.execute(f"update sis.applications set {', '.join(assignments)}, updated_at = now() where application_id = %s", values)
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
    courses = reporting_db.fetch_all_dict(
        "select course_code as id, 'courses' as category, course_code || ' — ' || title as title, coalesce(annex_section, '') as description, status, (status = 'active') as published from knowledge.courses where (%s = '%%' or course_code ilike %s or title ilike %s) order by course_code",
        (term, term, term),
    )
    groups = {
        "courses": {"label": "Courses", "items": courses, "related": [{"name": "course_descriptions", "count": reporting_db.fetch_one_dict("select count(*)::int as value from knowledge.course_descriptions")["value"]}, {"name": "course_requirements", "count": reporting_db.fetch_one_dict("select count(*)::int as value from knowledge.course_requirements")["value"]}, {"name": "course_rules", "count": reporting_db.fetch_one_dict("select count(*)::int as value from knowledge.course_rules")["value"]}, {"name": "course_schedule", "count": reporting_db.fetch_one_dict("select count(*)::int as value from knowledge.course_schedule")["value"]}, {"name": "course_tags", "count": reporting_db.fetch_one_dict("select count(*)::int as value from knowledge.course_tags")["value"]}]},
        "admissions_items": {"label": "Admission requirements", "items": admissions, "related": []},
        "application_status_translations": {"label": "Application statuses", "items": statuses, "related": []},
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
        "rules": "select * from knowledge.course_rules order by intake, category, id",
    }.items():
        course["related"][name] = reporting_db.fetch_all_dict(query, () if name == "rules" else (course_code,))
    return course


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


def update_knowledge_course_related(course_code: str, relation: str, row: dict) -> dict | None:
    tables = {"description": "course_descriptions", "requirements": "course_requirements", "schedule": "course_schedule", "tags": "course_tags", "electives": "course_electives", "metadata": "course_meta", "workload": "course_workload", "rules": "course_rules"}
    table = tables.get(relation)
    if not table:
        return None
    columns = reporting_db.fetch_all_dict("select column_name from information_schema.columns where table_schema = 'knowledge' and table_name = %s", (table,))
    valid = {item["column_name"] for item in columns}
    key_rows = reporting_db.fetch_all_dict("select kcu.column_name, tc.constraint_type from information_schema.table_constraints tc join information_schema.key_column_usage kcu on kcu.constraint_name = tc.constraint_name and kcu.table_schema = tc.table_schema where tc.table_schema = 'knowledge' and tc.table_name = %s and tc.constraint_type in ('PRIMARY KEY', 'FOREIGN KEY')", (table,))
    protected = {item["column_name"] for item in key_rows}
    assignments = [f"{column} = %s" for column in row if column in valid and column not in protected]
    values = [row[column] for column in row if column in valid and column not in protected]
    if not assignments:
        return None
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


def fetch_overview(days: int = 7) -> dict:
    users = reporting_db.fetch_one_dict(
        """
        select count(*)::int as total,
               count(*) filter (where account_status = 'active')::int as active
          from account.accounts
        """
    )
    conversations = reporting_db.fetch_one_dict(
        "select count(*)::int as total, count(*) filter (where status = 'normal')::int as active from chat.conversations where status_updated_at >= now() - (%s * interval '1 day')",
        (days,),
    )
    applications = reporting_db.fetch_all_dict(
        "select coalesce(status, '<unknown>') as status, count(*)::int as total from sis.applications group by status order by status",
    )
    checklist = reporting_db.fetch_one_dict(
        "select count(*)::int as total, count(*) filter (where submitted)::int as submitted, count(*) filter (where not submitted)::int as outstanding from sis.application_checklist_items"
    )
    processing = reporting_db.fetch_one_dict(
        "select round(avg(extract(epoch from (changed_at - a.submission_date)) / 86400)::numeric, 1) as value from sis.application_status_history h join sis.applications a on a.application_id = h.application_id where a.submission_date is not null and h.new_status in ('ACCEPTED', 'REJECTED')"
    ) or {}
    application_insights = {
        "by_term": reporting_db.fetch_all_dict(
            "select coalesce(admission_term, '<unknown>') as label, count(*)::int as total from sis.applications group by admission_term order by total desc"
        ),
        "monthly": reporting_db.fetch_all_dict(
            "select to_char(date_trunc('month', submission_date), 'Mon YYYY') as label, count(*)::int as total from sis.applications where submission_date is not null and submission_date >= now() - interval '12 months' group by date_trunc('month', submission_date) order by date_trunc('month', submission_date)"
        ),
        "average_processing_days": processing.get("value") or 0,
    }
    cases = reporting_db.fetch_one_dict(
        "select count(*)::int as total, count(*) filter (where status not in ('resolved', 'closed'))::int as open from chat.cases where created_at >= now() - (%s * interval '1 day')",
        (days,),
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
        "checklist": checklist or {"total": 0, "submitted": 0, "outstanding": 0},
        "application_insights": application_insights,
        "cases": cases or {"total": 0, "open": 0},
        "catalogue": catalogue or {"universities": 0, "programs": 0, "courses": 0},
        "recent_activity": activity,
    }
