"""
XER adapter for openCPM — converts PyP6XER Reader output into core model objects.

This is the ONLY module that depends on the xerparser library. The core
(opencpm.model, opencpm.solver) stays format-agnostic.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Optional

from opencpm.model import Activity, Calendar, RelType, Schedule, Status, TaskType, WorkWindow

REL_MAP = {
    "PR_FS": RelType.FS,
    "PR_SS": RelType.SS,
    "PR_FF": RelType.FF,
    "PR_SF": RelType.SF,
}

TASK_TYPE_MAP = {
    "TT_Task": TaskType.TASK,
    "TT_Mile": TaskType.MILESTONE,
    "TT_StartMilestone": TaskType.START_MILESTONE,
    "TT_FinMile": TaskType.FINISH_MILESTONE,
    "TT_WBS": TaskType.WBS,
}

STATUS_MAP = {
    "TK_NotStart": Status.NOT_STARTED,
    "TK_Active": Status.ACTIVE,
    "TK_Complete": Status.COMPLETE,
}

DAY_ORDER = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
# isoweekday: 1=Mon..7=Sun. PyP6XER dict keys: '1'=Sunday...'7'=Saturday
PYP6_DAY_INDEX = {"1": 7, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "7": 6}


def _to_dt(v) -> Optional[datetime]:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", ""))
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def _build_calendar(cal_obj) -> Calendar:
    holidays = set()
    for exc in (cal_obj.exceptions or []):
        if isinstance(exc, datetime):
            holidays.add(exc.date())
    windows: dict = {}
    for entry in (cal_obj.working_hours or []):
        dow_name = entry.get("DayOfWeek")
        iso = DAY_ORDER.index(dow_name) + 1  # 1=Mon..7=Sun
        wt = []
        for w in (entry.get("WorkTimes") or []):
            st = w.get("Start")
            fn = w.get("Finish")
            if st is None or fn is None:
                continue
            wt.append(WorkWindow(st, fn))
        windows[iso] = wt
    return Calendar(
        cal_id=str(cal_obj.clndr_id),
        name=cal_obj.clndr_name,
        day_hours=float(cal_obj.day_hr_cnt or 8.0),
        work_windows=windows,
        holidays=holidays,
        base_cal_id=str(cal_obj.base_clndr_id) if cal_obj.base_clndr_id else None,
        project_override=(cal_obj.clndr_type == "CA_Project"),
    )


def load_xer(path: str) -> Schedule:
    """Parse an XER file into an openCPM Schedule. Returns the first project."""
    from xerparser.reader import Reader

    reader = Reader(path)
    proj = next(iter(reader.projects))

    sched = Schedule(name=str(proj))

    for cal in reader.calendars:
        c = _build_calendar(cal)
        sched.calendars[c.cal_id] = c

    # Activities
    for t in reader.activities.activities:
        act = Activity(
            task_id=str(t.task_id),
            task_code=t.task_code,
            name=t.task_name or "",
            calendar_id=str(t.clndr_id),
            duration_hours=float(t.target_drtn_hr_cnt or 0.0),
            remaining_hours=float(t.remain_drtn_hr_cnt) if t.remain_drtn_hr_cnt is not None else None,
            task_type=TASK_TYPE_MAP.get(t.task_type, TaskType.TASK),
            status=STATUS_MAP.get(t.status_code, Status.NOT_STARTED),
            constraint_type=t.cstr_type,
            constraint_date=_to_dt(t.cstr_date),
            actual_start=_to_dt(t.act_start_date),
            actual_end=_to_dt(t.act_end_date),
            ref_early_start=_to_dt(t.early_start_date),
            ref_early_finish=_to_dt(t.early_end_date),
            ref_late_start=_to_dt(t.late_start_date),
            ref_late_finish=_to_dt(t.late_end_date),
            ref_total_float=float(t.total_float_hr_cnt) if t.total_float_hr_cnt is not None else None,
        )
        sched.activities[str(t.task_id)] = act

    # Relationships
    for rel in reader.relations:
        act = sched.activities.get(str(rel.task_id))
        if act is None:
            continue
        act.predecessors.append(
            (str(rel.pred_task_id), REL_MAP.get(rel.pred_type, RelType.FS), float(rel.lag_hr_cnt or 0.0))
        )

    sched.project_start = _to_dt(proj.plan_start_date)
    # Data date: P6 stamps last_recalc_date in the PROJECT row. In XER exports
    # completed activities carry ES=EE=data date, so this is the true anchor.
    sched.data_date = _to_dt(proj.next_data_date) or _to_dt(proj.apply_actuals_date) or _to_dt(proj.last_recalc_date)
    # P6's own computed finish (scd_end_date) — anchors the backward pass.
    sched.project_end = _to_dt(proj.scd_end_date)
    return sched
