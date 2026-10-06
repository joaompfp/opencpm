"""Find activities where ALL successors match P6's late dates but own LS/LF differs.
This isolates the pure backward-pass constraint bug (no cascade contamination)."""
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
    acts = sched.activities

    print("=== Backward root divergences (successors match, own LS doesn't) ===")
    found = 0
    for a in sched.activities.values():
        if a.status.value == "TK_Complete" or a.ref_late_start is None or a.late_start is None:
            continue
        succs = sched.successors(a.task_id)
        if not succs:
            continue
        # all successors' late_start must match P6
        succs_ok = True
        for sid, rt, lag in succs:
            s = acts.get(sid)
            if s is None or s.ref_late_start is None or s.late_start is None:
                succs_ok = False
                break
            if abs((s.late_start - s.ref_late_start).total_seconds()) > 30 * 60:
                succs_ok = False
                break
        if not succs_ok:
            continue
        # own LS differs
        d = (a.late_start - a.ref_late_start).total_seconds() / 3600.0
        if abs(d) > 0.5:
            print(f"\nROOT {a.task_code} {a.name[:40]}  LS delta={d:+.1f}h")
            print(f"  P6 LS={fmt(a.ref_late_start)} LF={fmt(a.ref_late_finish)} | calc LS={fmt(a.late_start)} LF={fmt(a.late_finish)}")
            print(f"  cstr={a.constraint_type} dur={a.duration_hours} cal={a.calendar_id} type={a.task_type.value}")
            for sid, rt, lag in succs:
                s = acts[sid]
                print(f"  succ {s.task_code:10s} {rt.value} lag={lag} P6_LS={fmt(s.ref_late_start)} calc_LS={fmt(s.late_start)}")
            found += 1
            if found >= 10:
                break
    print(f"\nshown: {found}")


if __name__ == "__main__":
    main()
