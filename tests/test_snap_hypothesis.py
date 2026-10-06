"""Test the late-date snap hypothesis on Draft 21.

Hypothesis (from trace): P6 keeps constraint timestamps (08:36) in EARLY
dates and in zero-duration LATE dates, but snaps positive-duration LATE
dates to window edges (LS -> next window start 08:00, LF -> prev window
end 16:00). Our engine propagates timestamps everywhere.

Check: among rows where our LS carries :36 minutes, what does P6 store?
Split by duration (0 vs >0).
"""
import sys
from collections import Counter

sys.path.insert(0, "/home/joao/projects/opencpm")
sys.path.insert(0, "/home/joao/projects/opencpm/xer_adapter")

from opencpm.solver import Solver
from xer_adapter import load_xer


def main(path):
    sched = load_xer(path)
    Solver(sched).solve()

    # rows where our computed LS has a :36 minute (timestamp residue)
    rows = []
    for a in sched.activities.values():
        if a.ref_early_start is None or a.ref_late_start is None:
            continue
        if a.late_start is None or a.late_finish is None:
            continue
        our_min = a.late_start.minute
        if our_min != 36 and our_min != 24:
            continue
        p6_ls_min = a.ref_late_start.minute
        p6_lf_min = a.ref_late_finish.minute
        rows.append((a.task_code, a.task_type, a.duration_hours, our_min, p6_ls_min, p6_lf_min,
                     a.late_start, a.ref_late_start, a.late_finish, a.ref_late_finish))

    print(f"Rows with :36/:24 residue in OUR LS: {len(rows)}")
    zero_dur = [r for r in rows if r[2] == 0]
    pos_dur = [r for r in rows if r[2] > 0]
    print(f"  zero-duration: {len(zero_dur)}  positive-duration: {len(pos_dur)}")

    # P6 minute distribution by duration class
    for label, grp in [("zero-duration", zero_dur), ("positive-duration", pos_dur)]:
        c_ls = Counter(r[4] for r in grp)
        c_lf = Counter(r[5] for r in grp)
        print(f"\n{label} ({len(grp)}): P6 LS minute dist {dict(sorted(c_ls.items()))}")
        print(f"{'':16} P6 LF minute dist {dict(sorted(c_lf.items()))}")

    # examples per class
    for label, grp in [("zero-duration", zero_dur), ("positive-duration", pos_dur)]:
        print(f"\n{label} examples (first 8):")
        for r in grp[:8]:
            print(f"  {r[0]:8s} {str(r[1])[:8]:8s} dur={r[2]:6.1f} "
                  f"LS {r[6]} -> P6 {r[7]} | LF {r[8]} -> P6 {r[9]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/XD/JLL/LIS10/Planning/LIS10-Draft 21.xer")
