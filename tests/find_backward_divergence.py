"""Find where the -24h backward-pass shift enters in samples/02.

Prints calc vs P6 LS/LF in topo order; first divergent row shows the
successor link that drove it.
"""
import sys

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "None"


def main(path):
    sched = load_xer(path)
    solver = Solver(sched)
    solver.solve()
    order = solver._topo_order()
    print(f"project_end={sched.project_end}")

    for tid in order:
        a = sched.activities[tid]
        if a.ref_late_start is None or a.late_start is None:
            continue
        d_ls = (a.late_start - a.ref_late_start).total_seconds() / 3600
        d_lf = (a.late_finish - a.ref_late_finish).total_seconds() / 3600
        if abs(d_ls) < 0.5 and abs(d_lf) < 0.5:
            continue
        print(f"\nFIRST DIVERGENCE: {a.task_code} {a.task_type} dur={a.duration_hours}")
        print(f"  LS calc={a.late_start} P6={a.ref_late_start} ({d_ls:+.0f}h)")
        print(f"  LF calc={a.late_finish} P6={a.ref_late_finish} ({d_lf:+.0f}h)")
        print(f"  TF calc={a.total_float_hours} P6={a.ref_total_float}")
        print(f"  ES calc={a.early_start} P6={a.ref_early_start}")
        print(f"  successors:")
        for sid, rtype, lag in sched.successors(tid):
            s = sched.activities[sid]
            print(f"    -> {s.task_code} {rtype} lag={lag} | LS calc={s.late_start} P6={s.ref_late_start} | LF calc={s.late_finish} P6={s.ref_late_finish}")
        return
    print("no divergence in backward pass")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "samples/02-multi-calendar-lags.xer")
