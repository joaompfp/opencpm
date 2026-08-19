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
# iso weekday: 1=Mon..7=Sun. Convert DAY_ORDER index (0=Sun..6=Sat) -> iso.
def _iso_weekday(dow_name: str) -> int:
    idx = DAY_ORDER.index(dow_name)
    return (idx + 6) % 7 + 1


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
    exceptions: dict = {}
    # P6 stores per-day overrides in clndr_data: (0||N(d|serial)(windows))
    # A day with windows is a WORKING exception; a day without windows is
    # a NON-WORKING exception (holiday). The `exceptions` attr only lists
    # dates, losing that distinction — so parse the blob.
    blob = getattr(cal_obj, "clndr_data", "") or ""
    import re as _re
    from datetime import timedelta as _td
    _EPOCH = datetime(1899, 12, 30)
    for _serial, _body in _re.findall(r"\(0\|\|\d+\(d\|(\d+)\)\((.*?)\)\)", blob):
        _dt = _EPOCH + _td(days=int(_serial))
        wins = []
        for _st, _fn in _re.findall(r"s\|(\d+:\d+)\|f\|(\d+:\d+)", _body):
            _sh, _sm = map(int, _st.split(":"))
            _fh, _fm = map(int, _fn.split(":"))
            wins.append(WorkWindow(time(_sh, _sm), time(_fh, _fm)))
        exceptions[_dt.date()] = wins or None

    windows: dict = {}
    wh = getattr(cal_obj, "working_hours", None)
    if wh is None:
        # Resource calendars (CA_Rsrc) have working_days but no
        # working_hours attribute. They don't drive activity dates —
        # skip building windows for them.
        return Calendar(
            cal_id=str(cal_obj.clndr_id),
            name=getattr(cal_obj, "clndr_name", "") or "",
            day_hours=float(getattr(cal_obj, "day_hr_cnt", None) or 8.0),
            work_windows=windows,
            exceptions=exceptions,
            base_cal_id=str(cal_obj.base_clndr_id) if getattr(cal_obj, "base_clndr_id", None) else None,
            project_override=(getattr(cal_obj, "clndr_type", "") == "CA_Project"),
        )
    for entry in (wh or []):
        dow_name = entry.get("DayOfWeek")
        iso = _iso_weekday(dow_name)
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
        exceptions=exceptions,
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
            ref_free_float=float(t.free_float_hr_cnt) if t.free_float_hr_cnt is not None else None,
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
