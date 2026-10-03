"""Recomputes the derived labels (app/domains/derived_labels/) for every user
and stores them on profile.derived. Time is an input to the drop-off and
graduation risks, so this is meant to run on a schedule as well as after a
rules change.

    cd backend
    python -m scripts.compute_derived_labels            # compute and store
    python -m scripts.compute_derived_labels --dry-run  # print only, no writes
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from app.domains.derived_labels import service
from app.domains.derived_labels.rules import RULES_VERSION
from app.domains.profile import interface as profile_interface


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the labels without storing them")
    args = parser.parse_args()

    user_ids = profile_interface.list_user_ids()
    tally: dict[str, Counter] = {"profile_usability": Counter(), "motivation_segment": Counter(), "drop_off_risk": Counter()}
    failed = 0
    for user_id in user_ids:
        try:
            labels = service.compute_labels(user_id) if args.dry_run else service.recompute(user_id)
        except Exception as exc:  # one bad profile shouldn't stop the run
            failed += 1
            print(f"FAILED {user_id}: {exc!r}", file=sys.stderr)
            continue
        for key, counter in tally.items():
            counter[str(labels[key])] += 1
        if args.dry_run:
            print(user_id, json.dumps(labels, ensure_ascii=False, default=str))

    action = "computed (dry run)" if args.dry_run else "stored"
    print(f"{len(user_ids) - failed}/{len(user_ids)} users {action}, rules {RULES_VERSION}")
    for key, counter in tally.items():
        print(f"  {key}: {dict(counter)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
