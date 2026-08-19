"""
openCPM core model — engine-agnostic dataclasses.

The core library has NO dependencies on any XER parser. Import adapters
(xer_adapter/) convert external formats into these objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Dict, List, Optional


class RelType(str, Enum):
    FS = "PR_FS"  # Finish-to-Start
    SS = "PR_SS"  # Start-to-Start
    FF = "PR_FF"  # Finish-to-Finish
    SF = "PR_SF"  # Start-to-Finish


class TaskType(str, Enum):
    TASK = "TT_Task"
    MILESTONE = "TT_Mile"
    START_MILESTONE = "TT_StartMilestone"
    FINISH_MILESTONE = "TT_FinMile"
    WBS = "TT_WBS"


class Status(str, Enum):
    NOT_STARTED = "TK_NotStart"
    ACTIVE = "TK_Active"
    COMPLETE = "TK_Complete"


@dataclass
class WorkWindow:
    start: time
    end: time


@dataclass
class Calendar:
    """A working-time calendar. Exceptions override the weekday pattern per
    date: a date mapping to a non-empty window list is a working day,
    a date mapping to None/empty is a non-working day."""

    cal_id: str
    name: str
    day_hours: float = 8.0
    work_windows: Dict[int, List[WorkWindow]] = field(default_factory=dict)  # weekday 1=Mon..7=Sun
    exceptions: Dict = field(default_factory=dict)  # date -> Optional[List[WorkWindow]]
    base_cal_id: Optional[str] = None
    project_override: bool = False

    def windows_for(self, day: datetime) -> List[WorkWindow]:
        if day.date() in self.exceptions:
            return self.exceptions[day.date()] or []
        return self.work_windows.get(day.isoweekday(), [])

    def is_workday(self, day: datetime) -> bool:
        if day.date() in self.exceptions:
            return bool(self.exceptions[day.date()])
        windows = self.work_windows.get(day.isoweekday())
        if not windows:
            return False
        return any(w.start != w.end for w in windows)

    def work_hours_on(self, day: datetime) -> float:
        """Total working hours on a given day (holidays = 0)."""
        if day.date() in self.exceptions:
            if not self.exceptions[day.date()]:
                return 0.0
            return sum((w.end.hour - w.start.hour) + (w.end.minute - w.start.minute) / 60.0
                       for w in self.exceptions[day.date()])
        windows = self.work_windows.get(day.isoweekday(), [])
        return sum((w.end.hour - w.start.hour) + (w.end.minute - w.start.minute) / 60.0 for w in windows)


@dataclass
class Activity:
    task_id: str
    task_code: str
    name: str
    calendar_id: str
    duration_hours: float = 0.0
    remaining_hours: Optional[float] = None
    task_type: TaskType = TaskType.TASK
    status: Status = Status.NOT_STARTED

    # Predecessors: (pred_task_id, rel_type, lag_hours)
    predecessors: List[tuple] = field(default_factory=list)

    # Constraints (v1: stored, used to flag expected mismatches; not solved)
    constraint_type: Optional[str] = None
    constraint_date: Optional[datetime] = None

    # Actuals from progressed schedule
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None

    # Computed by solver
    early_start: Optional[datetime] = None
    early_finish: Optional[datetime] = None
    late_start: Optional[datetime] = None
    late_finish: Optional[datetime] = None
    total_float_hours: Optional[float] = None

    # Reference values from source schedule (P6) for validation
    ref_early_start: Optional[datetime] = None
    ref_early_finish: Optional[datetime] = None
    ref_late_start: Optional[datetime] = None
    ref_late_finish: Optional[datetime] = None
    ref_total_float: Optional[float] = None

    @property
    def is_milestone(self) -> bool:
        return self.task_type in (TaskType.MILESTONE, TaskType.START_MILESTONE, TaskType.FINISH_MILESTONE)

    @property
    def effective_duration(self) -> float:
        """Duration used by solver: remaining hours for active tasks, full for unstarted, 0 for done."""
        if self.status == Status.COMPLETE:
            return 0.0
        if self.remaining_hours is not None and self.status == Status.ACTIVE:
            return self.remaining_hours
        return self.duration_hours


@dataclass
class Schedule:
    name: str
    activities: Dict[str, Activity] = field(default_factory=dict)
    calendars: Dict[str, Calendar] = field(default_factory=dict)
    project_start: Optional[datetime] = None
    project_end: Optional[datetime] = None  # set by solver
    data_date: Optional[datetime] = None

    def successors(self, task_id: str) -> List[tuple]:
        """(succ_id, rel_type, lag)"""
        out = []
        for act in self.activities.values():
            for pid, rtype, lag in act.predecessors:
                if pid == task_id:
                    out.append((act.task_id, rtype, lag))
        return out
