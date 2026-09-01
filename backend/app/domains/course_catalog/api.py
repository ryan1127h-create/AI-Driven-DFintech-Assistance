from fastapi import APIRouter

from app.domains.course_catalog import service
from app.domains.course_catalog.schemas import CourseOut

router = APIRouter()


@router.get("/courses", response_model=list[CourseOut])
def list_courses() -> list[CourseOut]:
    """The full raw course catalog, unfiltered — no login required, same as
    the curriculum page's previous data source."""
    return [CourseOut(**row) for row in service.list_courses()]
