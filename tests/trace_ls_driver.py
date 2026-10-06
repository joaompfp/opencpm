"""Backward-pass driver trace: for each LS/LF mismatch, show which successor
relationship drove our LF (type, lag, successor LS/LF) vs P6's stored value.

Research backing: docs/reference/02-p6-constraints-and-settings.md — P6 does
NOT always snap constraint timestamps on zero-duration late dates; LS < ES
with negative float is legitimate under constrained finish (A1019 TF=-0.6).
"""
import sys

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


def main(path, codes=None):
    sched = load_xer(path)
    Solver(sched).solve()
    by_code = {a.task_code: a for a in sched.activities.values()}

    if codes is None:
        codes = ["A1019", "A7400", "A7720", "A5150", "A5110", "A35251", "A35241", "A7670", "A7700"]

    for code in codes:
        a = by_code.get(code)
        if a is None:
            print(f"\n{code}: NOT FOUND")
            continue
        ls_d = delta(a.late_start, a.ref_late_start)
        lf_d = delta(a.late_finish, a.ref_late_finish)
        es_d = delta(a.early_start, a.ref_early_start)
        print(f"\n=== {code} ({a.task_type}, dur={a.duration_hours}) ===")
        print(f"  ES calc={fmt(a.early_start)} P6={fmt(a.ref_early_start)} {es_d}")
        print(f"  LS calc={fmt(a.late_start)} P6={fmt(a.ref_late_start)} {ls_d}")
        print(f"  LF calc={fmt(a.late_finish)} P6={fmt(a.ref_late_finish)} {lf_d}")
        print(f"  TF calc={a.total_float_hours} P6={a.ref_total_float}")
        if a.constraint_type and a.constraint_date:
            print(f"  constraint: {a.constraint_type} @ {a.constraint_date}")
        succs = sched.successors(a.task_id)
        print(f"  successors ({len(succs)}):")
        for sid, rtype, lag in succs:
            s = sched.activities[sid]
            print(f"    -> {s.task_code:8s} {rtype} lag={lag}h | "
                  f"LS calc={fmt(s.late_start)} P6={fmt(s.ref_late_start)} | "
                  f"LF calc={fmt(s.late_finish)} P6={fmt(s.ref_late_finish)}")
        preds = getattr(sched, "predecessors", None)
        if preds is not None:
            preds = preds(a.task_id)
            print(f"  predecessors ({len(preds)}):")
            for pid, rtype, lag in preds:
                p = sched.activities[pid]
                print(f"    <- {p.task_code:8s} {rtype} lag={lag}h | "
                      f"EF calc={fmt(p.early_finish)} P6={fmt(p.ref_early_finish)} | "
                      f"LF calc={fmt(p.late_finish)} P6={fmt(p.ref_late_finish)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/XD/JLL/LIS10/Planning/LIS10-Draft 21.xer",
         sys.argv[2:] or None)
