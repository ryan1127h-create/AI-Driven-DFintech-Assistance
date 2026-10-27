"""
The domain's processing stages, one package per workflow stage, run by
workflow.py:

    s3_facts/   each programme's catalogue facts -> a view by aspect, with sources and conflicts
    s4_fit/     each view read against the applicant
    s6_modes/   each mode's result from the stages above

(S1, S2 and S7 live in the tools layer; there is no S5.) Stages never
import each other: each takes the previous stage's output (see models.py)
and reads rules only from policy/.
"""
