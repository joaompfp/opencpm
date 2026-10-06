"""Partition remaining D21 LS mismatches by terminal subnetwork.

The research doc (03-xer-date-storage.md §6) proves Milestone 20 stores
LF=10-11 16:00 while ES=10-13 08:00 with TF=0 — a mixed-stamp artifact of
two runs. Every activity whose late dates are driven by that terminal in the
STORED file inherits the old run's values; our engine computes the current
run. Those rows are unreproducible BY CONSTRUCTION. This script measures how
much of the remaining mismatch population sits in Milestone-20-driven
subnetworks vs. elsewhere (genuine engine gaps).
"""
import sys
from collections import Counter, deque

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer


def main(path):
    sched = load_xer(path)
    Solver(sched).solve()

    def same(a, b, tol=1800):
        if a is None or b is None:
            return a is b
        return abs((a - b).total_seconds()) <= tol

    # Find terminals whose stored late dates are self-contradictory
    # (ref LF < ref ES with TF >= 0) = mixed-stamp terminals
    bad_terminals = set()
    for a in sched.activities.values():
        if a.ref_early_start is None or a.ref_late_finish is None:
            continue
        if not sched.successors(a.task_id) and a.ref_late_finish < a.ref_early_finish:
            bad_terminals.add(a.task_id)
            print(f"MIXED-STAMP terminal: {a.task_code} ref ES={a.ref_early_start} "
                  f"ref LF={a.ref_late_finish} TF={a.ref_total_float}")

    # Reachability: which activities have a path to a bad terminal?
    # Reverse BFS from bad terminals over predecessor edges.
    pred_map = {tid: [p for p, _, _ in a.predecessors if p in sched.activities]
                for tid, a in sched.activities.items()}
    reachable = set()
    q = deque(bad_terminals)
    while q:
        tid = q.popleft()
        for p in pred_map.get(tid, []):
            if p not in reachable:
                reachable.add(p)
                q.append(p)

    print(f"\nActivities upstream of mixed-stamp terminals: {len(reachable)}")

    # Classify mismatches
    in_bad = Counter()
    out_bad = Counter()
    n = 0
    for a in sched.activities.values():
        if a.ref_early_start is None or a.ref_late_start is None or a.late_start is None:
            continue
        if a.status.value.endswith("Complete"):
            continue
        if same(a.late_start, a.ref_late_start) and same(a.late_finish, a.ref_late_finish):
            continue
        n += 1
        if a.task_id in reachable:
            in_bad["count"] += 1
            d = (a.late_start - a.ref_late_start).total_seconds() / 3600
            in_bad[round(d / 8)] += 1
        else:
            out_bad["count"] += 1
            d = (a.late_start - a.ref_late_start).total_seconds() / 3600
            out_bad[round(d / 8)] += 1

    print(f"total late-date mismatches: {n}")
    print(f"  in mixed-stamp subnetworks: {in_bad['count']}  (working-day deltas: "
          f"{dict(sorted((k, v) for k, v in in_bad.items() if k != 'count'))})")
    print(f"  OUTSIDE (genuine engine gap): {out_bad['count']}  (working-day deltas: "
          f"{dict(sorted((k, v) for k, v in out_bad.items() if k != 'count'))})")
    if out_bad["count"]:
        print("\nExamples OUTSIDE mixed-stamp zones:")
        shown = 0
        for a in sched.activities.values():
            if a.ref_early_start is None or a.ref_late_start is None or a.late_start is None:
                continue
            if a.status.value.endswith("Complete"):
                continue
            if same(a.late_start, a.ref_late_start) and same(a.late_finish, a.ref_late_finish):
                continue
            if a.task_id in reachable:
                continue
            print(f"  {a.task_code:8s} dur={a.duration_hours:6.1f} LS calc={a.late_start} "
                  f"P6={a.ref_late_start} | LF calc={a.late_finish} P6={a.ref_late_finish} "
                  f"cstr={a.constraint_type}@{a.constraint_date}")
            shown += 1
            if shown >= 15:
                break


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/XD/JLL/LIS10/Planning/LIS10-Draft 21.xer")
