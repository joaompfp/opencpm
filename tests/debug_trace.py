"""Deep-dive: why does openCPM ES differ from P6 for specific activities?"""
import sys
from collections import Counter

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

    acts = sched.activities
    by_code = {a.task_code: a for a in acts.values()}
    print("data_date:", fmt(sched.data_date))
    print("project_end (calc):", fmt(sched.project_end))

    print("Constraints:", Counter(a.constraint_type for a in acts.values() if a.constraint_type))

    # Only compare NOT-STARTED activities (P6 stores completed ES as data date)
    ns = [a for a in acts.values() if a.status.value == "TK_NotStart"]
    print(f"\nNotStarted: {len(ns)}")

    diffs = []
    for a in ns:
        if a.ref_early_start and a.early_start:
            diffs.append(((a.early_start - a.ref_early_start).total_seconds() / 3600.0, a.task_code, a))
    diffs.sort(key=lambda x: x[0])
    print(f"Comparable: {len(diffs)}")
    exact = sum(1 for d, _, _ in diffs if abs(d) < 0.5)
    print(f"Exact ES match (<0.5h): {exact} ({100*exact/max(len(diffs),1):.1f}%)")

    print("\n--- 10 earliest (calc earlier than P6) ---")
    for d, code, a in diffs[:10]:
        print(f"{d:+8.0f}h {a.task_code:12s} {a.name[:40]:40s} cstr={str(a.constraint_type):8s} preds={len(a.predecessors):3d} P6={fmt(a.ref_early_start)} calc={fmt(a.early_start)}")

    print("\n--- 10 latest (calc later than P6) ---")
    for d, code, a in diffs[-10:]:
        print(f"{d:+8.0f}h {a.task_code:12s} {a.name[:40]:40s} cstr={str(a.constraint_type):8s} preds={len(a.predecessors):3d} P6={fmt(a.ref_early_start)} calc={fmt(a.early_start)}")

    # Trace A1130
    print("\n--- Trace A1130 (active, CS_MEO) ---")
    a = by_code.get("A1130")
    if a:
        print("A1130:", a.name)
        print("  status:", a.status, "| actual_start:", fmt(a.actual_start), "| remain:", a.remaining_hours, "| dur:", a.duration_hours)
        print("  P6 ES:", fmt(a.ref_early_start), "P6 EF:", fmt(a.ref_early_finish))
        print("  calc ES:", fmt(a.early_start), "calc EF:", fmt(a.early_finish))
        for pid, rt, lag in a.predecessors:
            p = acts.get(pid)
            if p:
                print(f"    pred {p.task_code:12s} {p.name[:28]:28s} {rt.value} lag={lag}h P6_EF={fmt(p.ref_early_finish)} calc_EF={fmt(p.early_finish)}")

    # Trace the first non-started no-pred activity
    print("\n--- First NotStarted activity with no predecessors ---")
    for a in acts.values():
        if a.status.value == "TK_NotStart" and not a.predecessors:
            print(f"{a.task_code:12s} {a.name[:40]:40s} act_start={fmt(a.actual_start)} P6={fmt(a.ref_early_start)} calc={fmt(a.early_start)}")
            break

    # A1019 Power ON trace
    print("\n--- Trace A1019 Power ON ---")
    a = by_code.get("A1019")
    if a:
        print("P6 ES:", fmt(a.ref_early_start), "calc ES:", fmt(a.early_start))
        for pid, rt, lag in a.predecessors[:8]:
            p = acts.get(pid)
            if p:
                print(f"    pred {p.task_code:12s} {p.name[:28]:28s} {rt.value} lag={lag}h P6_EF={fmt(p.ref_early_finish)} calc_EF={fmt(p.early_finish)}")


if __name__ == "__main__":
    main("/XD/JLL/LIS1/Planning/LIS10-Draft 21.xer")
