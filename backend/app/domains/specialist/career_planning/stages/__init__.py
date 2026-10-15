"""
The domain's processing stages, one package per workflow stage, run by
workflow.py:

    s3_evidence/   profile facts and courses -> per-skill evidence and status
    s4_fit/        role fit from that evidence (exploration, compare)
    s5_roadmap/    dated phases and milestones (plan)
    s6_modes/      each mode's result from the stages above

Stages never import each other: each takes the previous stage's output
(see models.py) and reads rules and tunables only from policy/.
"""
