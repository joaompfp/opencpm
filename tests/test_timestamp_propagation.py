"""Test: do P6 timestamp-keeping chains flow only from MILESTONE successors?

Hypothesis from A3920 (FF->MS18 MEO 08:36, P6 keeps 08:36) vs A1015
(FS->A1048 task, P6 snaps): constraint timestamps propagate through
zero-duration milestone pins but NOT through task-to-task chains.
"""
import sys
from collections import Counter

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer

path = "/XD/JLL/LIS1/Planning/LIS10-Draft 21.xer"
sched = load_xer(path)
Solver(sched).solve()
by_code = {a.task_code: a for a in sched.activities.values()}

# rows where our LF is off by >= 15h
mismatch = []
for a in sched.activities.values():
    if a.ref_early_start is None or a.late_finish is None or a.ref_late_finish is None:
        continue
    d = (a.late_finish - a.ref_late_finish).total_seconds() / 3600
    if abs(d) >= 15:
        mismatch.append(a)

print(f"{len(mismatch)} rows with LF off by >=15h")
driver_stats = Counter()
examples = []
for a in mismatch:
    # find the driving successor: the one whose candidate produced our LF
    # (recompute candidates; the min is the driver)
    cal = None
    # reuse solver logic: candidates per successor
    solver = Solver(sched)
    # skip recompute; approximate: list all successors with their P6 LF minute
    succs = sched.successors(a.task_id)
    if not succs:
        driver_stats["no_successors"] += 1
        continue
    for sid, rtype, lag in succs:
        s = sched.activities[sid]
        if s.late_finish is None:
            continue
        if rtype.name in ("FF", "SF") and s.late_finish.minute in (24, 36):
            driver_stats[f"{rtype.name}_from_milestone_ts"] += 1
            examples.append((a.task_code, rtype.name, s.task_code, s.task_type, s.late_finish))
            break
        if rtype.name in ("FS", "SS") and s.late_start and s.late_start.minute in (24, 36):
            driver_stats[f"{rtype.name}_from_milestone_ts"] += 1
            examples.append((a.task_code, rtype.name, s.task_code, s.task_type, s.late_start))
            break
    else:
        driver_stats["successor_ts_not_found"] += 1
        examples.append((a.task_code, "?", "?", "?", None))

print(dict(driver_stats))
print("\nexamples (task, rel, successor, succ_type, ts):")
for e in examples[:15]:
    print("  ", e)
