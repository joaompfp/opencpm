"""
Validation harness: run openCPM on a real XER and diff against P6's own computed
dates stored in the file (early_start, early_end, late_start, late_end, TF).

If the engine matches P6 on a real schedule, the CPM semantics are right.
"""
import sys
from collections import Counter
from datetime import datetime

from opencpm.solver import Solver
from xer_adapter import load_xer


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "None"


def compare(path):
    sched = load_xer(path)
    n_acts = len(sched.activities)
    print(f"Loaded: {sched.name} | {n_acts} activities | {len(sched.calendars)} calendars")
    print(f"Project start: {fmt(sched.project_start)} | data date: {fmt(sched.data_date)}")

    solver = Solver(sched)
    solver.solve()

    es_hours = ef_hours = ls_hours = lf_hours = tf_match = 0
    es_diff = []
    no_ref = 0
    es_off_by = Counter()
    ef_off_by = Counter()

    for act in sched.activities.values():
        if act.ref_early_start is None:
            no_ref += 1
            continue
        if act.status.value == "TK_Complete":
            # P6 stores ES=EE=data date for completed; not comparable
            no_ref += 1
            continue
        if act.early_start is None:
            continue  # complete activity, both None

        def same(a, b, tol_minutes=30):
            if a is None or b is None:
                return a is b
            return abs((a - b).total_seconds()) <= tol_minutes * 60

        if same(act.early_start, act.ref_early_start):
            es_hours += 1
        else:
            d = (act.early_start - act.ref_early_start).total_seconds() / 3600.0
            es_off_by[round(d)] += 1
            if len(es_diff) < 20:
                es_diff.append((act.task_code, act.name, fmt(act.ref_early_start), fmt(act.early_start), round(d, 1)))
        if same(act.early_finish, act.ref_early_finish):
            ef_hours += 1
        else:
            d = (act.early_finish - act.ref_early_finish).total_seconds() / 3600.0
            ef_off_by[round(d)] += 1
        if same(act.late_start, act.ref_late_start):
            ls_hours += 1
        if same(act.late_finish, act.ref_late_finish):
            lf_hours += 1
        if act.ref_total_float is not None and act.total_float_hours is not None:
            if abs(act.ref_total_float - act.total_float_hours) < 1.0:
                tf_match += 1

    total = n_acts - no_ref
    print(f"\n=== ES match: {es_hours}/{total} ({100*es_hours/max(total,1):.1f}%)")
    print(f"=== EF match: {ef_hours}/{total} ({100*ef_hours/max(total,1):.1f}%)")
    print(f"=== LS match: {ls_hours}/{total} ({100*ls_hours/max(total,1):.1f}%)")
    print(f"=== LF match: {lf_hours}/{total} ({100*lf_hours/max(total,1):.1f}%)")
    if tf_match:
        print(f"=== TF match: {tf_match}/{total} ({100*tf_match/max(total,1):.1f}%)")
    print(f"Activities without P6 refs (complete/dangling): {no_ref}")

    if es_off_by:
        print("\nES offset histogram (hours, count):")
        for off, cnt in sorted(es_off_by.items()):
            print(f"  {off:+d}h: {cnt}")
    if ef_off_by:
        print("\nEF offset histogram (hours, count):")
        for off, cnt in sorted(ef_off_by.items()):
            print(f"  {off:+d}h: {cnt}")

    if es_diff:
        print("\nFirst 20 ES mismatches:")
        for code, name, ref, calc, d in es_diff:
            print(f"  {code} {name[:45]:45s} P6={ref}  openCPM={calc}  ({d:+}h)")

    cp = solver.critical_path()
    print(f"\nCritical path (TF=0 chain): {len(cp)} activities")
    for tid in cp[:15]:
        a = sched.activities[tid]
        print(f"  {a.task_code} {a.name[:50]} {fmt(a.early_start)} -> {fmt(a.early_finish)}")


if __name__ == "__main__":
    compare(sys.argv[1] if len(sys.argv) > 1 else "/XD/JLL/LIS1/Planning/LIS10-Draft 21.xer")
