"""Walk a chain forward from A1015, printing P6 vs calc late dates at each step.
Finds the first node where LS diverges (the root of the backward drift)."""
import sys

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "None"


def main():
    sched = load_xer("/XD/JLL/LIS10/Planning/LIS10-Draft 21.xer")
    solver = Solver(sched)
    solver.solve()
    by_id = {a.task_id: a for a in sched.activities.values()}
    by_code = {a.task_code: a for a in sched.activities.values()}

    # Follow the FS chain: A1015 -> A1048 -> ? (print succs at each node)
    start = by_code.get("A1015")
    visited = set()
    cur = start
    for step in range(12):
        if not cur or cur.task_id in visited:
            break
        visited.add(cur.task_id)
        d = ""
        if cur.ref_late_start and cur.late_start:
            d = f"{(cur.late_start - cur.ref_late_start).total_seconds()/3600:+.0f}h"
        print(f"{step}: {cur.task_code:10s} {cur.name[:32]:32s} P6_LS={fmt(cur.ref_late_start)} calc_LS={fmt(cur.late_start)} {d}")
        succs = sched.successors(cur.task_id)
        if not succs:
            print("   (terminal)")
            break
        nxt = None
        for sid, rt, lag in succs[:3]:
            s = by_id.get(sid)
            if s:
                dd = ""
                if s.ref_late_start and s.late_start:
                    dd = f"{(s.late_start - s.ref_late_start).total_seconds()/3600:+.0f}h"
                print(f"   succ {s.task_code:10s} {rt.value} lag={lag} P6_LS={fmt(s.ref_late_start)} calc_LS={fmt(s.late_start)} {dd}")
                if nxt is None:
                    nxt = s
        cur = nxt


if __name__ == "__main__":
    main()
