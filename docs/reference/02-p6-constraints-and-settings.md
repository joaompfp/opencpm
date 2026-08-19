# P6 Constraints and SCHEDOPTIONS: Calculation Semantics

**Status:** Reference — openCPM parity research
**Date:** 2026-08-19
**Primary sources:** Oracle P6 help "Working with Activity Constraints" (https://docs.oracle.com/cd/G48897_01/p6help/nl/6673.htm, last published 2026-04-23), Oracle SCHEDOPTIONS XER data map (https://docs.oracle.com/cd/F88966_01/English/Mapping_and_Schema/xer_import_export_data_map_project/97903.htm), verified against real P6 15.2 EPPM exports (LIS10 Draft 19/21) per 03-xer-date-storage.md.

---

## 1. Constraint types and their exact calculation effect

Oracle's official definitions (verbatim-semantics, not paraphrased) — [Working with Activity Constraints](https://docs.oracle.com/cd/G48897_01/p6help/nl/6673.htm):

| Constraint | XER code | Oracle's own description | Effect |
|---|---|---|---|
| **Start On** | CS_MSO | "Imposes the specific start date you select. The Start On constraint can delay an activity's early start or move forward an activity's late start to satisfy the constraint date." | Affects BOTH early and late dates (soft, logic-preserving: delay ES forward, move LS forward) |
| **Start On or Before** | CS_MSOB | "Defines the latest date an activity can start. This constraint only affects late dates and can decrease total float. When calculating a schedule, P6 imposes the start on or before constraint in the backward pass only if the calculated late start date will be later than the imposed date." | LATE dates only, backward pass only, conditional (only if LS > date) |
| **Start On or After** | CS_MSOA | "Defines the earliest date an activity can begin. This constraint affects only early dates. When calculating a schedule, P6 imposes the start on or after constraint in the forward pass only if the calculated early start date will be earlier than the imposed date." | EARLY dates only, forward pass only, conditional (only if ES < date) |
| **Finish On** | CS_MEO | "Imposes the specific finish date you select. The Finish On constraint can delay an activity's early finish or move forward an activity's late finish to satisfy the constraint date." | Affects BOTH early and late dates (soft) |
| **Finish On or Before** | CS_MEOB | "Defines the latest time an activity can finish. The finish on or before constraint affects only late dates." | LATE dates only |
| **Finish On or After** | CS_MEOA | "Defines the earliest date an activity can finish. The finish on or after constraint reduces float to coordinate parallel activities, ensuring that the finish of an activity is not scheduled before the specified date." | EARLY dates only |
| **As Late As Possible** | CS_ALAP | "Imposes a restriction on an activity with positive float to allow it to start as late as possible without delaying its successors. When calculating a schedule, P6 sets the activity's early dates as late as possible without affecting successor activities. This option disables the calendar icon." | EARLY dates only; positive-float activities only; forward-side bound by successors' EARLY dates; soft |
| **Mandatory Start** | CS_MS | "Imposes the early and late start dates you select. P6 uses the mandatory early start date regardless of its effect on network logic. A mandatory early start date could affect the late dates for all activities that lead to the constrained activity and all early dates for the activities that lead from the constrained activity." | BOTH dates, hard, ignores logic, propagates both directions |
| **Mandatory Finish** | CS_ME | "Imposes the early and late finish dates you select. P6 uses the mandatory finish date regardless of its effect on network logic. This constraint affects the late dates for all activities that lead to the constrained activity and all early dates for the activities that lead from the constrained activity." | BOTH dates, hard, ignores logic, propagates both directions |

### Key nuances the engine must honor

1. **CS_ALAP is NOT ES=LS.** It is a forward-pass post-processing step: after the normal forward pass, for each positive-float activity with CS_ALAP, push ES as late as possible while keeping every successor's EARLY dates unchanged. Verified in real data: Draft 21 A3660 has TF=72h, ES=10-05, LS=10-19 — ES≠LS. The ProjectControls.online comparison table ("ES = LS, EF = LF") describes the textbook intent, but Oracle's own wording ("sets the activity's early dates as late as possible without affecting successor activities") and the real XER data both confirm it is forward-side only. [Oracle](https://docs.oracle.com/cd/G48897_01/p6help/nl/6673.htm); [ProjectControls.online](https://projectcontrols.blog/2024/04/23/best-practices-constraints); [tensix.com](https://tensix.com/as-late-as-possible-scheduling-constraint-in-primavera-p6-eppm-explained); [Plan Academy](https://www.planacademy.com/as-late-as-possible-constraint-p6-video)

2. **Soft constraints (MSO, MEO, MSOA, MEOA) apply "only if" the network would violate them** — they are floors/ceilings, not pins. MSOA floors ES in the forward pass; MSOB caps LS in the backward pass. The conditional wording is explicit in Oracle's page.

3. **Hard constraints (Mandatory Start/Finish) ignore network logic entirely** and pin both early and late dates. Their effect propagates: predecessors of a Mandatory-Finish activity inherit the pinned late dates (backward), successors inherit pinned early dates (forward). This matches the "affects the late dates for all activities that lead to the constrained activity and all early dates for the activities that lead from" language.

4. **CS_MEO pins both EF and LF in the engine's inline handling** (delays early finish AND moves forward late finish per Oracle's "delay an activity's early finish or move forward an activity's late finish"). Draft 21 Milestone 18 (Cx L5 IST) has CS_MEO at 2027-07-14 08:36 and the whole downstream chain A7980→MS18→MS20 reproduces exactly when the MEO constraint is applied inline in both passes.

5. **Negative float under constrained finish**: Finish On / Mandatory Finish on the project tail makes late dates earlier than early dates for behind-schedule chains — "late dates are early" is legitimate, not corruption [primaverascheduling.com](https://primaverascheduling.com/when-p6-late-dates-are-early). Draft 21 has 34 such rows, all on the constrained finish chain.

---

## 2. SCHEDOPTIONS flags in the XER and their meaning

The SCHEDOPTIONS table maps to P6 EPPM Schedule Options. Oracle's data map lists the fields but (importantly) **does not define their runtime semantics in prose** — the semantics below come from the field names, P6 UI knowledge, and empirical XER evidence.

| Field | Values seen | Meaning (per Oracle field name + P6 UI + evidence) |
|---|---|---|
| `sched_calendar_on_relationship_lag` | `rcal_Successor` / `rcal_Predecessor` | Which calendar P6 uses to schedule relationship lag. Emerald Associates: lag "can be added to any relationship type and can be positive or negative. There are four calendar types available for scheduling lag, the predecessor activity calendar, the successor activity calendar, the 24-hour calendar and the project default calendar" [P6 Terms](https://www.emerald-associates.com/primavera-p6-terms-and-definitions.html). Empirical rule verified on real exports (see §2.1): with `rcal_Predecessor`, zero-duration successors keep the predecessor's window-end instant; with the default (`rcal_Successor`, or absent when no SCHEDOPTIONS row), successors snap to the next working instant. |
| `sched_use_project_end_date_for_float` | `Y` / `N` | "Use project finish date for open ends": when Y, activities with no successors anchor LF at the project finish (scd_end) instead of their own EF. Both LIS10 files set Y. When absent (no SCHEDOPTIONS row), P6 default applies. |
| `sched_float_type` | `FT_TF` / `FT_FF` | Float basis: total float (`FT_TF`, computed LS−ES) vs finish float (`FT_FF`, computed LF−EF). Both LIS10 files set `FT_FF`. When comparing engine TF against stored `total_float_hr_cnt`, use the matching basis; with FT_FF, LS−ES and LF−EF agree only approximately (a full-day identity subtlety for zero-duration rows). [03-xer-date-storage.md §6](03-xer-date-storage.md) |
| `sched_retained_logic` | (enum) | Retained logic vs progress override vs actual dates — how P6 treats completed work in the forward pass. "Retained Logic": successors wait for the predecessor's ORIGINAL duration to elapse (retained logic); "Progress Override": remaining logic drives successors (overrides original); "Actual Dates": actuals drive. Not yet fully verified against these exports (both LIS10 files export actuals-dominated behavior). |
| `sched_lag_early_start_flag` | Y/N | Controls whether lag affects early start of the successor. Oracle publishes no prose; treat as research note. |
| `sched_open_critical_flag` | Y/N | Whether open-ended activities are flagged critical. |
| `sched_outer_depend_type` | (enum) | Cross-project (outer) dependency type. |
| `sched_progress_override` | Y/N | Progress-override mode toggle. |
| `sched_setplantoforecast` | Y/N | Set plan dates to forecast when scheduling. |

### 2.1 The rcal_Predecessor question — what the evidence says

**Question:** does `sched_calendar_on_relationship_lag=rcal_Predecessor` mean a zero-lag FS successor starts exactly at the predecessor's window-end instant, or does it only control how LAG HOURS are converted?

**Evidence from real P6 15.2 EPPM exports (both LIS10 files set `rcal_Predecessor`):**
- A35301 (TT_FinMile, dur 0): FS 0-lag from A35291 whose EF is 2026-10-02 16:00. Stored ES = 2026-10-02 16:00 — the successor keeps the exact window-end instant. [03-xer-date-storage.md §4](03-xer-date-storage.md)
- A35351 (TT_FinMile, dur 0): pred A35451 EF=2026-08-09 23:59 (data-date stamp) → stored ES=2026-08-12 16:00; FF 0-lag from A35241 EF=2026-08-12 08:00 → ES=2026-08-12 16:00. The 23:59 stamp did NOT snap to 08-12 08:00 — the successor resolved against the 08-12 08:00 predecessor and kept 16:00.
- A22601 (TT_Task, dur 40h): FS 0-lag from completed A2260 with stored EF=2026-08-14 16:00 → stored ES=2026-08-17 08:00. A POSITIVE-duration successor snapped to the next working start.
- Milestones with constraint timestamps keep them: A3730 ES=2027-04-05 08:36 (a CS_MEO-derived instant, not a window start).

**Conclusion supported by the data:** with `rcal_Predecessor`, the zero-lag successor's ES resolution depends on the successor's own duration: zero-duration activities (milestones AND zero-duration tasks) keep the exact predecessor window-end instant; positive-duration activities snap to the next working window start. The flag's name (calendar on relationship lag) and Emerald's description point to lag-calendar selection; the empirical pattern in the exports is duration-driven snapping. Oracle publishes no prose resolving this further — the data is the operative source.

**Default behavior (no SCHEDOPTIONS row — the agent-authored sample fixture):** successors snap to the next working instant regardless of duration (MS-020 at 08-26 08:00 after CX-030's EF 08-25 16:00). The sample was never scheduled by P6 (`last_schedule_date=''`), so treat this as unverified default behavior, NOT parity evidence. [03-xer-date-storage.md §4](03-xer-date-storage.md)

---

## 3. Float for completed and in-progress activities

- **Completed**: `total_float_hr_cnt` and `free_float_hr_cnt` are EMPTY (`''`) in real exports for all 65 completed rows in both LIS10 files. PyP6XER exposes `total_float_hr_cnt = None` for completed tasks. The engine must treat None as "no float", not 0. [03-xer-date-storage.md §2, §7](03-xer-date-storage.md)
- **Completed**: stored `late_start_date`/`late_end_date` are REAL backward-pass values (e.g. A2200 LS=2026-09-15 08:00) — P6 does export late dates for completed rows, but the engine's own backward pass must not recompute them from the (stale) ES/EF stamps: pin completed LS/LF = ES/EF as computed from actuals (parity-verified; see 03-xer-date-storage.md §2 engine consequence).
- **In-progress**: float computed on remaining work. Remaining early start = data date; remaining late dates from backward pass.

---

## 4. Known quirks and data-quality ceilings

1. **`total_float_hr_cnt` frequently does not reconcile with `LS−ES` in wall-clock hours** — it is calendar hours, fractional (`-0.6`, `0.6`, `1936.6`). Wall-clock checks falsely flagged ~70% of D21 rows; even calendar-hour checks flag rows whose LS/ES come from different schedule runs (mixed stamps). [03-xer-date-storage.md §6](03-xer-date-storage.md)
2. **Data-date stamping**: completed activities export ES/EF = `last_recalc_date` stamp (42/65 rows in both files), not actuals. Mixed intermediate stamps (17 rows at `2026-08-12 16:00`) prove the file accumulates values across runs. [03-xer-date-storage.md §2](03-xer-date-storage.md)
3. **Export never recalculates** — the XER is a database snapshot. `last_schedule_date` is the freshness check for late dates; `last_recalc_date` for data date; ERMHDR for export date — three different clocks. [03-xer-date-storage.md §6](03-xer-date-storage.md)
4. **Constraint timestamps leak into zero-duration late dates** (08:36, 15:24 residues in D21) — P6 does not always snap them back to window edges. The engine matching 96.7% LS on Draft 19 is the realistic ceiling; D21's residue rows are genuine P6 output. [03-xer-date-storage.md §4](03-xer-date-storage.md)
5. **The terminal milestone can store LF < its own ES with TF=0** (D21 Milestone 20: LF=2026-10-11 16:00, ES=2027-10-13 08:00) — a mixed-stamp artifact reproducible by NO single engine run. This is the file's data-quality ceiling, not engine error. [03-xer-date-storage.md §6](03-xer-date-storage.md)

---

## 5. Sources

- Oracle, "Working with Activity Constraints" — https://docs.oracle.com/cd/G48897_01/p6help/nl/6673.htm (primary: constraint definitions)
- Oracle, "SCHEDOPTIONS (Schedule Options)" XER data map — https://docs.oracle.com/cd/F88966_01/English/Mapping_and_Schema/xer_import_export_data_map_project/97903.htm
- Oracle, "Activity dates" (P6 help) — https://docs.oracle.com/cd/F25600_01/client_help/ru_RU/activity_dates.htm
- Emerald Associates, "Primavera P6 Terms and Definitions" — https://www.emerald-associates.com/primavera-p6-terms-and-definitions.html
- tensix.com, "As Late As Possible Scheduling Constraint in P6 EPPM" — https://tensix.com/as-late-as-possible-scheduling-constraint-in-primavera-p6-eppm-explained
- Plan Academy, "As Late As Possible Constraint" — https://www.planacademy.com/as-late-as-possible-constraint-p6-video
- ProjectControls.online, "Best Practices — Constraints" — https://projectcontrols.blog/2024/04/23/best-practices-constraints
- Primavera Scheduling, "When P6 Late Dates are Early" — https://primaverascheduling.com/when-p6-late-dates-are-early
- Companion evidence doc: 03-xer-date-storage.md (raw XER field analysis of 11 real exports)
