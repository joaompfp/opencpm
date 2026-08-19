"""Find FIRST activity whose preds all match P6 but computed ES differs.
This isolates local semantic bugs (not cascades)."""
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

    order = solver._topo_order()

    print("=== Activities with all-matching preds but own ES differs (local bugs) ===")
    found = 0
    for tid in order:
        a = acts[tid]
        if a.status.value == "TK_Complete" or a.ref_early_start is None or a.early_start is None:
            continue
        if not a.predecessors:
            continue
        # all preds must match P6
        preds_ok = True
        for pid, rt, lag in a.predecessors:
            p = acts.get(pid)
            if p is None or p.ref_early_finish is None or p.early_finish is None:
                preds_ok = False
                break
            if abs((p.early_finish - p.ref_early_finish).total_seconds()) > 30 * 60:
                preds_ok = False
                break
        if not preds_ok:
            continue
        # this activity diverges?
        d = (a.early_start - a.ref_early_start).total_seconds() / 3600.0
        if abs(d) > 0.5:
            print(f"\nLOCAL DIV {a.task_code} {a.name[:42]}  diff={d:+.2f}h")
            print(f"  P6 ES={fmt(a.ref_early_start)}  calc={fmt(a.early_start)}")
            print(f"  P6 EF={fmt(a.ref_early_finish)}  calc={fmt(a.early_finish)}")
            print(f"  status={a.status.value} cstr={a.constraint_type} cal={a.calendar_id} dur={a.duration_hours}")
            for pid, rt, lag in a.predecessors:
                p = acts[pid]
                print(f"  pred {p.task_code:10s} {rt.value} lag={lag}h P6_EF={fmt(p.ref_early_finish)} calc_EF={fmt(p.early_finish)}")
            found += 1
            if found >= 12:
                break
    print(f"\nTotal local divergences shown: {found}")


if __name__ == "__main__":
    main()
