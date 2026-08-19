"""Backward-pass verification for SS/FF relationships.

Calendar: Mon-Fri 08:00-16:00 (8h/day).
Project start Mon 2026-05-11 08:00.
Network:
  A (16h) FS -> B (16h)
  A (16h) SS -> C (32h)   C starts when A starts
  B (16h) FF -> D (8h)    D finishes when B finishes
Expected (hand-computed):
  A: ES 05-11 08:00 EF 05-12 16:00
  B: ES 05-13 08:00 EF 05-14 16:00
  C: ES 05-11 08:00 EF 05-15 16:00   (32h = 4 days: 11,12,13,14)
  D: ES 05-15 08:00 EF 05-15 16:00   (FF: finish with B; D 8h -> ES=EF-8h)
Project end = max(EF) = C EF = 05-15 16:00
Backward:
  LF(C)=05-15 16:00 LS(C)=05-11 08:00 (32h back)
  LF(B)=05-14 16:00 LS(B)=05-13 08:00 (16h back)
  LF(A): min(succ constraints)
    from B FS: B.LS - 0 = 05-13 08:00
    from C SS: C.LS - 0 = 05-11 08:00
    => LF(A)=05-11 08:00, LS(A)=05-11 08:00-16h -> 05-08 16:00 (Friday)
  Hmm... A LS before project start is weird for a backward pass from C: C.LS is
  constrained by C's successors (none) => C.LS = C.ES = 05-11 08:00. So the SS
  link forces A.LS = 05-11 08:00, making A critical via SS even though B and D
  finish later. Float: A 0, B = 0? B.LS=05-13 (from D FF: LF(D)=... hmm D has
  no succ so LF(D)=project end 05-15 16:00, LS(D)=05-15 08:00; FF: LF(B) =
  LF(D)-0 = 05-15 16:00 -> LS(B)=05-13 08:00. B.TF = 0. C.TF = 0. D.TF=0.
  Everything critical. Not great for float separation but fine for date math.
"""
from datetime import datetime, time

from opencpm.model import Activity, Calendar, RelType, Schedule, WorkWindow
from opencpm.solver import Solver


def cal():
    return Calendar(cal_id="c", name="8h", day_hours=8.0,
                    work_windows={i: [WorkWindow(time(8, 0), time(16, 0))] for i in range(1, 6)},
                    exceptions={})


def build():
    s = Schedule(name="ssff", calendars={"c": cal()}, project_start=datetime(2026, 5, 11, 8, 0))
    A = Activity(task_id="A", task_code="A", name="A", calendar_id="c", duration_hours=16)
    B = Activity(task_id="B", task_code="B", name="B", calendar_id="c", duration_hours=16,
                 predecessors=[("A", RelType.FS, 0)])
    C = Activity(task_id="C", task_code="C", name="C", calendar_id="c", duration_hours=32,
                 predecessors=[("A", RelType.SS, 0)])
    D = Activity(task_id="D", task_code="D", name="D", calendar_id="c", duration_hours=8,
                 predecessors=[("B", RelType.FF, 0)])
    for a in (A, B, C, D):
        s.activities[a.task_id] = a
    return s


def main():
    s = build()
    Solver(s).solve()
    exp = {
        "A": ("2026-05-11 08:00", "2026-05-12 16:00"),
        "B": ("2026-05-13 08:00", "2026-05-14 16:00"),
        "C": ("2026-05-11 08:00", "2026-05-14 16:00"),
        "D": ("2026-05-14 08:00", "2026-05-14 16:00"),
    }
    exp_ls = {
        "A": "2026-05-11 08:00",
        "B": "2026-05-13 08:00",
        "C": "2026-05-11 08:00",
        "D": "2026-05-14 08:00",
    }
    ok = True
    for code, (es, ef) in exp.items():
        a = s.activities[code]
        ges = a.early_start.strftime("%Y-%m-%d %H:%M")
        gef = a.early_finish.strftime("%Y-%m-%d %H:%M")
        stat = "OK" if (ges, gef) == (es, ef) else "FAIL"
        if stat == "FAIL":
            ok = False
        print(f"{stat} {code}: ES={ges} EF={gef} (exp {es} -> {ef})")
    print()
    for code, ls in exp_ls.items():
        a = s.activities[code]
        gls = a.late_start.strftime("%Y-%m-%d %H:%M") if a.late_start else "None"
        stat = "OK" if gls == ls else "FAIL"
        if stat == "FAIL":
            ok = False
        print(f"{stat} {code}: LS={gls} (exp {ls})")
    print("\nRESULT:", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
