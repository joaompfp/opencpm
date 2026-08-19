"""Trace activities with matching forward dates but mismatched late dates.
Isolates backward-pass math issues."""
import sys

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "None"


def main():
    sched = load_xer("/XD/JLL/LIS1/Planning/LIS10-Draft 21.xer")
    solver = Solver(sched)
    solver.solve()
    acts = sched.activities
    by_code = {a.task_code: a for a in acts.values()}

    print("=== Forward-matching, backward-mismatching activities ===")
    found = 0
    for a in sched.activities.values():
        if a.status.value == "TK_Complete" or a.ref_early_start is None or a.early_start is None:
            continue
        if a.ref_late_start is None or a.late_start is None:
            continue
        # forward must match
        if abs((a.early_start - a.ref_early_start).total_seconds()) > 30 * 60:
            continue
        if abs((a.early_finish - a.ref_early_finish).total_seconds()) > 30 * 60:
            continue
        # backward mismatch
        d_ls = (a.late_start - a.ref_late_start).total_seconds() / 3600.0
        if abs(d_ls) <= 0.5:
            continue
        print(f"\nBACK DIV {a.task_code} {a.name[:40]}  LS delta={d_ls:+.2f}h")
        print(f"  P6 LS={fmt(a.ref_late_start)} LF={fmt(a.ref_late_finish)} TF={a.ref_total_float}")
        print(f"  cal LS={fmt(a.late_start)} LF={fmt(a.late_finish)} TF={a.total_float_hours}")
        print(f"  cstr={a.constraint_type} dur={a.duration_hours} cal={a.calendar_id}")
        for sid, rt, lag in sched.successors(a.task_id):
            s = acts.get(sid)
            if not s:
                continue
            print(f"  succ {s.task_code:10s} {rt.value} lag={lag}h P6_LS={fmt(s.ref_late_start)} P6_LF={fmt(s.ref_late_finish)} cal_LS={fmt(s.late_start)} cal_LF={fmt(s.late_finish)}")
        found += 1
        if found >= 10:
            break
    print(f"\nshown: {found}")


def abs_l(x):
    return abs(x)


if __name__ == "__main__":
    main()
