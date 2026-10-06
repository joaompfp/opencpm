"""Classify Draft 21 LS/LF mismatches into reproducibility classes.

Classes (research-backed, see docs/reference/02-p6-constraints-and-settings.md
and 03-xer-date-storage.md):
  A. mixed-run stamps: P6 stores late dates from an EARLIER schedule run
     (e.g. LF < constraint date, or LF < ES with TF=0 while the row has a
     constraint that would pin LF later). Unreproducible by any single run.
  B. +24h / +16h snap-back shifts: engine late dates one working day later
     than P6 (LS at window start where P6 backed to previous window end).
     Potentially a real engine bug (subtract_hours snap semantics).
  C. 0.6h / 16.6h / 64.6h constraint-timestamp residue: CS_MEO 08:36
     timestamps propagating through zero-duration late-date arithmetic.
     Genuine P6 output; engine keeps them where P6 snaps (or vice versa).
  D. negative float clamped: engine forces TF=0 when LS<=ES; P6 stores
     negative float (-0.6 etc.) under constrained finish. Real engine bug.
"""
import sys
from collections import Counter

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer


def wh(a, b):
    """Working hours between two datetimes (positive)."""
    if a is None or b is None:
        return None
    return abs((a - b).total_seconds()) / 3600.0


def classify(path):
    sched = load_xer(path)
    Solver(sched).solve()

    classes = Counter()
    examples = {}
    total_mismatch = 0

    for a in sched.activities.values():
        if a.ref_early_start is None or a.status.value.endswith("Complete"):
            continue
        if a.ref_late_start is None or a.late_start is None:
            continue
        ls_d = (a.late_start - a.ref_late_start).total_seconds() / 3600.0
        lf_d = (a.late_finish - a.ref_late_finish).total_seconds() / 3600.0
        if abs(ls_d) < 0.5 and abs(lf_d) < 0.5:
            continue  # matches

        total_mismatch += 1
        # Class D: P6 negative float we clamp (LS<=ES but P6 TF<0 or 0 with LS<ES)
        if a.ref_late_start < a.ref_early_start and a.late_start >= a.early_start:
            cls = "D_negative_float_clamped"
        # Class A: P6 LF < its own constraint date (stamp predates constraint)
        elif a.constraint_type and a.constraint_date and a.ref_late_finish < a.constraint_date:
            cls = "A_mixed_stamp_vs_constraint"
        # Class A: P6 LF < P6 ES (late before early, no negative float stored) -> mixed run
        elif a.ref_late_finish < a.ref_early_finish and (a.ref_total_float is None or a.ref_total_float >= 0):
            cls = "A_mixed_stamp_lf_lt_es"
        # Class C: residue is a multiple of 0.6h or ~16.6h / 64.6h (constraint timestamp)
        elif abs(round(lf_d * 10) % 6) <= 1 and abs(lf_d) < 200:
            cls = "C_timestamp_residue"
        # Class B: whole-workday shift (+8h working = +24h wall typically)
        elif abs(lf_d) >= 15 and abs(lf_d) % 8 < 1.0:
            cls = "B_snap_back_shift"
        else:
            cls = "X_other"
        classes[cls] += 1
        examples.setdefault(cls, []).append(
            f"{a.task_code} LS {a.late_start} vs {a.ref_late_start} "
            f"({ls_d:+.1f}h) LF {a.late_finish} vs {a.ref_late_finish} ({lf_d:+.1f}h) "
            f"TF {a.total_float_hours} vs {a.ref_total_float} cstr={a.constraint_type}@{a.constraint_date}"
        )

    print(f"\n{path.split('/')[-1]}: {total_mismatch} late-date mismatches")
    for cls, n in classes.most_common():
        print(f"  {cls}: {n}")
        for ex in examples[cls][:3]:
            print(f"      {ex}")
    return total_mismatch, classes


if __name__ == "__main__":
    classify(sys.argv[1] if len(sys.argv) > 1 else "/XD/JLL/LIS10/Planning/LIS10-Draft 21.xer")
