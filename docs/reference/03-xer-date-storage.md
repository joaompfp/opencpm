# XER Date Storage: What P6 Actually Exports for Activity Dates

**Status:** Reference — openCPM parity research
**Date:** 2026-08-19
**Evidence base:** LIS10-Draft 19 (exported 2026-08-12, 483 tasks) and LIS10-Draft 21 (exported 2026-08-14, 487 tasks), both P6 15.2 EPPM exports; plus LIS10-Draft 14, "LIS1 - Data Center Full program" (Draft 12), "260525_Scenario A" (Draft 8), sample XERs and PyP6XER/xerparser parser sources. All date values below were read directly from the raw `%R` rows of the XER files (TSV, `latin-1`), column positions per the `%F` header.

> **File-location note:** this document lives at `opencpm/docs/reference/03-xer-date-storage.md` (the repo root is `/home/joao/projects/opencpm`). The XER evidence files used are under `/home/joao/.playwright-mcp/uploads/` and `/home/joao/projects/LIS1/planning/`.

**Bottom line:** a P6 XER stores the last *calculated* schedule results as plain columns on each `TASK` row — it is a snapshot of the database at export time, not a recomputation. Export does **not** recalculate. Therefore (a) early/late dates and float can be a mix of stamps from *different* schedule runs, (b) completed activities carry early dates that are a data-date stamp rather than their actuals, and (c) late dates can legitimately sit *before* early dates (negative float) when the project finish is constrained. Free float **is** stored (`free_float_hr_cnt`). Milestones export `LS == LF` exactly. All of these are observed in the LIS10 files and corroborated by Oracle P6 help and community sources below.

---

## 1. The TASK table: what P6 writes for computed dates

Every exported XER has one `TASK` row per activity. The `%F` header of LIS10-Draft 21 (61 columns) is, verbatim:

```
task_id proj_id wbs_id clndr_id phys_complete_pct rev_fdbk_flag est_wt lock_plan_flag
auto_compute_act_flag complete_pct_type task_type duration_type status_code task_code task_name
rsrc_id total_float_hr_cnt free_float_hr_cnt remain_drtn_hr_cnt act_work_qty remain_work_qty
target_work_qty target_drtn_hr_cnt target_equip_qty act_equip_qty remain_equip_qty cstr_date
act_start_date act_end_date late_start_date late_end_date expect_end_date early_start_date
early_end_date restart_date reend_date target_start_date target_end_date rem_late_start_date
rem_late_end_date cstr_type priority_type suspend_date resume_date float_path float_path_order
guid tmpl_guid cstr_date2 cstr_type2 driving_path_flag act_this_per_work_qty
act_this_per_equip_qty external_early_start_date external_late_end_date create_date update_date
create_user update_user location_id crt_path_num
```

The same 61-column layout appears in every P6 15.2 export examined (Draft 8/12/14/19/21, sample-schedule, sample-baseline). PyP6Xer parses exactly this header order (`xerparser/model/tasks.py` lines 161–170 in [PyP6Xer source](https://github.com/HassanEmam/PyP6Xer/blob/master/xerparser/model/tasks.py)), and jjCode01/xerparser maps the same fields in its `TASK` schema ([task.py](https://github.com/jjCode01/xerparser/blob/master/xerparser/schemas/task.py)).

**There is no `actual_duration` column.** P6 and the parser libraries derive "Actual Duration" from `act_start_date`/`act_end_date` (or `last_recalc_date` when `act_end_date` is blank), per the Deltek/Acumen XER calculated-fields spec ([source](https://help.deltek.com/product/acumentouchstone/8.2/ga/Primavera%20P6%20XER%20Calculated%20Fields.html)).

### 1.1 Field semantics, by activity status

All values below are from raw LIS10-Draft 21 rows; `''` = empty string in the file.

| XER field | Not Started (TK_NotStart) | Active (TK_Active) | Completed (TK_Complete) |
|---|---|---|---|
| `early_start_date` | forward-pass ES (logic + data date + constraints) | forward-pass ES of *remaining* work (data-date driven; **not** the actual start) | **data-date stamp, not the actual start** (see §2) |
| `early_end_date` | forward-pass EF | forward-pass EF of remaining work | **same stamp as ES** (ES=EF for all 65 completed rows in D21) |
| `late_start_date` | backward-pass LS | backward-pass LS of remaining work | backward-pass LS (real value, e.g. `2026-09-15 08:00` on A2200) |
| `late_end_date` | backward-pass LF | backward-pass LF | == LS (all 65 completed rows have LS=LF) |
| `total_float_hr_cnt` | float in hours (calendar hours, fractional e.g. `-0.6`) | float in hours | **empty** (`''`) for all 65 completed rows |
| `free_float_hr_cnt` | free float in hours, or `0` | free float in hours | **empty** (`''`) |
| `act_start_date` | `''` | actual start (`2026-06-11 08:00` on A1130) | actual start |
| `act_end_date` | `''` | `''` (blank until complete) | actual finish |
| `target_drtn_hr_cnt` | original duration, hours | original duration, hours | original duration, hours (kept; e.g. A1009=16) |
| `remain_drtn_hr_cnt` | == target duration (e.g. A1015: 64/64) | remaining hours (A1130: 96 of 200) | `0` |
| `phys_complete_pct` | `0` | 0–99 | `100` |
| `restart_date` / `reend_date` | remaining start/finish (blank when never scheduled) | remaining start/finish of remaining work (A1130: `2026-08-31 08:00` / `2026-09-15 16:00`) | blank per Oracle: Remaining Start/Finish are blank when complete |
| `rem_late_start_date` / `rem_late_end_date` | remaining late start/finish | set (A1130: = LS/LF) | blank per Oracle: Remaining Late Start/Finish are blank when complete |
| `target_start_date` / `target_end_date` | planned start/finish (set by scheduler, then frozen — not changed after actuals) | planned start/finish (frozen) | planned start/finish (frozen) |
| `expect_end_date` | manual expected finish (blank unless entered) | manual expected finish | manual expected finish |
| `cstr_type` / `cstr_date` | constraint code/date | constraint code/date | constraint code/date |

Source for field definitions: [PyP6Xer task.py docstrings](https://github.com/HassanEmam/PyP6Xer/blob/master/xerparser/model/classes/task.py) (e.g. total float = "Late Start - Early Start or Late Finish - Early Finish", free float = "amount of time the activity can be delayed before delaying the start date of any successor activity", remaining duration = "computed using the activity's calendar... After the activity is completed the remaining duration is zero"); Oracle P6 help "[Activity dates](https://docs.oracle.com/cd/F25600_01/client_help/ru_RU/activity_dates.htm)" (Remaining Start = Data Date once started; blank when complete).

### 1.2 Durations and float are calendar hours, not wall-clock hours

All `*_hr_cnt` values are hours counted on the activity's calendar. Oracle: remaining duration is "the total working time... computed using the activity's calendar" ([PyP6Xer task.py](https://github.com/HassanEmam/PyP6Xer/blob/master/xerparser/model/classes/task.py)); total float can be computed as LS−ES *or* LF−EF, "this option can be set when running the project scheduler" (same source; also [Emerald Associates](https://www.emerald-associates.com/item/early-dates-late-dates-and-total-float-in-primavera-p6.html)). Consequently **TF vs (LS−ES) checks must use calendar working hours**; wall-clock differences over weekends/holidays will not reconcile. This is the single most common false "stale file" signal (see §6).

The float values are hour-precision and fractional: D21 stores `-0.6`, `0.6`, `7.4`, `1936.6`, `72.6` etc. — i.e. P6's hour counts are computed with sub-hour calendar arithmetic (a 0.6 h residue appears wherever a 08:36 constraint/EF stamp meets a 08:00 anchor, see §4).

---

## 2. Completed activities: ES/EF are a data-date stamp, not the actuals

**Observation (LIS10-Draft 19 and 21, both exported from the same database):** all 65 `TK_Complete` rows have `early_start_date == early_end_date`, and 42 of 65 are stamped exactly `2026-08-09 23:59` — which is `PROJECT.last_recalc_date` of both files. The actual work spans are entirely different:

| task_code | stored ES/EF | act_start | act_end | target_drtn |
|---|---|---|---|---|
| A1002 (milestone) | `2026-08-09 23:59` | `2026-06-11 08:00` | `2026-06-11 08:00` | 0 |
| A1009 | `2026-08-09 23:59` | `2026-06-11 08:00` | `2026-06-26 16:00` | 16 |
| A2200 | `2026-08-09 23:59` | `2026-06-15 08:00` | `2026-06-17 16:00` | 40 |

The other 23 completed rows carry *other* stamps — `2026-08-12 16:00` (17 rows), `2026-08-14 16:00` (2), `2026-08-10 08:00`, `2026-08-13 16:00`, `2026-08-21 16:00`, `2026-09-11 16:00` (1 each). None equal the activity's actual start/end; none are the current data date. They look like snapshots from *intermediate schedule runs* of the same database (e.g. 2026-08-12 16:00 = the day Draft 19 was exported, `last_schedule_date = 2026-08-12 15:09`). Draft 19's completed rows show the **identical** stamp distribution — the stamp was baked into the database, not produced at export.

**Corroborating sources:**

- P6 help: under Retained Logic, Early Start/Finish "will always be visible, even if an activity is completed" — i.e. they are *displayed* values of the last run, not the actuals ([Oracle, Activity dates](https://docs.oracle.com/cd/F25600_01/client_help/ru_RU/activity_dates.htm)). The same page defines **Start** = Actual Start for started activities and **Finish** = Actual Finish for completed activities — the *user-facing* dates P6 uses are the actuals, never the early dates of a completed row.
- Practitioners: "When an actual start/finish date has been captured (as seen in the act_start_date and act_end_date fields above), then the dates that are stored in the early_start_date and early_end_date fields are no longer valid" — Darrin Kinney, [P6 Date Formats – Quick Data Hacks](https://datamonkeysite.com/2019/07/22/p6-date-formats-quick-data-hacks) (senior project controls professional; the recommended fix is `START = IF(ISBLANK(act_start_date), early_start_date, act_start_date)`).
- Parser libraries encode the same distrust: jjCode01/xerparser's `TASK.start` property returns `act_start_date` when present, falling back to `early_start_date` only when blank, and its `finish` property prefers `act_end_date` then `reend_date` then `early_end_date` ([task.py lines 284–293, 436–443](https://github.com/jjCode01/xerparser/blob/master/xerparser/schemas/task.py)). PyP6Xer's Task class parses the same fields with identical precedence semantics.
- Deltek's XER calculated-fields spec derives "Start Date" = `act_start_date` if present else `target_start_date`, and "Finish Date" = `act_end_date` if present else `target_end_date` — never the early dates ([Deltek Acumen Touchstone help](https://help.deltek.com/product/acumentouchstone/8.2/ga/Primavera%20P6%20XER%20Calculated%20Fields.html)).

**Engine consequence (validated on Draft 19):** pinning completed activities to their stored ES/EF *breaks* the forward pass — parity dropped from 88.5% to 64.4% ES. Pinning to `act_start`/`act_end` reproduces successor chains; the ES ≥ data-date floor catches anything earlier. See the openCPM semantics catalog (`cpm-engine-development` skill, `references/p6-xer-semantics.md`).

---

## 3. The data date: where it lives and how it is formatted

The XER has **no single "data date" column**. The relevant `PROJECT` row fields (Oracle XER data map: [P6 EPPM XER Import/Export Data Map Guide — PROJECT](https://docs.oracle.com/cd/F51303_01/English/Mapping_and_Schema/xer_import_export_data_map_project/97885.htm)):

| Field | Oracle name | LIS10-Draft 21 value | Meaning |
|---|---|---|---|
| `last_recalc_date` | Last Recalc Date (P6 EPPM) | `2026-08-09 23:59` | data-date stamp of the last recalc run that produced the stored early/late dates |
| `last_schedule_date` | Last Scheduled Date (P6 EPPM only) | `2026-08-14 15:09` | when the current schedule was last *calculated* |
| `next_data_date` | — (not in Oracle's PROJECT map; PyP6Xer parses it) | `''` | next data date; almost always empty in exports |
| `plan_start_date` | Planned Start | `2026-05-11 00:00` | project planned start |
| `scd_end_date` | Schedule Finish | `2027-10-13 08:00` | P6's computed project finish (used as backward-pass anchor; see `sched_use_project_end_date_for_float`) |
| `apply_actuals_date` | Last Apply Actuals Date | `''` | — |
| header row (`ERMHDR`) | — | `ERMHDR 15.2 2026-08-14 Project ADMIN tpous ...` | P6 version, **export** date, export user |

The first line of the file (`ERMHDR`) carries the *export* date; `last_recalc_date`/`last_schedule_date` carry schedule-run dates. In both LIS10 files: `last_recalc_date = 2026-08-09 23:59`, `last_schedule_date = 2026-08-12 15:09` (D19) / `2026-08-14 15:09` (D21).

**Format conventions:**
- All XER datetimes are strings `YYYY-MM-DD HH:MM` (no seconds, no timezone) — both parser libraries parse `'%Y-%m-%d %H:%M'` ([PyP6Xer task.py](https://github.com/HassanEmam/PyP6Xer/blob/master/xerparser/model/classes/task.py); jjCode01 `date_format` in [validators.py](https://github.com/jjCode01/xerparser/blob/master/xerparser/src/validators.py)).
- **`23:59` = "end of day" convention for EPPM data dates.** P6 EPPM stores the data date at 23:59 of the status day, so that the whole day counts as elapsed. This explains `last_recalc_date = 2026-08-09 23:59` and the completed-activity stamp `2026-08-09 23:59`. P6 Professional exports often carry `HH:00` instead (`2026-03-02 08:00` on the sample files, `2026-06-11 00:00` on Draft 12/14). Deltek's spec treats `last_recalc_date` as the "Status Date" (falling back to `plan_start_date` when empty or earlier), and uses it as the `act_end_date` substitute when computing Actual Duration of in-progress work ([Deltek](https://help.deltek.com/product/acumentouchstone/8.2/ga/Primavera%20P6%20XER%20Calculated%20Fields.html)).
- jjCode01/xerparser defines the effective data date as `max(last_recalc_date, plan_start_date)` ([project.py lines 46–49](https://github.com/jjCode01/xerparser/blob/master/xerparser/schemas/project.py)) — a sane default, but note it ignores `last_schedule_date`. If you need the *most recent* run, use `last_schedule_date`.
- A schedule that was never calculated exports `last_schedule_date=''` and a garbage `last_recalc_date` (`'0.0000'` in the agent-authored `260716-integrated-master-programme.xer`). Treat such files as uncalculated (the cpm-engine-development skill flags this class of fixture).

`next_data_date` was empty in all 11 real P6 exports examined; PyP6Xer still parses it ([project.py line 96](https://github.com/HassanEmam/PyP6Xer/blob/master/xerparser/model/classes/project.py)). Treat it as present-but-usually-empty; do not use it as the data date.

---

## 4. Zero-duration activities: milestones and zero-duration tasks

**Milestones (TT_Mile / TT_FinMile) export `late_start_date == late_end_date` exactly.** In LIS10-Draft 21: 60/60 milestones have LS=LF. In the Draft 12 file ("LIS1 - Data Center Full program.xer"): 72/72; Draft 14: 70/70; Scenario A: 23/23. Their early dates are also equal (ES=EF), as expected for zero duration. Example (Draft 12): `A1002 Start Early works: ES=EF=2026-06-11 08:00, LS=LF=2026-06-19 08:00, TF=48`.

**Zero-duration non-milestone tasks** (TT_Task with `target_drtn_hr_cnt=0`) also export LS=LF (0 exceptions in Draft 12/14/21's handful of such rows; the D21 set has 57 zero-duration not-started rows, all with LS=LF). This matches the engine rule in the openCPM semantics catalog: "Zero-duration: LS == LF exactly (no snap-back to previous window)" — the backward pass must be *identity* for zero duration, or every late date shifts by a day.

**Counter-example worth knowing:** the agent-authored `sample-schedule.xer` (never scheduled by P6; `last_schedule_date=''`) has 2/2 milestones with LS≠LF and ES≠EF (8 h apart) — the file's author modelled milestones as 8-hour activities. This is evidence *against the fixture*, not against the rule: real P6 exports always satisfy ES=EF and LS=LF on milestones. The cpm-engine-development skill uses this exact file as its cautionary example.

**The 08:36/15:24 residue.** D21's zero-duration rows downstream of a `CS_MEO` constraint at 08:36 store EF/LF at `08:36` (e.g. `A3730 ES=2027-04-05 08:36, LS=2027-04-05 08:00`) and a cluster stores `15:24` (`A35241 ES=2026-08-12 08:00 LS=2026-08-11 16:00`, `A35351 ES=2026-08-12 16:00 LS=2026-08-12 15:24`). These are genuine P6 output — constraint timestamps propagate through zero-duration late-date arithmetic and P6 does *not* snap them back to the calendar window edge in every case. The openCPM engine matches P6 to 96.7% LS on Draft 19; the residual ~36-min differences on Draft 21 are this stamp residue, not staleness (cpm-engine-development status notes).

**Negative float on milestones is normal.** D21 milestone `A1019 Power ON - DH117` stores `TF=-0.6`, `LS=2027-04-30 16:00 < ES=2027-05-03 08:36` — a finish milestone whose late date is earlier than its early date because the constrained project finish forces it. See §6 for why this is legitimate.

---

## 5. Free float: yes, it is stored

`free_float_hr_cnt` is a real TASK column (col 17 in the 61-column layout) and it is **populated** in every real P6 export examined (11 files). Distribution in LIS10-Draft 21 (487 rows):

- `''` (empty): 65 rows — exactly the completed activities (same rule as total float: no float once complete)
- `0`: 292 rows
- positive values in hours, fractional allowed: e.g. `8`, `40`, `104`, `0.6`, `344.6`, `1936.6`, `2024`
- relationship to total float: in the data, FF ≤ TF whenever TF ≥ 0 (e.g. A2410 TF=56 FF=8; A1018 TF=144 FF=104), and rows with negative TF store FF=`0` (all 34 negative-TF rows except A8000, TF=-1, which stores FF=`0.6`).

Semantics (PyP6Xer docstring): "The amount of time the activity can be delayed before delaying the start date of any successor activity" ([task.py](https://github.com/HassanEmam/PyP6Xer/blob/master/xerparser/model/classes/task.py)). jjCode01/xerparser parses it (`optional_float`) and exposes `TASK.free_float` in days (`free_float_hr_cnt / 8`, assuming 8 h/day) ([task.py lines 138, 296–300](https://github.com/jjCode01/xerparser/blob/master/xerparser/schemas/task.py)).

**Engine implication:** openCPM currently computes free float; it can be *validated* directly against `free_float_hr_cnt` for all not-started/active rows (calendar hours, tolerance ~1 h), the same way total float is validated. There is no separate "free float" field anywhere else in the XER (no such column in TASKFIN, TASKPRED, or PROJWBS).

---

## 6. Does export recalculate? — No. The XER is a snapshot; late dates can be stale

**Export does not run the scheduler.** The XER dumps the stored database columns as-is. Evidence:

1. **`last_schedule_date` vs `last_recalc_date` vs export date.** D19 was exported 2026-08-12 (ERMHDR) while `last_schedule_date = 2026-08-12 15:09` and `last_recalc_date = 2026-08-09 23:59`. If export recalculated, the file would carry the export time as the recalc stamp. D21 was exported 2026-08-14, `last_schedule_date = 2026-08-14 15:09` — 15:09 on *two different days* for two different exports of the same project is the user's manual "Schedule" click time, not an export-side run (and the data date/recalc stamp is still 08-09).
2. **Completed-activity stamps predate the export** (§2): identical stamp distributions in D19 and D21 exported 2 days apart — the stamps are stored in the database.
3. **Mixed stamps in one file:** D21 stores 42 completed rows at `2026-08-09 23:59` (last_recalc) *and* 17 at `2026-08-12 16:00` (a run between 08-09 and 08-14) *and* others — impossible in a single recalculation, proof that TASK columns accumulate values across runs and export writes whatever is there. The terminal milestone of D21 stores `LF=2026-10-11 16:00 < ES=2027-10-13 08:00` with `TF=0` — a mix of stamps from different runs in the same row (noted in the cpm-engine-development skill).
4. **Oracle's own guidance** on XER round-tripping: "Once data is exported from P6 into another project management tool, dates, durations and other data may no longer reflect those in P6 if the other project management tool **recalculates** this data" (Planning Engineer FZE, quoting Oracle, [Primavera P6 Export File Types Explained](https://planningengineer.net/primavera-p6-export-file-types-explained)) — i.e. the XER carries P6's last computed values and *recalculation happens on the receiving side*, not at export.
5. P6 EPPM's export dialog exports "the current project schedule and any selected baselines or scenarios" — the current stored schedule ([Oracle Primavera Cloud export help](https://docs.oracle.com/cd/E80480_01/English/admin/app_admin_guide/144609.htm)).

**Consequences for parity work:**

- **Late dates (and TF, and even ES/EF of completed rows) are only as fresh as the last Schedule run** that wrote them. If a planner edits logic/durations and exports *without* rescheduling, the file mixes pre-edit early dates with post-edit actuals, or vice-versa. The data-date floor for ES is *not* re-applied at export.
- **`TF == calendar_hours(LS − ES)` is the correct internal-consistency test for a single run**, and it fails on mixed-stamp rows. On D21, wall-clock checks falsely flagged ~70% of rows; even calendar-hour checks flag rows whose LS/ES come from different runs (previous openCPM analysis: 299/422 rows failed calendar-hour reconciliation on D21, and the terminal milestone was self-contradictory — see the semantics catalog). Draft 19 is the clean parity reference.
- **LS < ES with TF = 0 (or slightly negative) is legitimate P6**, not corruption, when the project finish is constrained: "when the project end date is constrained, activities that are behind schedule flip the script... the late dates are earlier than the early dates... The late dates, being constrained by the last activity, are indicative of how to get back 'on' schedule" ([Primavera Scheduling, "When P6 Late Dates are Early"](https://primaverascheduling.com/when-p6-late-dates-are-early)). D21 has 34 non-completed rows with LS < ES (e.g. `A1070 ES=2027-01-15 08:00 LS=2027-01-14 16:00 TF=0`; `A8000 ES=2027-01-15 08:00 LS=2027-01-14 16:00 TF=-1`), all on the constrained finish chain — consistent with this behavior, *not* with stale late dates. Draft 12/14/Scenario A (no finish constraint in play) have **zero** LS<ES rows.
- **TF values in the file do not need to equal LS−ES to the minute even in a single run:** P6 computes float with sub-hour calendar arithmetic (fractional values like `-0.6`), and with `sched_float_type=FT_FF` (both LIS10 files) float is finish-float, computed from LF−EF — comparing against LS−ES in calendar hours is only approximately equivalent (a full-day-identity subtlety for zero-duration rows). Always compare TF against both (LS−ES) and (LF−EF), in calendar hours, with a tolerance.

---

## 7. Known quirks — quick list

1. **Completed activities: `early_start_date`/`early_end_date` are not actuals.** They carry the data-date stamp of the last recalc (42/65 rows in both LIS10 drafts: `2026-08-09 23:59` = `last_recalc_date`) or an intermediate run's stamp. Use `act_start_date`/`act_end_date` for completed rows (Oracle help; datamonkeysite; both parsers' start/finish precedence). ES=EF on all 65 completed rows.
2. **Completed activities: `total_float_hr_cnt` and `free_float_hr_cnt` are empty** (`''`), not 0. Filter `None` before float math (PyP6XER: completed tasks have `total_float_hr_cnt = None`).
3. **Export never recalculates.** The XER is a database snapshot; early/late dates can mix stamps from different Schedule runs. `last_recalc_date` (data date of last recalc), `last_schedule_date` (last Schedule click), and the ERMHDR line (export date) are three different clocks. Check `last_schedule_date` freshness before trusting late dates.
4. **No `actual_duration` column** — derive from `act_start`/`act_end` (or `last_recalc_date` when in progress).
5. **Milestones and zero-duration tasks export LS = LF exactly.** Backward pass must be identity for zero duration (no snap-back), or every LS/LF shifts.
6. **Constraint timestamps leak into late dates** (08:36, 15:24 residues in D21). P6 does not always snap zero-duration late dates back to calendar window edges.
7. **LS < ES with TF=0/negative is legitimate** under a constrained project finish ("late dates are early"); it indicates the schedule is behind the finish target. Do not flag as stale by itself.
8. **Float hours are calendar hours and fractional** (`-0.6`, `0.6`, `1936.6`). Wall-clock reconciliation of TF vs LS−ES is meaningless; even calendar-hour checks need ~1 h tolerance and both (LS−ES) and (LF−EF).
9. **Data date convention: EPPM stamps end-of-day `23:59`** (`2026-08-09 23:59`); Professional exports often `HH:00` or `00:00`. Parse `%Y-%m-%d %H:%M`; never assume midnight.
10. **`next_data_date` exists but is empty in real exports** — not a usable data date.
11. **`last_recalc_date` can be garbage (`'0.0000'`)** in never-scheduled files; detect via `last_schedule_date=''`.
12. **The terminal milestone can store LF < its own ES with TF=0** (D21 Milestone 20: LF=2026-10-11 16:00, ES=2027-10-13 08:00) — a mixed-stamp artifact of multiple runs, reproducible by no single engine run. File-level data-quality ceiling, not engine error.
13. **Free float IS stored** (`free_float_hr_cnt`, col 17) — validate the engine's FF against it; it is empty only for completed rows.

---

## 8. Sources

**Primary evidence (raw XER rows read for this document):**
- `/home/joao/.playwright-mcp/uploads/LIS10-Draft 19.xer` (exported 2026-08-12, P6 15.2 EPPM, 483 tasks)
- `/home/joao/.playwright-mcp/uploads/LIS10-Draft 21.xer` (exported 2026-08-14, 487 tasks)
- `/home/joao/projects/LIS1/planning/LIS1 - Data Center Full program.xer` (Draft 12), `/home/joao/vaults/pessoal/LIS10-Draft_14.xer`, `/home/joao/projects/CoW/DLR-LIS10-2.4MW-Refit/PMO/Programme/260525_Scenario A - Early Delivery Room DH117 Level 01 - Print Primavera P6.xer`, `/home/joao/.playwright-mcp/sample-schedule.xer` and `sample-baseline.xer`

**Parser sources (cloned 2026-08-19):**
- jjCode01/xerparser — https://github.com/jjCode01/xerparser (`xerparser/schemas/task.py`, `project.py`, `schedoptions.py`, `src/validators.py`)
- HassanEmam/PyP6Xer — https://github.com/HassanEmam/PyP6Xer (`xerparser/model/classes/task.py`, `xerparser/model/tasks.py`, `xerparser/model/classes/project.py`)

**Specifications and help:**
- Oracle P6 help, "Activity dates" — https://docs.oracle.com/cd/F25600_01/client_help/ru_RU/activity_dates.htm (Early/Late/Remaining date definitions; Retained Logic visibility; Remaining Start = Data Date once started; Remaining dates blank when complete)
- Oracle, "P6 EPPM XER Import/Export Data Map Guide (Project)" — https://docs.oracle.com/cd/F51303_01/English/Mapping_and_Schema/xer_import_export_data_map_project/97885.htm (PROJECT columns: last_recalc_date, last_schedule_date, scd_end_date, plan_start_date, apply_actuals_date)
- Deltek Acumen Touchstone, "Primavera P6 (XER) Calculated Fields" — https://help.deltek.com/product/acumentouchstone/8.2/ga/Primavera%20P6%20XER%20Calculated%20Fields.html (derivation rules for Actual Duration, Status Date, Start/Finish, Critical Flag)

**Community / practitioner:**
- Darrin Kinney, "P6 Date Formats – Quick Data Hacks" — https://datamonkeysite.com/2019/07/22/p6-date-formats-quick-data-hacks (early dates invalid once actuals exist; START/FINISH formulas)
- "When P6 Late Dates are Early" — https://primaverascheduling.com/when-p6-late-dates-are-early (constrained end date ⇒ late dates earlier than early dates; negative float is intended)
- Emerald Associates, "Early Dates, Late Dates and Total Float in Primavera P6" — https://www.emerald-associates.com/item/early-dates-late-dates-and-total-float-in-primavera-p6.html (forward/backward pass; TF = LS−ES or LF−EF, scheduler option)
- Planning Engineer FZE, "Primavera P6 Export File Types Explained" — https://planningengineer.net/primavera-p6-export-file-types-explained (XER is a snapshot; recalculation happens on the importing side — quoting Oracle)
- Plan Academy, "Understanding Primavera XER Files" — https://www.planacademy.com/understanding-primavera-xer-files (%T/%F/%R/%E structure; header row semantics)
- Oracle Primavera Cloud export help — https://docs.oracle.com/cd/E80480_01/English/admin/app_admin_guide/144609.htm (export exports the current stored schedule; no recalculation step)
