"""Chain trace with candidate values: find where whole-day shifts enter."""
import sys

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer

def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "None"

path = "/XD/JLL/LIS10/Planning/LIS10-Draft 21.xer"
sched = load_xer(path)
solver = Solver(sched)
solver.solve()
by_id = {a.task_id: a for a in sched.activities.values()}
by_code = {a.task_code: a for a in sched.activities.values()}

def walk_up(code, depth=0, max_depth=10):
    a = by_code.get(code)
    if a is None:
        print(f"{'  '*depth}{code}: NOT FOUND")
        return
    if depth > max_depth:
        return
    cal = solver.cal_time_for(a)
    cstr = a.constraint_type
    d = (a.late_finish - a.ref_late_finish).total_seconds()/3600 if a.late_finish and a.ref_late_finish else 0
    print(f"{'  '*depth}{a.task_code:8s} cal={a.calendar_id} dur={a.effective_duration:6.1f} "
          f"cstr={cstr}@{fmt(a.constraint_date) if a.constraint_date else '-':16s} "
          f"LF {fmt(a.late_finish)} vs P6 {fmt(a.ref_late_finish)} ({d:+.1f}h)")
    succs = sched.successors(a.task_id)
    if not succs:
        print(f"{'  '*depth}  no succs -> LF=end")
        return
    best = None
    for sid, rtype, lag in succs:
        s = by_id.get(sid)
        if s is None or s.early_start is None:
            continue
        raw = solver._constraint_late_finish(a, s, rtype, lag)
        print(f"{'  '*depth}  -> {s.task_code:8s} {rtype.name} lag={lag:5.0f} raw={fmt(raw)} "
              f"| succ LS {fmt(s.late_start)} P6 {fmt(s.ref_late_start)} | succ LF {fmt(s.late_finish)} P6 {fmt(s.ref_late_finish)}")
        if raw is not None and (best is None or raw < best[0]):
            best = (raw, s)
    if best and a.late_finish is not None and abs((best[0] - a.late_finish).total_seconds()) < 3600:
        walk_up(best[1].task_code, depth + 1, max_depth)

for code in ["A1018", "A7620", "A1080", "A7370"]:
    print(f"\n===== {code} chain =====")
    walk_up(code)
