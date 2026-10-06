"""Check: are the remaining D21 late-date mismatches downstream of Milestone 20's
stale LF anchor (10-11 16:00, mixed-run artifact)?

If yes, the engine is right per a single-run anchor at scd_end; the file's
late dates are from the previous run. D19 (single-run) at 99.0% proves it.
"""
import sys

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer

path = "/XD/JLL/LIS10/Planning/LIS10-Draft 21.xer"
sched = load_xer(path)
Solver(sched).solve()

# Build reverse adjacency (successor -> predecessors) for reachability
preds_of = {}
for tid, a in sched.activities.items():
    for sid, _, _ in sched.successors(tid):
        preds_of.setdefault(sid, []).append(tid)

ms20 = next(a for a in sched.activities.values() if a.task_code == "Milestone 20")

# All activities upstream of MS20 (reverse BFS)
upstream = set()
queue = [ms20.task_id]
while queue:
    cur = queue.pop(0)
    for p in preds_of.get(cur, []):
        if p not in upstream:
            upstream.add(p)
            queue.append(p)

print(f"MS20 stored: ES={ms20.ref_early_start} LF={ms20.ref_late_finish} TF={ms20.ref_total_float} "
      f"(LF < ES = mixed-run artifact)")
print(f"activities upstream of MS20: {len(upstream)}")

mismatch_total = 0
mismatch_upstream = 0
mismatch_downstream = 0
for a in sched.activities.values():
    if a.ref_early_start is None or a.late_finish is None or a.ref_late_finish is None:
        continue
    d = (a.late_finish - a.ref_late_finish).total_seconds() / 3600
    if abs(d) >= 15:
        mismatch_total += 1
        if a.task_id in upstream or a.task_id == ms20.task_id:
            mismatch_upstream += 1
        else:
            mismatch_downstream += 1

print(f"late-date mismatches (>=15h): {mismatch_total}")
print(f"  upstream of MS20 (stale anchor): {mismatch_upstream}")
print(f"  NOT upstream: {mismatch_downstream}")
