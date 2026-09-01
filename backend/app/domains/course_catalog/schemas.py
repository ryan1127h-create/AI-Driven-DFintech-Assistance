"""Response schema for the course catalog API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CourseOut(BaseModel):
    course_code: str
    title: str
    annex_title: Optional[str] = None
    nusmods_title: Optional[str] = None
    annex_presence: Optional[str] = None
    annex_section: Optional[str] = None
    module_credit: Optional[float] = None
    faculty: Optional[str] = None
    department: Optional[str] = None
    description: Optional[str] = None
    prerequisite: Optional[str] = None
    corequisite: Optional[str] = None
    preclusion: Optional[str] = None
    semester_count: Optional[int] = None
    source_url: Optional[str] = None
