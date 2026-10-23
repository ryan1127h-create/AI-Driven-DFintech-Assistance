"""
Lifecycle domain's public interface: the only module outside this domain
allowed to import from app.domains.lifecycle (besides its api.py, which the
router mounts).
"""

from __future__ import annotations

from app.domains.lifecycle import service


def progress_text(user_id: str) -> str | None:
    """A current or graduating student's degree progress as plain sentences
    for the assistant's context; None for anyone else."""
    return service.progress_text(user_id)
