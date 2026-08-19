"""
openCPM solver — calendar-aware CPM engine.

Implements:
- Forward pass (ES/EF) with FS/SS/FF/SF relationships and hour lags
- Backward pass (LS/LF)
- Total float
- Critical path (TF=0 chain)

Durations are in HOURS and are converted through each activity's calendar,
matching P6 semantics. Zero-dependency pure Python.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .model import Activity, Calendar, RelType, Schedule, Status, TaskType


class CalendarTime:
    """Working-time arithmetic over a Calendar."""

    def __init__(self, cal: Calendar):
        self.cal = cal

    def next_working_instant(self, dt: datetime) -> datetime:
        """First working instant >= dt (window start, or dt itself if inside a window)."""
        day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        while True:
            if self.cal.is_workday(day):
                for w in self.cal.windows_for(day):
                    ws = day.replace(hour=w.start.hour, minute=w.start.minute)
                    we = day.replace(hour=w.end.hour, minute=w.end.minute)
                    if we <= dt:
                        continue
                    cand = max(ws, dt)
                    if cand < we:
                        return cand
            day += timedelta(days=1)

    def prev_working_instant(self, dt: datetime) -> datetime:
        """Last working instant <= dt (window end, or dt itself if inside a window)."""
        day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        while True:
            if self.cal.is_workday(day):
                for w in sorted(self.cal.windows_for(day),
                                key=lambda x: (x.end.hour, x.end.minute), reverse=True):
                    ws = day.replace(hour=w.start.hour, minute=w.start.minute)
                    we = day.replace(hour=w.end.hour, minute=w.end.minute)
                    if ws >= dt:
                        continue
                    cand = min(we, dt)
                    if cand > ws:
                        return cand
            day -= timedelta(days=1)

    def add_hours(self, dt: datetime, hours: float) -> datetime:
        """Advance dt by `hours` of calendar working time.

        Snaps forward: if dt is at/after a window end (or outside working
        time), the next working instant is the next window start. This matches
        P6, where an FS+0 successor of an activity ending at 17:00 starts the
        following workday 08:00, not 17:00.
        """
        if hours < 0:
            # Negative lag / FF-SF duration offset: walk backward instead
            return self.subtract_hours(dt, -hours)
        if hours == 0:
            return dt
        remaining = hours
        current = dt

        # Locate first working instant >= current
        anchor = self.next_working_instant(current)

        # Consume from anchor forward, full windows per day
        day = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
        while remaining > 0:
            if self.cal.is_workday(day):
                for w in self.cal.windows_for(day):
                    ws = day.replace(hour=w.start.hour, minute=w.start.minute)
                    we = day.replace(hour=w.end.hour, minute=w.end.minute)
                    day_len = (we - ws).total_seconds() / 3600.0
                    if day_len <= 0:
                        continue
                    # Only consume windows at/after anchor
                    if we <= anchor:
                        continue
                    eff_start = max(ws, anchor)
                    if eff_start >= we:
                        continue
                    available = (we - eff_start).total_seconds() / 3600.0
                    if remaining <= available:
                        return eff_start + timedelta(hours=remaining)
                    remaining -= available
            # After the anchor's day, all remaining windows are beyond it
            day += timedelta(days=1)
        return day  # unreachable

    def subtract_hours(self, dt: datetime, hours: float, snap_zero: bool = True) -> datetime:
        """Move dt backward by `hours` of calendar working time.

        Snaps backward: if dt is at/before a window start, the previous
        working instant is the previous window end (P6 FS-0 predecessor
        finishing at 08:00 really finished previous day 17:00).

        snap_zero=False: hours==0 returns dt unchanged (identity). Used for
        SS/SF backward links where the start instant is shared, not snapped
        (verified: A35251 LS = A35261 LS = 08-12 08:00 in Draft 21).
        """
        if hours < 0:
            return self.add_hours(dt, -hours)
        remaining = hours
        current = dt

        # Locate last working instant <= current
        anchor = self.prev_working_instant(current)

        if remaining <= 0:
            return dt if not snap_zero else anchor

        day = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
        while remaining > 0:
            if self.cal.is_workday(day):
                for w in sorted(self.cal.windows_for(day),
                                key=lambda x: (x.end.hour, x.end.minute), reverse=True):
                    ws = day.replace(hour=w.start.hour, minute=w.start.minute)
                    we = day.replace(hour=w.end.hour, minute=w.end.minute)
                    day_len = (we - ws).total_seconds() / 3600.0
                    if day_len <= 0:
                        continue
                    if ws >= anchor:
                        continue
                    eff_end = min(we, anchor)
                    if eff_end <= ws:
                        continue
                    available = (eff_end - ws).total_seconds() / 3600.0
                    if remaining <= available:
                        return eff_end - timedelta(hours=remaining)
                    remaining -= available
            day -= timedelta(days=1)
        return day  # unreachable

    def working_hours_between(self, start: datetime, end: datetime) -> float:
        """Total working hours from start to end."""
        if end <= start:
            return 0.0
        cal = self.cal
        total = 0.0
        day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end_day = end.replace(hour=0, minute=0, second=0, microsecond=0)
        while day <= end_day:
            if cal.is_workday(day):
                for w in cal.work_windows.get(day.isoweekday(), []):
                    ws = day.replace(hour=w.start.hour, minute=w.start.minute)
                    we = day.replace(hour=w.end.hour, minute=w.end.minute)
                    lo = max(ws, start) if day.date() == start.date() else ws
                    hi = min(we, end) if day.date() == end.date() else we
                    if hi > lo:
                        total += (hi - lo).total_seconds() / 3600.0
            day += timedelta(days=1)
        return total


class Solver:
    def __init__(self, schedule: Schedule):
        self.sched = schedule
        self.cal_time: Dict[str, CalendarTime] = {
            cid: CalendarTime(cal) for cid, cal in schedule.calendars.items()
        }

    def cal_time_for(self, act: Activity) -> CalendarTime:
        return self.cal_time[act.calendar_id]

    # ---- relationship constraint application -------------------------------

    def _constraint_early_start(self, act: Activity, pred: Activity, rtype: RelType, lag_hours: float) -> datetime:
        """Earliest start of `act` given one predecessor relationship."""
        cal = self.cal_time_for(act)
        if rtype == RelType.FS:
            assert pred.early_finish is not None
            return cal.add_hours(pred.early_finish, lag_hours)
        if rtype == RelType.SS:
            assert pred.early_start is not None
            return cal.add_hours(pred.early_start, lag_hours)
        if rtype == RelType.FF:
            assert pred.early_finish is not None
            return cal.add_hours(pred.early_finish, lag_hours - act.effective_duration)
        if rtype == RelType.SF:
            assert pred.early_start is not None
            return cal.add_hours(pred.early_start, lag_hours - act.effective_duration)
        raise ValueError(f"Unknown relationship type {rtype}")

    def _constraint_late_finish(self, act: Activity, succ: Activity, rtype: RelType, lag_hours: float) -> datetime:
        """Latest finish of `act` given one successor relationship.

        Backward-pass algebra (calendar-aware, NOT simple hour algebra):
        - FS: succ.ES >= act.EF + lag  ->  act.LF = succ.LS - lag
        - SS: succ.ES >= act.ES + lag  ->  act.LS = succ.LS - lag
              then act.LF = act.LS + dur  (two separate calendar moves)
        - FF: succ.EF >= act.EF + lag  ->  act.LF = succ.LF - lag
        - SF: succ.LF >= act.LS + lag  ->  act.LS = succ.LF - lag
              then act.LF = act.LS + dur
        """
        cal = self.cal_time_for(act)
        if rtype == RelType.FS:
            assert succ.late_start is not None
            return cal.subtract_hours(succ.late_start, lag_hours)
        if rtype == RelType.SS:
            assert succ.late_start is not None
            # SS backward: LS_pred = LS_succ - lag. With lag=0 the start
            # instant is IDENTICAL (no snap-back to previous window end) —
            # SS means the two activities share the same start instant
            # (verified: A35251 LS = A35261 LS = 08-12 08:00 in Draft 21).
            act_ls = cal.subtract_hours(succ.late_start, lag_hours, snap_zero=False)
            return cal.add_hours(act_ls, act.effective_duration)
        if rtype == RelType.FF:
            assert succ.late_finish is not None
            return cal.subtract_hours(succ.late_finish, lag_hours)
        if rtype == RelType.SF:
            assert succ.late_finish is not None
            act_ls = cal.subtract_hours(succ.late_finish, lag_hours, snap_zero=False)
            return cal.add_hours(act_ls, act.effective_duration)
        raise ValueError(f"Unknown relationship type {rtype}")

    # -------------------------------------------------------------------------

    def _topo_order(self) -> List[str]:
        """Kahn's algorithm. Cycles are broken by appending leftover nodes."""
        sched = self.sched
        preds_of: Dict[str, List[str]] = {
            tid: [p for p, _, _ in a.predecessors if p in sched.activities]
            for tid, a in sched.activities.items()
        }
        indeg = {tid: len(preds_of[tid]) for tid in sched.activities}
        queue = [tid for tid, d in indeg.items() if d == 0]
        order: List[str] = []
        while queue:
            tid = queue.pop(0)
            order.append(tid)
            for sid, _, _ in sched.successors(tid):
                indeg[sid] -= 1
                if indeg[sid] == 0:
                    queue.append(sid)
        for tid in sched.activities:
            if tid not in order:
                order.append(tid)
        return order

    def solve(self) -> Schedule:
        sched = self.sched
        start_date = sched.data_date or sched.project_start
        if start_date is None:
            raise ValueError("Schedule needs project_start or data_date")

        # -- Forward pass -----------------------------------------------------
        order = self._topo_order()
        # Data date: explicit if set, else max actual end (schedule is progressed)
        if sched.data_date is None:
            dd = max(
                (a.actual_end for a in sched.activities.values() if a.actual_end),
                default=start_date,
            )
            sched.data_date = dd

        # Forward-pass floor: P6 never schedules an activity before the later
        # of the data date and the project start date. samples/04 has data
        # date 2012-05-10 but plan_start 2012-06-04 — P6's stored ES starts
        # 06-05+; flooring only at the data date ran every chain 24-30 days
        # early. LIS/01-03 have plan_start <= data date, so the floor is the
        # data date there (unchanged behaviour).
        floor = sched.data_date or sched.project_start
        if (sched.data_date is not None and sched.project_start is not None
                and sched.project_start > sched.data_date):
            floor = sched.project_start

        for tid in order:
            act = sched.activities[tid]
            if act.status == Status.COMPLETE:
                # Completed activities anchor successors at their ACTUAL
                # dates (P6 recomputes from actuals when progressing; the
                # stored ES/EF in the XER for completed rows is a stamped
                # data-date artifact that does not reproduce the chains —
                # verified regression: refs-anchoring drops Draft 19 ES
                # 88.5% -> 64.4%).
                act.early_start = act.actual_start
                act.early_finish = act.actual_end or act.actual_start
                continue
            if act.is_milestone or act.effective_duration == 0:
                dur = 0.0
            else:
                dur = act.effective_duration
            cal = self.cal_time_for(act)

            if not act.predecessors:
                es = floor
            else:
                es = None
                for pid, rtype, lag in act.predecessors:
                    if pid not in sched.activities:
                        continue
                    p = sched.activities[pid]
                    if p.early_start is None:
                        continue
                    cand = self._constraint_early_start(act, p, rtype, lag)
                    if es is None or cand > es:
                        es = cand
                if es is None:
                    es = floor
            # Active activity: P6 ES is driven by data date + logic, not the
            # historical actual start. The data-date floor below covers it.
            # Hard constraints (v1: MEO/MSOA, the ones that move early dates)
            cstr = act.constraint_type
            if cstr == "CS_MEO" and act.constraint_date is not None:
                # Must end on: ES >= cstr_date - duration
                if dur <= 0:
                    es = max(es, act.constraint_date)
                else:
                    es = max(es, cal.subtract_hours(act.constraint_date, dur))
            elif cstr == "CS_MSOA" and act.constraint_date is not None:
                # Must start on or after
                es = max(es, act.constraint_date)
            # CS_ALAP handled after backward pass (ES := LS)
            # P6 floor: no remaining work starts before the data date /
            # project start (see floor computation above).
            if floor is not None and es < floor:
                es = floor
            # Snap ES into a valid working start. P6 snaps:
            # - positive-duration activities (always)
            # - zero-duration TASKS (TT_Task) — they behave like work
            # but NOT milestones (TT_Mile/TT_FinMile) which may sit exactly
            # on a window end (CS_MEO and FF-linked milestones).
            if dur > 0 or act.task_type == TaskType.TASK:
                es = cal.next_working_instant(es)
            act.early_start = es
            act.early_finish = cal.add_hours(es, dur)

        # Project end = max EF, unless P6's own finish was imported (that
        # anchors the backward pass identically to how P6 calculated it)
        end = sched.project_float_end or sched.project_end or max(
            (a.early_finish for a in sched.activities.values() if a.early_finish),
            default=start_date,
        )
        # An imposed finish is typed as a plain date (00:00), but float is
        # measured from the last WORKING instant at or before it — P6 reports
        # late finishes at the end of the preceding workday, never at midnight
        # (samples/02: plan_end 2013-03-01 00:00 -> anchor 2013-02-28 17:00).
        if sched.project_float_end is not None and sched.activities:
            _ref = next(iter(sched.activities.values()))
            end = self.cal_time_for(_ref).prev_working_instant(end)

        # -- Project finish constraint -----------------------------------------
        # P6 with "use project finish date for float" (SCHEDOPTIONS
        # sched_use_project_end_date_for_float=Y) treats the scheduled end
        # date as a hard finish anchor: the terminal activity of the network
        # is pinned to scd_end_date. Without this, a network whose natural
        # finish lands before the project end date shows the wrong terminal
        # date (Draft 21: network ends 10-12 08:36, P6 pins Milestone 20 at
        # scd_end 10-13 08:00).
        if sched.project_end is not None:
            # Find the terminal activity with the latest early finish (the
            # network's end node) and pin it to the project end date.
            terminals = [
                a for a in sched.activities.values()
                if a.early_finish is not None and not sched.successors(a.task_id)
            ]
            if terminals:
                end_node = max(terminals, key=lambda a: a.early_finish or datetime.min)
                assert end_node.early_finish is not None
                if end_node.early_finish < sched.project_end:
                    cal = self.cal_time_for(end_node)
                    end_node.early_start = sched.project_end
                    end_node.early_finish = cal.add_hours(sched.project_end, 0)  # zero-duration pin

        # -- Backward pass ----------------------------------------------------
        for tid in reversed(order):
            act = sched.activities[tid]
            if act.early_start is None:
                continue
            cal = self.cal_time_for(act)
            succs = sched.successors(tid)
            if not succs:
                lf = end
            else:
                lf = None
                for succ_id, rtype, lag in succs:
                    s = sched.activities[succ_id]
                    if s.early_start is None:
                        continue
                    cand = self._constraint_late_finish(act, s, rtype, lag)
                    if lf is None or cand < lf:
                        lf = cand
                if lf is None:
                    lf = end
            # Hard constraints that affect LATE dates, applied INLINE so
            # predecessors see the pinned value (Oracle constraint docs):
            # - CS_MEO (Finish On): late finish = constraint date exactly
            # - CS_MSOB (Finish On or Before): late finish <= constraint date
            # - CS_MSO (Start On): late start = constraint date -> LF = date + dur
            cstr = act.constraint_type
            if cstr == "CS_MEO" and act.constraint_date is not None:
                lf = act.constraint_date
            elif cstr == "CS_FOB" and act.constraint_date is not None:
                lf = min(lf, act.constraint_date)
            elif cstr == "CS_MSO" and act.constraint_date is not None:
                cand = cal.add_hours(act.constraint_date, act.effective_duration)
                lf = min(lf, cand)
            act.late_finish = lf
            dur = 0.0 if act.is_milestone else act.effective_duration
            if dur <= 0:
                # Zero-duration: LS == LF exactly (P6: milestone late dates
                # are identical, no snap-back to previous window). Constraint
                # timestamps (08:36) are KEPT for zero-duration rows.
                act.late_start = lf
            else:
                act.late_start = cal.subtract_hours(lf, dur)

        # -- ALAP constraints ---------------------------------------------------
        # CS_ALAP: "sets the activity's early dates as late as possible without
        # affecting successor activities" (Oracle docs). Only applies to
        # activities with POSITIVE float. ES is bounded by the successors'
        # EARLY dates (not by LS): the largest ES that keeps every successor's
        # early start/finish unchanged. Zero-duration and completed activities
        # are skipped.
        for act in sched.activities.values():
            if act.constraint_type != "CS_ALAP":
                continue
            if act.early_start is None or act.early_finish is None:
                continue
            if act.total_float_hours is not None and act.total_float_hours <= 0:
                continue  # only positive-float activities
            dur = 0.0 if act.is_milestone else act.effective_duration
            cal = self.cal_time_for(act)
            bound = None
            for sid, rtype, lag in sched.successors(act.task_id):
                s = sched.activities.get(sid)
                if s is None or s.early_start is None:
                    continue
                assert s.early_finish is not None
                if rtype == RelType.FS:
                    # succ.ES >= act.EF + lag  ->  act.ES <= succ.ES - dur - lag
                    cand = cal.subtract_hours(s.early_start, dur + lag)
                elif rtype == RelType.SS:
                    cand = cal.subtract_hours(s.early_start, lag)
                elif rtype == RelType.FF:
                    # succ.EF >= act.EF + lag -> act.ES <= succ.EF - dur - lag
                    cand = cal.subtract_hours(s.early_finish, dur + lag)
                elif rtype == RelType.SF:
                    # succ.EF >= act.ES + lag
                    cand = cal.subtract_hours(s.early_finish, lag)
                else:
                    continue
                if bound is None or cand < bound:
                    bound = cand
            if bound is not None and bound > act.early_start:
                act.early_start = bound
                act.early_finish = cal.add_hours(bound, dur)

        # -- Float (after ALAP: ALAP mutates ES, so float must be computed
        # on the FINAL early dates — the earlier position left stale TF on
        # CS_ALAP rows like A3920) --------------------------------------------
        for act in sched.activities.values():
            if act.early_start is None:
                act.total_float_hours = None
                act.free_float_hours = None
                continue
            es, ls = act.early_start, act.late_start
            assert es is not None and ls is not None
            if ls <= es:
                # Negative float is legitimate under constrained finish
                # (research doc 02 §1.5: "late dates are early"; Draft 21
                # stores -0.6 etc.). Calendar hours between LS and ES, negated.
                act.total_float_hours = -self.cal_time_for(act).working_hours_between(ls, es)
            else:
                act.total_float_hours = self.cal_time_for(act).working_hours_between(es, ls)

            # Free float: amount the activity can slip before delaying the
            # start of any successor (PyP6Xer docstring; XER stores it in
            # free_float_hr_cnt for every non-completed row). Calendar hours,
            # clamped at 0.
            cal = self.cal_time_for(act)
            succs = sched.successors(act.task_id)
            if not succs:
                # Open end with use-project-end-for-float: the project finish
                # acts as a pseudo-successor, so FF = TF (A1050: FF=TF=1640,
                # A1090: FF=TF=1272 in Draft 21).
                act.free_float_hours = max(act.total_float_hours or 0.0, 0.0)
                continue
            ff = None
            for sid, rtype, lag in succs:
                s = sched.activities.get(sid)
                if s is None or s.early_start is None:
                    continue
                if rtype == RelType.FS:
                    cand = cal.subtract_hours(s.early_start, lag, snap_zero=False)
                    base = act.early_finish
                elif rtype == RelType.SS:
                    cand = cal.subtract_hours(s.early_start, lag, snap_zero=False)
                    base = act.early_start
                elif rtype == RelType.FF:
                    assert s.early_finish is not None
                    cand = cal.subtract_hours(s.early_finish, lag, snap_zero=False)
                    base = act.early_finish
                elif rtype == RelType.SF:
                    assert s.early_finish is not None
                    cand = cal.subtract_hours(s.early_finish, lag, snap_zero=False)
                    base = act.early_start
                else:
                    continue
                if cand is None or base is None:
                    continue
                if cand > base:
                    wh = cal.working_hours_between(base, cand)
                    ff = wh if ff is None else min(ff, wh)
                else:
                    ff = 0.0 if ff is None else min(ff, 0.0)
            act.free_float_hours = 0.0 if ff is None else ff

        return sched

    def critical_path(self) -> List[str]:
        """Chain of TF=0 activities from earliest start to project end."""
        sched = self.sched
        tf0 = [
            a for a in sched.activities.values()
            if a.total_float_hours is not None and a.total_float_hours <= 0 and a.early_start is not None
        ]
        if not tf0:
            return []
        succ_of: Dict[str, List[str]] = {a.task_id: [] for a in tf0}
        for a in tf0:
            for sid, _, _ in sched.successors(a.task_id):
                s = sched.activities.get(sid)
                if s and s.total_float_hours is not None and s.total_float_hours <= 0 and s.early_start is not None:
                    succ_of[a.task_id].append(sid)
        # Longest path with unit weights over the TF=0 subgraph
        fwd: Dict[str, float] = {}
        for a in sorted(tf0, key=lambda x: x.early_start or datetime.min):
            fwd[a.task_id] = fwd.get(a.task_id, 0.0)
            for sid in succ_of[a.task_id]:
                fwd[sid] = max(fwd.get(sid, 0.0), fwd[a.task_id] + 1.0)
        ends = [tid for tid, ss in succ_of.items() if not ss]
        if not ends:
            return []
        end_node = max(ends, key=lambda t: fwd.get(t, 0.0))
        chain = [end_node]
        cur = end_node
        visited = {end_node}
        while True:
            candidates = [a.task_id for a in tf0 if cur in succ_of.get(a.task_id, [])]
            candidates = [c for c in candidates if c not in visited]
            if not candidates:
                break
            best = max(candidates, key=lambda c: fwd.get(c, 0.0))
            chain.append(best)
            visited.add(best)
            cur = best
        chain.reverse()
        return chain
