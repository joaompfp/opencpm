"""Identify the +264h..+336h cluster activities."""
import sys
from collections import Counter

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "None"


def main():
    sched = load_xer("/XD/JLL/LIS10/Planning/LIS10-Draft 21.xer")
    Solver(sched).solve()
    acts = sched.activities
    by_code = {a.task_code: a for a in acts.values()}

    for code, a in sorted(by_code.items()):
        if a.status.value == "TK_Complete" or a.ref_early_start is None or a.early_start is None:
            continue
        d = (a.early_start - a.ref_early_start).total_seconds() / 3600.0
        if 250 <= d <= 350:
            # find preds and their constraint types
            preds_info = []
            for pid, rt, lag in a.predecessors:
                p = by_code.get(pid) or acts.get(pid)
                if p:
                    preds_info.append(f"{p.task_code}:{p.constraint_type}")
            print(f"{d:+5.0f}h {a.task_code:10s} {a.name[:38]:38s} cstr={a.constraint_type} preds={','.join(preds_info[:5])}")


if __name__ == "__main__":
    main()
