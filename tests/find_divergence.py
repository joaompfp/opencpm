"""Find the first divergence point in the network (cascade root)."""
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

    order = solver._topo_order()

    print("First 30 activities in topo order where calc != P6:")
    shown = 0
    for tid in order:
        a = acts[tid]
        if a.status.value == "TK_Complete":
            continue
        if a.ref_early_start is None or a.early_start is None:
            continue
        diff = (a.early_start - a.ref_early_start).total_seconds() / 3600.0
        if abs(diff) > 0.5:
            print(f"\nDIVERGE {a.task_code} {a.name[:45]}")
            print(f"  diff={diff:+.0f}h  P6 ES={fmt(a.ref_early_start)} calc ES={fmt(a.early_start)}")
            print(f"  P6 EF={fmt(a.ref_early_finish)} calc EF={fmt(a.early_finish)}")
            print(f"  status={a.status.value} cstr={a.constraint_type} act_start={fmt(a.actual_start)} dur={a.duration_hours} remain={a.remaining_hours} cal={a.calendar_id}")
            for pid, rt, lag in a.predecessors:
                p = acts.get(pid)
                if p:
                    pd = ""
                    if p.ref_early_finish and p.early_finish:
                        pd = f"({(p.early_finish - p.ref_early_finish).total_seconds()/3600:+.0f}h)"
                    print(f"    pred {p.task_code:12s} {p.name[:35]:35s} {rt.value} lag={lag}h  P6_EF={fmt(p.ref_early_finish)} calc_EF={fmt(p.early_finish)} {pd} st={p.status.value[:4]} cstr={p.constraint_type}")
            shown += 1
            if shown >= 15:
                break


if __name__ == "__main__":
    main()
