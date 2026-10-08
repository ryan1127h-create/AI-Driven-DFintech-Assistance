"""
The domain's processing stages, one package or module per workflow stage,
run in this order by workflow.py:

    s3_constraints/   catalog classification, hard eligibility, degree progress
    s4_slots.py       open requirement groups derived from degree progress
    s5_scoring/       per-group scoring and selection

Stages never import each other: each takes the previous stage's output
(see models.py) and reads rules and tunables only from policy/.
"""
