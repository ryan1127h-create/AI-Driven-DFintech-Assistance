from datetime import datetime

from pydantic import BaseModel


class AdminStat(BaseModel):
    total: int
    active: int | None = None


class AdminOverview(BaseModel):
    generated_at: datetime
    users: AdminStat
    conversations: AdminStat
    applications: dict[str, int]
    checklist: dict[str, int]
    application_insights: dict
    cases: dict[str, int]
    catalogue: dict[str, int]
    recent_activity: list[dict]


class AdminUserConversation(BaseModel):
    conversation_id: str
    turn_count: int | None = 0
    total_messages: int | None = 0
    status: str | None = None
    status_updated_at: datetime | None = None


class AdminUserApplication(BaseModel):
    application_id: str
    application_no: str | None = None
    admission_term: str | None = None
    status: str | None = None
    final_decision: str | None = None
    submission_date: datetime | None = None
    updated_at: datetime | None = None


class AdminUser(BaseModel):
    user_id: str
    email: str
    full_name: str
    account_status: str
    role: str
    is_anonymous: bool
    last_login_at: datetime | None = None
    created_at: datetime
    conversations: list[AdminUserConversation] = []
    applications: list[AdminUserApplication] = []


class AdminUserList(BaseModel):
    items: list[AdminUser]
    total: int


class AdminUserUpdate(BaseModel):
    full_name: str | None = None
    account_status: str | None = None
    role: str | None = None


class AdminApplication(BaseModel):
    application_id: str
    application_no: str | None = None
    applicant_email: str | None = None
    application_type: str | None = None
    admission_term: str | None = None
    submission_date: datetime | None = None
    status: str | None = None
    final_decision: str | None = None
    updated_at: datetime | None = None
    checklist_total: int = 0
    checklist_submitted: int = 0


class AdminApplicationList(BaseModel):
    items: list[AdminApplication]
    total: int


class AdminApplicationUpdate(BaseModel):
    status: str | None = None
    final_decision: str | None = None


class AdminChecklistUpdate(BaseModel):
    submitted: bool


class AdminEscalationCase(BaseModel):
    id: str
    shortId: str
    user_id: str | None = None
    name: str
    email: str | None = None
    initials: str
    trigger: str
    origin: str
    category: str
    priority: str
    summary: str
    status: str
    createdDate: str
    createdTime: str
    resolvedAt: str | None = None
    resolvedBy: str | None = None
    resolutionNotes: str | None = None


class AdminEscalationCaseList(BaseModel):
    items: list[AdminEscalationCase]
    total: int
    stats: dict[str, int | str]


class AdminKnowledgeUpdate(BaseModel):
    label: str | None = None
    why: str | None = None
    required: bool | None = None
    human_status: str | None = None
    next_step: str | None = None


class AdminCourseUpdate(BaseModel):
    title: str | None = None
    annex_section: str | None = None
    annex_intake: str | None = None
    module_credit: int | None = None
    status: str | None = None
