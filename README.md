# boomsonic_v0 — 500 N-class turbojet + ≤25 kg MTOW airframe conceptual design study

Integrated engine/airframe conceptual sizing study. See `turbojet_500N_mission_brief.md`
for the brief, `tools_survey.md` for the Phase 0 tool survey, `design_log.md` for the
running decision log, and (at the Phase 5 gate) `design_freeze.md`.

## Repo layout

```
scripts/
  phase0_tools/          smoke tests for every candidate tool (+ vendored upstream examples)
  phase1_requirements/   operating point + mission definition
  phase2_airframe/       ADRpy constraint diagram, mass budget
  phase3_cycle/          pyCycle + Cantera cycle model and architecture trades
  phase4_turbomachinery/ turbo-design / TurboFlow meanline design, maps, mass estimate
plots/                   all generated figures
data/                    input data (engine database, maps, mission tables)
docs/                    supporting notes
design_log.md            running decision log (tool, inputs, outputs, why)
tools_survey.md          Phase 0 deliverable
requirements-np2.txt     frozen main env (.venv, NumPy 2)
requirements-np1.txt     frozen legacy env (.venv-np1, NumPy 1.26)
```

## Environments (two, on purpose)

Python 3.12.10 via `uv`. Two venvs because ADRpy and TurboFlow are NumPy-1-only while
OpenMDAO/pyCycle and turbodesigner require NumPy ≥ 2 (details in `tools_survey.md`).

```powershell
uv venv --python 3.12 .venv      ; $env:VIRTUAL_ENV="$PWD\.venv";     uv pip install -r requirements-np2.txt
uv venv --python 3.12 .venv-np1  ; $env:VIRTUAL_ENV="$PWD\.venv-np1"; uv pip install -r requirements-np1.txt
```

| env         | packages                                                        | used for                              |
|-------------|-----------------------------------------------------------------|---------------------------------------|
| `.venv`     | openmdao, om-pycycle (git), cantera, turbo-design (git), turbodesigner, pyturbo-aero, aerosandbox | cycle, combustion, turbomachinery, drag build-up |
| `.venv-np1` | ADRpy, turboflow, CoolProp                                       | airframe constraint sizing, centrifugal/axial meanline cross-check |

## Phase 0 smoke tests

```powershell
.venv\Scripts\python scripts\phase0_tools\smoke_pycycle.py        # design + 2 off-design points converge
.venv\Scripts\python scripts\phase0_tools\smoke_cantera.py        # kerosene surrogate T_ad, gamma, cp
.venv\Scripts\python scripts\phase0_tools\smoke_turbodesign.py    # NASA HECC centrifugal validation (PR, eta vs measured)
.venv\Scripts\python scripts\phase0_tools\smoke_turbodesigner.py  # axial compressor meanline at micro scale
.venv-np1\Scripts\python scripts\phase0_tools\smoke_adrpy.py      # jet constraint diagram at 25 kg scale
.venv-np1\Scripts\python scripts\phase0_tools\smoke_turboflow.py  # centrifugal compressor meanline (Oh losses)
```

## Phase 2 (airframe sizing)

```powershell
python scripts\phase2_airframeun_phase2.py     # regenerates every Phase 2 table and plot (both venvs)
```

Report: `docs/phase2_airframe.md`. Key plots: `plots/phase2_constraint_diagram.png`,
`plots/phase2_drag_polar.png`, `plots/phase2_area_distribution.png`,
`plots/phase2_mass_budget.png`, `plots/phase2_engine_database.png`.
