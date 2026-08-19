"""
Synthetic CPM test — textbook schedule with hand-computed expected dates.

Calendar: 5-day workweek, 8h/day (08:00-12:00, 13:00-17:00), no holidays.
Project start: Monday 2026-05-11 08:00.

Network:
  A (16h) -> B (16h) -> D (16h) -> E (8h)
  A (16h) -> C (32h) -> D
  F (8h) SS+0 from A

Expected dates (Monday-Friday, 8h/day ending 17:00):
  A: 05-11 08:00 -> 05-12 17:00
  B: 05-13 08:00 -> 05-15 17:00
  C: 05-13 08:00 -> 05-18 17:00   (32h = 4 days: 13,14,15,18)
  D: 05-19 08:00 -> 05-20 17:00   (driven by C, FS+0)
  E: 05-21 08:00 -> 05-21 17:00
  F: SS+0 from A -> ES 05-11 08:00, EF 05-11 17:00 (8h)
Critical path: A -> C -> D -> E (16+32+16+8 = 72h)
Float: B = 8h (LS Thu 14 08:00 vs ES Wed 13 08:00). F = 64h (no succ, LF = project end 05-21 17:00, LS = 05-21 08:00; working hours from 05-11 08:00 = 8 full days x 8h)
"""

from datetime import datetime, date, time

from opencpm.model import Activity, Calendar, RelType, Schedule, Status, TaskType, WorkWindow
from opencpm.solver import Solver


def make_cal():
    windows = {}
    for iso in range(1, 6):  # Mon-Fri
        windows[iso] = [WorkWindow(time(8, 0), time(12, 0)), WorkWindow(time(13, 0), time(17, 0))]
    return Calendar(cal_id="c1", name="5d", day_hours=8.0, work_windows=windows, holidays=set())


def build_sched():
    sched = Schedule(name="synthetic", calendars={"c1": make_cal()})
    sched.project_start = datetime(2026, 5, 11, 8, 0)
    specs = {
        "A": (16, []),
        "B": (24, [("A", RelType.FS, 0)]),
        "C": (32, [("A", RelType.FS, 0)]),
        "D": (16, [("B", RelType.FS, 0), ("C", RelType.FS, 0)]),
        "E": (8, [("D", RelType.FS, 0)]),
        "F": (8, [("A", RelType.SS, 0)]),
    }
    for code, (dur, preds) in specs.items():
        act = Activity(task_id=code, task_code=code, name=code, calendar_id="c1", duration_hours=dur)
        act.predecessors = preds
        sched.activities[code] = act
    return sched


def main():
    sched = build_sched()
    Solver(sched).solve()
    ok = True
    exp = {
        "A": ("2026-05-11 08:00", "2026-05-12 17:00"),
        "B": ("2026-05-13 08:00", "2026-05-15 17:00"),
        "C": ("2026-05-13 08:00", "2026-05-18 17:00"),
        "D": ("2026-05-19 08:00", "2026-05-20 17:00"),
        "E": ("2026-05-21 08:00", "2026-05-21 17:00"),
        "F": ("2026-05-11 08:00", "2026-05-11 17:00"),
    }
    for code, (es_exp, ef_exp) in exp.items():
        a = sched.activities[code]
        es = a.early_start.strftime("%Y-%m-%d %H:%M") if a.early_start else "None"
        ef = a.early_finish.strftime("%Y-%m-%d %H:%M") if a.early_finish else "None"
        status = "OK" if es == es_exp and ef == ef_exp else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"{status} {code}: ES={es} EF={ef} (exp {es_exp} -> {ef_exp})")

    cp = Solver(sched).critical_path()
    print("Critical path:", cp)
    if cp != ["A", "C", "D", "E"]:
        ok = False
        print("FAIL critical path")
    else:
        print("OK critical path")

    # Float checks
    tf = {code: sched.activities[code].total_float_hours for code in sched.activities}
    print("Total float:", tf)
    if tf["B"] != 8.0:
        ok = False
        print("FAIL: B float expected 8h, got", tf["B"])
    else:
        print("OK B float 8h")

    print("\nRESULT:", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
