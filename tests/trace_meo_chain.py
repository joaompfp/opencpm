"""Trace the CS_MEO chain backward pass on LIS10-Draft 21.

The Cx chain (Milestone 18 CS_MEO at 2027-07-14 08:36 -> ... -> Milestone 20)
reproduces exactly in the forward pass; the backward pass leaves a residue
on Draft 21 (LS parity ~20% vs Draft 19's 96.7%). Print calc vs P6 LS/LF at
every hop around the constrained milestone so the propagation error is
visible. Research backing: docs/reference/02-p6-constraints-and-settings.md
(CS_MEO pins both EF and LF; residue is genuine P6 output).
"""
import sys
from datetime import datetime

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "None"


def delta(a, b):
    if a is None or b is None:
        return ""
    return f"{(a - b).total_seconds() / 3600:+.1f}h"


def main(path):
    sched = load_xer(path)
    Solver(sched).solve()
    by_code = {a.task_code: a for a in sched.activities.values()}

    # Find CS_MEO constrained activities (the 08:36 pin lives on the Cx chain)
    meo = [
        a for a in sched.activities.values()
        if a.constraint_type == "CS_MEO" and a.constraint_date is not None
    ]
    print(f"CS_MEO activities: {len(meo)}")
    anchors = []
    for a in meo:
        # walk upstream one hop to see predecessors, then downstream chain
        preds = sched.predecessors(a.task_id) if hasattr(sched, "predecessors") else []
        print(f"\n  {a.task_code} MEO at {a.constraint_date} ({a.task_type}, dur={a.duration_hours})")

    # Walk the full chain: from each MEO anchor, downstream successors
    seen = set()

    def walk(tid, depth=0):
        if depth > 12 or tid in seen:
            return
        seen.add(tid)
        a = sched.activities[tid]
        ls_d = delta(a.late_start, a.ref_late_start)
        lf_d = delta(a.late_finish, a.ref_late_finish)
        es_d = delta(a.early_start, a.ref_early_start)
        flag = "  <<<" if ls_d not in ("", "+0.0h") or lf_d not in ("", "+0.0h") else ""
        print(
            f"{'  ' * depth}{a.task_code:8s} {a.task_type[:8]:8s} dur={a.duration_hours:6.1f} "
            f"ES {fmt(a.early_start)[5:]} vs {fmt(a.ref_early_start)[5:]} {es_d} | "
            f"LS {fmt(a.late_start)[5:]} vs {fmt(a.ref_late_start)[5:]} {ls_d} | "
            f"LF {fmt(a.late_finish)[5:]} vs {fmt(a.ref_late_finish)[5:]} {lf_d}{flag}"
        )
        for sid, rtype, lag in sched.successors(tid):
            walk(sid, depth + 1)

    for a in meo:
        print(f"\n=== chain downstream of {a.task_code} (MEO {a.constraint_date}) ===")
        seen = set()
        walk(a.task_id)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/XD/JLL/LIS1/Planning/LIS10-Draft 21.xer")
