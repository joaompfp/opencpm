# CPM Fundamentals: The Semantics a P6-Parity Engine Needs

**Status:** Reference — openCPM parity research
**Date:** 2026-08-19
**Scope:** Standard CPM mechanics as implemented by Primavera P6, focused on the exact semantics that a parity engine must reproduce. Primary sources: Oracle P6 help (Activity dates, Working with Activity Constraints), Oracle XER data maps, Emerald Associates definitions, PMI/PMBOK definitions, and verified behavior of real P6 15.2 EPPM exports (LIS10 Draft 19/21).

---

## 1. Forward and backward passes

The CPM calculation runs two passes over the network:

1. **Forward pass** computes Early Start (ES) and Early Finish (EF) per activity:
   - ES = latest of: data-date floor, predecessor-derived constraints (EF/ES + lag per relationship type), and early-side activity constraints (Start On, Finish On, Start On or After, ALAP forward bound).
   - EF = ES + duration, counted in the activity's calendar working hours.
   - Oracle: "The early start date for an activity in P6 is the earliest possible date the remaining work for the activity can begin... calculated based on network logic, schedule constraints, and resource availability." [Emerald Associates, Early Dates, Late Dates and Total Float in Primavera P6](https://www.emerald-associates.com/item/early-dates-late-dates-and-total-float-in-primavera-p6.html)

2. **Backward pass** computes Late Start (LS) and Late Finish (LF):
   - LF = earliest of: successor-derived constraints (LS/ES − lag per relationship type), the project finish anchor, and late-side activity constraints (Finish On, Finish On or Before, Start On or Before, Mandatory Finish).
   - LS = LF − duration in calendar hours.
   - Oracle: "The late finish date is the latest possible date the activity must finish given the current activity information to avoid delaying the project finish date." [Emerald Associates](https://www.emerald-associates.com/item/early-dates-late-dates-and-total-float-in-primavera-p6.html)

3. **Relationship types** (P6 uses four, with hour lags):
   - FS (Finish-to-Start): successor starts after predecessor finishes. The dominant, default type.
   - SS (Start-to-Start): successor starts after predecessor starts.
   - FF (Finish-to-Finish): successor finishes after predecessor finishes.
   - SF (Start-to-Finish): successor finishes after predecessor starts. Least used.
   - [tensix.com, Relationship Types in Primavera P6 Explained](https://tensix.com/relationship-types-in-primavera-p6-explained)

---

## 2. Total float and free float: calendar hours, not wall clock

- **Total float (TF)**: the time an activity can slip before delaying the project finish. P6 computes it as `LS − ES` (or `LF − EF`), in **calendar working hours** of the activity's calendar — not wall-clock elapsed hours. Weekends and holidays simply do not count. [PyP6Xer task.py](https://github.com/HassanEmam/PyP6Xer/blob/master/xerparser/model/classes/task.py); [Emerald Associates](https://www.emerald-associates.com/item/early-dates-late-dates-and-total-float-in-primavera-p6.html)
- **Free float (FF)**: "the amount of time the activity can be delayed before delaying the start date of any successor activity." [PyP6Xer task.py](https://github.com/HassanEmam/PyP6Xer/blob/master/xerparser/model/classes/task.py). Stored per-activity in XER exports as `free_float_hr_cnt` (col 17) — populated for all not-started/active rows, empty for completed. Verified on 11 real P6 exports. [See 03-xer-date-storage.md §5](03-xer-date-storage.md)
- **Float values are fractional**: real exports store `-0.6`, `0.6`, `7.4`, `1936.6`. P6 computes float with sub-hour calendar arithmetic; a 0.6 h residue appears wherever a constraint timestamp (e.g. 08:36) meets an 08:00 anchor. Parity comparisons need ~1 h tolerance and both `LS−ES` and `LF−EF` forms when `sched_float_type=FT_FF` (finish float) is in effect. [03-xer-date-storage.md §1.2, §6](03-xer-date-storage.md)
- **Negative float is legitimate**: when the project finish is constrained, activities behind schedule get late dates earlier than early dates. "The late dates, being constrained by the last activity, are indicative of how to get back 'on' schedule." [Primavera Scheduling, When P6 Late Dates are Early](https://primaverascheduling.com/when-p6-late-dates-are-early). Draft 21 has 34 such rows on its constrained finish chain; Draft 12/14/Scenario A (unconstrained) have zero.

---

## 3. Open-end policy: no-successor activities

- Standard CPM practice: an activity with **no successors** anchors the backward pass — its LF equals the project finish (the maximum EF of the network), giving it zero total float.
- P6 with `sched_use_project_end_date_for_float=Y` (as in both LIS10 files): open-ended activities get LF = the scheduled project finish (scd_end). This is the "use project finish date for open ends" option.
- P6 with the flag unset (default): open ends close at the activity's own EF, float = 0.
- Oracle data map documents the flag as `sched_use_project_end_date_for_float` on SCHEDOPTIONS. [Oracle, SCHEDOPTIONS XER map](https://docs.oracle.com/cd/F88966_01/English/Mapping_and_Schema/xer_import_export_data_map_project/97903.htm)
- Caveat from evidence: in Draft 21, the terminal milestone stores `LF=2026-10-11 16:00 < ES=2027-10-13 08:00` with `TF=0` — a mixed-stamp artifact of multiple schedule runs, unreproducible by any single engine run. This is a file-level data-quality ceiling, not engine error. [03-xer-date-storage.md §6](03-xer-date-storage.md)

---

## 4. Data date / status date and how activities enter the calculation

- The **data date** (status date) is the point separating completed from future work. P6 EPPM stamps it end-of-day (`23:59`), P6 Professional often `HH:00`. In XER exports it lives in `PROJECT.last_recalc_date` (the "Last Recalc Date"); `last_schedule_date` is the last Schedule-click timestamp; the ERMHDR line carries the export date. There is **no single data-date column** and `next_data_date` is empty in real exports. [03-xer-date-storage.md §3](03-xer-date-storage.md); [Oracle, P6 EPPM XER data map — PROJECT](https://docs.oracle.com/cd/F51303_01/English/Mapping_and_Schema/xer_import_export_data_map_project/97885.htm)
- **Completed activities**: enter with actual dates; their stored ES/EF in the XER are a data-date stamp, NOT their actuals (42/65 completed rows in both LIS10 drafts carry exactly `last_recalc_date`). Use `act_start_date`/`act_end_date`. Both parser libraries encode this precedence (`TASK.start` prefers `act_start_date`). [03-xer-date-storage.md §2](03-xer-date-storage.md); [jjCode01/xerparser task.py](https://github.com/jjCode01/xerparser/blob/master/xerparser/schemas/task.py); [datamonkeysite, P6 Date Formats](https://datamonkeysite.com/2019/07/22/p6-date-formats-quick-data-hacks)
- **In-progress (active) activities**: ES of remaining work = data date (snapped to a working start); EF = data date + remaining duration. `restart_date`/`reend_date` hold the remaining start/finish. Oracle: "Remaining Start = Data Date once started; blank when complete." [Oracle, Activity dates](https://docs.oracle.com/cd/F25600_01/client_help/ru_RU/activity_dates.htm)
- **Not-started activities**: normal forward/backward pass with the data-date floor.
- **Remaining vs original duration**: `remain_drtn_hr_cnt` = remaining calendar hours (equals target for not-started; shrinks for active; 0 when complete). `target_drtn_hr_cnt` = original duration, kept even after completion. There is no `actual_duration` column; actual duration derives from act_start/act_end (or last_recalc_date when in progress). [Deltek, P6 XER Calculated Fields](https://help.deltek.com/product/acumentouchstone/8.2/ga/Primavera%20P6%20XER%20Calculated%20Fields.html)

---

## 5. Zero-duration activities and milestone instants

- **Milestones** (TT_Mile / TT_FinMile) and zero-duration tasks export `ES == EF` and `LS == LF` exactly, in 100% of real P6 exports examined (60/60 in D21, 72/72 in Draft 12, 70/70 in Draft 14). The backward pass for zero duration is **identity** — no snap-back to the previous window, or every late date shifts by a day. [03-xer-date-storage.md §4](03-xer-date-storage.md)
- **The agent-authored `sample-schedule.xer` violates this** (its milestones sit 8 h apart, LS≠LF, and `last_schedule_date=''`). It was never scheduled by P6; do not use it as a parity reference. [03-xer-date-storage.md §4](03-xer-date-storage.md)
- **Start-instant resolution for zero-lag links**: in real P6 exports with `sched_calendar_on_relationship_lag=rcal_Predecessor` (both LIS10 files), a zero-duration finish milestone linked FS/FF with 0 lag to a predecessor ending at 16:00 keeps exactly 16:00 (A35301, A35351, A7710). Positive-duration successors snap to the next working window start (A22601: pred EF 08-14 16:00 → ES 08-17 08:00). The distinction observed in the data is duration-driven: zero duration keeps the instant (constraint timestamps even leak through: `A3730 ES=2027-04-05 08:36`), positive duration starts at a window start. [03-xer-date-storage.md §4](03-xer-date-storage.md)
- **Lag calendar options**: P6 schedules lag in one of four calendars — "the predecessor activity calendar, the successor activity calendar, the 24-hour calendar and the project default calendar" [Emerald Associates, P6 Terms](https://www.emerald-associates.com/primavera-p6-terms-and-definitions.html). The XER SCHEDOPTIONS flag `sched_calendar_on_relationship_lag` selects which; the field exists in the Oracle data map but Oracle publishes no prose on its exact effect beyond the calendar selection — the empirical rule above (from real exports) is the operative one.

---

## 6. Negative lag / lead time

- Lag is an offset between linked activities, positive or negative; it can apply to any relationship type. [Emerald Associates, P6 Terms](https://www.emerald-associates.com/primavera-p6-terms-and-definitions.html)
- Negative lag (lead/overlap) lets a successor start before its predecessor finishes (e.g. FS with −40 h starts the successor 5 working days before the predecessor ends, on the lag calendar).
- P6 exposes `sched_lag_early_start_flag` in SCHEDOPTIONS (Oracle data map) controlling early-start behavior of lagged links; the flag's exact runtime effect is not documented in prose by Oracle — treat as a research note.

---

## 7. Constraint semantics (summary; full detail in 02-p6-constraints-and-settings.md)

From Oracle's official "Working with Activity Constraints" page [docs.oracle.com](https://docs.oracle.com/cd/G48897_01/p6help/nl/6673.htm):

| Constraint | Early dates | Late dates | Direction |
|---|---|---|---|
| Start On (CS_MSO) | delays ES to date | moves LS forward to date | both |
| Start On or Before (CS_MSOB) | — | only if LS later than date | backward only |
| Start On or After (CS_MSOA) | only if ES earlier than date | — | forward only |
| Finish On (CS_MEO) | delays EF to date | moves LF forward to date | both |
| Finish On or Before (CS_MEOB) | — | only | backward only |
| Finish On or After (CS_MEOA) | only | — | forward only |
| As Late As Possible (CS_ALAP) | sets early dates as late as possible | — | forward only, positive float only |
| Mandatory Start / Finish | hard pins | hard pins | both, ignores logic |

ALAP explicitly: "Imposes a restriction on an activity with positive float to allow it to start as late as possible without delaying its successors. When calculating a schedule, P6 sets the activity's early dates as late as possible without affecting successor activities." [Oracle](https://docs.oracle.com/cd/G48897_01/p6help/nl/6673.htm) — forward-side, positive-float-only, soft. Corroborated by [tensix.com ALAP explainer](https://tensix.com/as-late-as-possible-scheduling-constraint-in-primavera-p6-eppm-explained) and [Plan Academy ALAP video](https://www.planacademy.com/as-late-as-possible-constraint-p6-video).

---

## 8. Sources

- Oracle, "Working with Activity Constraints" — https://docs.oracle.com/cd/G48897_01/p6help/nl/6673.htm
- Oracle, "Activity dates" (P6 help) — https://docs.oracle.com/cd/F25600_01/client_help/ru_RU/activity_dates.htm
- Oracle, "SCHEDOPTIONS (Schedule Options)" XER data map — https://docs.oracle.com/cd/F88966_01/English/Mapping_and_Schema/xer_import_export_data_map_project/97903.htm
- Oracle, "P6 EPPM XER Import/Export Data Map — PROJECT" — https://docs.oracle.com/cd/F51303_01/English/Mapping_and_Schema/xer_import_export_data_map_project/97885.htm
- Emerald Associates, "Early Dates, Late Dates and Total Float in Primavera P6" — https://www.emerald-associates.com/item/early-dates-late-dates-and-total-float-in-primavera-p6.html
- Emerald Associates, "Primavera P6 Terms and Definitions" — https://www.emerald-associates.com/primavera-p6-terms-and-definitions.html
- tensix.com, "Relationship Types in Primavera P6 Explained" — https://tensix.com/relationship-types-in-primavera-p6-explained
- tensix.com, "As Late As Possible Scheduling Constraint in P6 EPPM" — https://tensix.com/as-late-as-possible-scheduling-constraint-in-primavera-p6-eppm-explained
- Plan Academy, "As Late As Possible Constraint" — https://www.planacademy.com/as-late-as-possible-constraint-p6-video
- Primavera Scheduling, "When P6 Late Dates are Early" — https://primaverascheduling.com/when-p6-late-dates-are-early
- Deltek Acumen, "Primavera P6 (XER) Calculated Fields" — https://help.deltek.com/product/acumentouchstone/8.2/ga/Primavera%20P6%20XER%20Calculated%20Fields.html
- Companion evidence doc: 03-xer-date-storage.md (raw XER field analysis of 11 real exports)
