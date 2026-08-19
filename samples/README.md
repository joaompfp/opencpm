# Parity fixtures — real P6 XER exports

Genuine Primavera P6 exports (verified via `ERMHDR`), collected as test subjects for
the CPM engine. Every file carries **P6's own computed ES/EF/LS/LF/TF**, which is what
makes them usable as a parity oracle: run the solver, diff against the dates P6 already
wrote into the file.

Ordered as a difficulty ladder — if an early one fails, the later ones will too, so fix
in order.

| File | Acts | Rels | Calendars | Constraints | P6 | What it exercises |
|---|---|---|---|---|---|---|
| `01-basic-fs-only.xer` | 25 | 40 FS | 2 (8h) | none | 8.2 | Bare minimum: pure FS, **zero lags, zero constraints**. The floor — if this isn't 100%, the core forward/backward pass is wrong. |
| `02-multi-calendar-lags.xer` | 66 | 66 FS + 18 SS | **4** (8h) | 1 × `CS_MSOB` | 5.0 | Calendar arithmetic across 4 different calendars, **28 relationships with lag**, start/finish milestones. |
| `03-all-rel-types-10h-cal.xer` | 198 | 269 FS + 10 SS + 2 FF + **20 SF** | 1 (**10h/day**) | none | 8.2 | All four relationship types incl. rare **SF**, and a **10-hour workday** — catches any hardcoded 8h/day assumption. |
| `04-scale-4217-alap.xer` | 4217 | 5925 FS + 1083 SS + 577 FF + 1 SF | **11** | **20 × `CS_ALAP`** | 6.0 | Scale + performance, 1336 lagged relationships, and ALAP semantics. |

## Gotcha on `04-scale-4217-alap.xer`

This file contains **4 projects**, and the one with the activities is **not the first**:

| proj_short_name | activities |
|---|---|
| `DS` | 0 |
| `OP` | 0 |
| `CR` | 19 |
| `HBTF-2` | **4217** |

`xer_adapter.load_xer()` selects the project owning the most TASK rows, so
this file loads the right project (HBTF-2) automatically. Parity (Aug 2026):
LS 99.5%, LF 96.5%, ES 54.1% (ES residue = FF-lag arithmetic + 12/20
CS_ALAP rows). Untracked — 3.8MB third-party data; re-fetch with:

```bash
curl -sL "https://raw.githubusercontent.com/soulmajor1/Primavera-P6-Xer-Viewer/HEAD/XER%20Files/Hotel%20Project.xer" \
  -o samples/04-scale-4217-alap.xer
```

## Running parity

The import path is order-sensitive (`xer_adapter/` must come *before* `.`, since
`xer_adapter/__init__.py` doesn't re-export `load_xer`), and PyP6XER must be importable:

```bash
cd ~/projects/opencpm
PYTHONPATH=xer_adapter:. python3 tests/validate_against_p6.py samples/01-basic-fs-only.xer
```

If `xerparser` isn't installed in the active interpreter, XERlock's venv has it:
`~/projects/schedule-app/.venv/bin/python3`.

## Why these, specifically

`01` isolates the core with everything else stripped away. `02` adds the two things most
likely to break calendar-aware arithmetic (multiple calendars, lags). `03` is the only one
with SF relationships and a non-8h workday. `04` is the realistic stress case and the only
one besides the LIS file with ALAP constraints — relevant because on LIS the forward-pass
mismatches all skew *earlier than P6*, which is the signature of ALAP not being fully
applied, and LIS has 26 of them.

## Provenance / licensing

Third-party files pulled from public GitHub repos, retained under their original names in
the table below. They are 2012–2013-era exports (P6 v5.0–8.2) — good for core semantics,
but they predate newer P6 features.

| File | Source repo | Original path |
|---|---|---|
| `01-basic-fs-only.xer` | `Constology/XERNative` | `sample.xer` |
| `02-multi-calendar-lags.xer` | `soulmajor1/Primavera-P6-Xer-Viewer` | `XER Files/TERMINAL BUILDING-AIRPORT.xer` |
| `03-all-rel-types-10h-cal.xer` | `Constology/XERNative` | `wk2.xer` |
| `04-scale-4217-alap.xer` | `soulmajor1/Primavera-P6-Xer-Viewer` | `XER Files/Hotel Project.xer` |

Neither source repo carries an explicit licence for these files, and they contain real
company/project names. **04 is untracked** (3.7 MB history bloat, unlicensed third-party);
01-03 are committed (407 KB total) so the parity ladder is reproducible from a clean clone.
Current parity (Aug 19 2026, after the backward-pass anchor fix):

| File | ES | EF | LS | LF | TF |
|---|---|---|---|---|---|
| 01-basic-fs-only | 100% | 100% | 100% | 100% | 100% |
| 02-multi-calendar-lags | 98.5% | 98.5% | 98.5% | 86.4% | 98.5% |
| 03-all-rel-types-10h-cal | 100% | 98.0% | 93.4% | 94.9% | 94.9% |
| 04-scale-4217-alap | 54.1% | 54.1% | 99.5% | 96.6% | 54.2% |

LIS10 (real DLR files): Draft 19 ES 88.5% / LS 99.0% / LF 98.8%; Draft 21
ES 88.4% / LS 96.7% / LF 97.4%.
