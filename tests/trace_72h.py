"""Trace a +72h cluster activity to find the systematic offset."""
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
    by_code = {a.task_code: a for a in acts.values()}

    for code in ["A6150", "A23001", "A7730", "A6960"]:
        a = by_code.get(code)
        if not a:
            continue
        print(f"\n=== {code} {a.name[:45]}")
        print(f"  cal={a.calendar_id} dur={a.duration_hours} remain={a.remaining_hours} st={a.status.value} cstr={a.constraint_type}")
        print(f"  P6 ES={fmt(a.ref_early_start)} EF={fmt(a.ref_early_finish)}")
        print(f"  calc ES={fmt(a.early_start)} EF={fmt(a.early_finish)}")
        for pid, rt, lag in a.predecessors:
            p = acts.get(pid)
            if not p:
                continue
            pd = ""
            if p.ref_early_finish and p.early_finish:
                pd = f"delta={(p.early_finish - p.ref_early_finish).total_seconds()/3600:+.0f}h"
            print(f"  pred {p.task_code:10s} {p.name[:32]:32s} {rt.value} lag={lag}h P6_EF={fmt(p.ref_early_finish)} calc_EF={fmt(p.early_finish)} {pd} cal={p.calendar_id}")


def fmt_(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "None"


if __name__ == "__main__":
    main()
