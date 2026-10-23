from fastapi import APIRouter, Depends

from app.domains.admin import service
from app.domains.admin.schemas import AdminApplication, AdminApplicationList, AdminApplicationUpdate, AdminChecklistUpdate, AdminCourseUpdate, AdminKnowledgeUpdate, AdminOverview, AdminUser, AdminUserList, AdminUserUpdate, AdminEscalationCase, AdminEscalationCaseList, AdminEscalationUpdate, AdminProgramUpdate
from app.domains.alumni.schemas import StaffAlumnusCreate, StaffAlumnusFields
from app.domains.auth.interface import get_current_user_id

router = APIRouter(prefix="/admin")


@router.get("/escalations", response_model=AdminEscalationCaseList)
def list_admin_escalations(user_id: str = Depends(get_current_user_id)):
    return service.list_escalations(user_id)


@router.get("/escalations/{case_id}", response_model=AdminEscalationCase)
def get_admin_escalation(case_id: str, user_id: str = Depends(get_current_user_id)):
    return service.get_escalation(user_id, case_id)


@router.patch("/escalations/{case_id}", response_model=AdminEscalationCase)
def update_admin_escalation(case_id: str, update: AdminEscalationUpdate, user_id: str = Depends(get_current_user_id)):
    return service.resolve_escalation(user_id, case_id, update.resolution_notes)


@router.get("/overview", response_model=AdminOverview)
def get_admin_overview(user_id: str = Depends(get_current_user_id)):
    return service.get_overview(user_id)


@router.get("/users", response_model=AdminUserList)
def list_admin_users(search: str = "", user_id: str = Depends(get_current_user_id)):
    return service.list_users(user_id, search)


@router.get("/users/{target_user_id}", response_model=AdminUser)
def get_admin_user(target_user_id: str, user_id: str = Depends(get_current_user_id)):
    return service.get_user(user_id, target_user_id)


@router.patch("/users/{target_user_id}", response_model=AdminUser)
def update_admin_user(target_user_id: str, update: AdminUserUpdate, user_id: str = Depends(get_current_user_id)):
    return service.update_user(user_id, target_user_id, update.model_dump(exclude_none=True))


@router.delete("/users/{target_user_id}")
def delete_admin_user(target_user_id: str, user_id: str = Depends(get_current_user_id)):
    return service.delete_user(user_id, target_user_id)


@router.get("/applications", response_model=AdminApplicationList)
def list_admin_applications(user_id: str = Depends(get_current_user_id)):
    return service.list_applications(user_id)


@router.get("/applications/{application_id}")
def get_admin_application(application_id: str, user_id: str = Depends(get_current_user_id)):
    return service.get_application(user_id, application_id)


@router.patch("/applications/{application_id}")
def update_admin_application(application_id: str, update: AdminApplicationUpdate, user_id: str = Depends(get_current_user_id)):
    # exclude_unset, not exclude_none: an explicit null clears final_decision.
    return service.update_application(user_id, application_id, update.model_dump(exclude_unset=True))


@router.patch("/checklist/{item_id}")
def update_admin_checklist(item_id: str, update: AdminChecklistUpdate, user_id: str = Depends(get_current_user_id)):
    return service.update_checklist(user_id, item_id, update.submitted)


@router.delete("/applications/{application_id}")
def delete_admin_application(application_id: str, user_id: str = Depends(get_current_user_id)):
    return service.delete_application(user_id, application_id)


@router.get("/conversations")
def list_admin_conversations(user_id: str = Depends(get_current_user_id)):
    return service.list_conversations(user_id)


@router.get("/conversations/{conversation_id}")
def get_admin_conversation(conversation_id: str, user_id: str = Depends(get_current_user_id)):
    return service.get_conversation(user_id, conversation_id)


@router.get("/knowledge")
def list_admin_knowledge(search: str = "", main_table: str = "all", user_id: str = Depends(get_current_user_id)):
    return service.list_knowledge(user_id, search, main_table)


@router.get("/knowledge/courses/{course_code}")
def get_admin_knowledge_course(course_code: str, user_id: str = Depends(get_current_user_id)):
    return service.get_knowledge_course(user_id, course_code)


@router.get("/knowledge/programs/{program_id}")
def get_admin_knowledge_program(program_id: str, user_id: str = Depends(get_current_user_id)):
    return service.get_knowledge_program(user_id, program_id)


@router.patch("/knowledge/programs/{program_id}")
def update_admin_knowledge_program(program_id: str, update: AdminProgramUpdate, user_id: str = Depends(get_current_user_id)):
    return service.update_knowledge_program(user_id, program_id, update.model_dump(exclude_none=True))


@router.patch("/knowledge/courses/{course_code}")
def update_admin_knowledge_course(course_code: str, update: AdminCourseUpdate, user_id: str = Depends(get_current_user_id)):
    return service.update_knowledge_course(user_id, course_code, update.model_dump(exclude_none=True))


@router.patch("/knowledge/courses/{course_code}/{relation}")
def update_admin_knowledge_course_related(course_code: str, relation: str, payload: dict, user_id: str = Depends(get_current_user_id)):
    return service.update_knowledge_course_related(user_id, course_code, relation, payload.get("row", {}))


@router.get("/alumni")
def list_admin_alumni(user_id: str = Depends(get_current_user_id)):
    return service.list_alumni(user_id)


@router.post("/alumni", status_code=201)
def create_admin_alumnus(body: StaffAlumnusCreate, user_id: str = Depends(get_current_user_id)):
    return service.create_alumnus(user_id, body.email, body.model_dump(exclude={"email"}, exclude_unset=True))


@router.patch("/alumni/{alumnus_id}")
def update_admin_alumnus(alumnus_id: str, body: StaffAlumnusFields, user_id: str = Depends(get_current_user_id)):
    return service.update_alumnus(user_id, alumnus_id, body.model_dump(exclude_unset=True))


@router.delete("/alumni/{alumnus_id}")
def delete_admin_alumnus(alumnus_id: str, user_id: str = Depends(get_current_user_id)):
    return service.delete_alumnus(user_id, alumnus_id)


# Declared after the /knowledge/courses/... routes: FastAPI matches in order,
# and this pattern would otherwise capture PATCH /knowledge/courses/{code}.
@router.patch("/knowledge/{category}/{item_id}")
def update_admin_knowledge(category: str, item_id: str, update: AdminKnowledgeUpdate, user_id: str = Depends(get_current_user_id)):
    return service.update_knowledge(user_id, item_id, category, update.model_dump(exclude_none=True))
