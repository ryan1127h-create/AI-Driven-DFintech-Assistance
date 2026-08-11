"""Public interface exposed by the checklist module to other modules."""

from app.modules.checklist.service import get_checklist

__all__ = ["get_checklist"]

