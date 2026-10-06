"""Parity on the self-consistent subset: activities where P6's stored TF
reconciles with (LF-EF) in calendar hours. If our backward pass is right,
LS/LF must match on this subset regardless of the stale-rows problem."""
import sys

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer


def main():
    sched = load_xer("/XD/JLL/LIS10/Planning/LIS10-Draft 21.xer")
    solver = Solver(sched)
    solver.solve()

    ls_ok = lf_ok = total = 0
    bad = []
    for a in sched.activities.values():
        if a.status.value == "TK_Complete":
            continue
        if a.ref_total_float is None or a.ref_late_start is None or a.late_start is None:
            continue
        # Check P6 self-consistency: working hours between ref LS and ref ES == ref TF
        cal = solver.cal_time_for(a)
        ref_span = cal.working_hours_between(a.ref_early_start, a.ref_late_start) if a.ref_early_start else None
        if ref_span is None:
            continue
        if abs(ref_span - a.ref_total_float) > 1.0:
            continue  # stale row — exclude
        total += 1
        if abs((a.late_start - a.ref_late_start).total_seconds()) <= 1800:
            ls_ok += 1
        else:
            bad.append((a.task_code, a.late_start, a.ref_late_start))
        if abs((a.late_finish - a.ref_late_finish).total_seconds()) <= 1800:
            lf_ok += 1
    print(f"Self-consistent subset: {total} activities")
    print(f"LS match: {ls_ok}/{total} ({100*ls_ok/max(total,1):.1f}%)")
    print(f"LF match: {lf_ok}/{total} ({100*lf_ok/max(total,1):.1f}%)")
    print("First 8 LS mismatches:")
    for code, ours, ref in bad[:8]:
        print(f"  {code:12s} calc={ours} P6={ref}")


if __name__ == "__main__":
    main()
