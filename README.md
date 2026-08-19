# openCPM

Open-source Critical Path Method engine — calendar-aware scheduling that
replicates Primavera P6 semantics for XER files.

## Architecture

```
opencpm/           core library (ZERO external dependencies)
  model.py         Schedule / Activity / Calendar dataclasses
  solver.py        CalendarTime arithmetic + Solver (forward/backward pass,
                   float, constraints, critical path)
xer_adapter/       XER import via PyP6XER -> core model objects
tests/             synthetic validation + P6 parity harness
```

The core library is deliberately format-agnostic: it knows nothing about XER,
P6, or Oracle. Adapters convert external formats into the model. Future UIs,
APIs, and report tools build on the same core.

## Status (prototype)

- Calendar-aware forward/backward pass with FS/SS/FF/SF + hour lags: WORKING
  (verified on a hand-computed synthetic network)
- Data date anchoring, actuals for completed activities: WORKING
- Constraint handling v1: CS_MEO, CS_MSOA, CS_ALAP (pinned + cascade)
- Critical path (TF=0 chain): WORKING
- P6 parity on real LIS10-Draft 21: ES exact 16.6%, TF 32.8% — remaining gaps
  are constraint semantics and backward-pass anchor behavior

## Run

```bash
# synthetic validation
python3 -c "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'xer_adapter'); from tests.test_synthetic import main; main()"

# P6 parity diff on a real XER
python3 tests/validate_against_p6.py /path/to/file.xer
```

## Roadmap

- [ ] Data date / retained logic modes
- [ ] Free float
- [ ] Baseline comparison + slippage
- [ ] Edit layer (change duration, add/remove logic, re-solve)
- [ ] Export computed XER
- [ ] Remaining constraint types (SNET, FNET, MSO, MFO, ALAP secondary)
