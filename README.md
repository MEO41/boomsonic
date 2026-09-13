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
python scripts/phase2_airframe/run_phase2.py     # regenerates every Phase 2 table and plot (both venvs)
```

Report: `docs/phase2_airframe.md`. Key plots: `plots/phase2_constraint_diagram.png`,
`plots/phase2_drag_polar.png`, `plots/phase2_area_distribution.png`,
`plots/phase2_mass_budget.png`, `plots/phase2_engine_database.png`.

## Phase 3 (engine cycle and architecture trade)

Report: `docs/phase3_engine.md`. Main entry points (run from the repo root with `.venv`; they
call TurboFlow in `.venv-np1` themselves):

```powershell
.venv\Scripts\python scripts\phase3_cycle\arch_trade.py            # env: P3_OPR, P3_CASES, P3_TURB_CAP, P3_CC_REF
.venv\Scripts\python scripts\phase3_cycle\compile_trade.py         # summary table + plots/phase3_arch_trade.png
.venv\Scripts\python scripts\phase3_cycle\validate_mass_model.py   # P400 / Nike validation of the mass model
```

## Phase 4 entry gate (impeller stress check, pure centrifugal)

Report: `docs/phase4_impeller_stress_gate.md`. Verdict: the disc and burst pass with a boreless
hub, but the 30 deg backswept exducer blade root fails at 537 m/s. Phase 4 proceeds on the pure axial.

```powershell
.venv\Scripts\python scripts\phase4_turbomachinery\verify_axisym_fe.py       # FE check vs rotating-disc theory
.venv\Scripts\python scripts\phase4_turbomachinery\impeller_stress_gate.py   # hub sweep, burst, blade root (~7 s)
.venv\Scripts\python scripts\phase4_turbomachinery\impeller_gate_extras.py   # thermal gradient, backsweep sensitivity
```

## Phase 4 (axial engine: Phase 3 correction, operability, rotor dynamics)

**Reports:**
* `docs/phase3_engine.md` section 14: erratum, with corrected axial numbers;
* `docs/phase4_operability.md`;
* `docs/phase4_rotordynamics.md`.

```powershell
.venv\Scripts\python scripts\phase4_turbomachinery\check_turbodesigner_blockage.py        # evidence for the Phase 3 blockage error
$env:P3_OPR=5; $env:P3_CASES="axial:0"; $env:P3_TURB_CAP=1; $env:P3_CC_REF=0.794; $env:P3_TAG_SUFFIX="_blk"; .venv\Scripts\python scripts\phase3_cycle\arch_trade.py
bash scripts/phase4_turbomachinery/run_turbine_map.sh ax0_opr5_t1150_cap_blk                 # TurboFlow turbine map (.venv-np1)
.venv\Scripts\python scripts\phase4_turbomachinery\operability.py ax0_opr5_t1150_cap_blk      # stacking map, running lines, variable IGV
.venv\Scripts\python scripts\phase4_turbomachinery\nozzle_sweep.py ax0_opr5_t1150_cap_blk 1.3,1.6,2.0
.venv\Scripts\python scripts\phase4_turbomachinery\bleed_sweep.py ax0_opr5_t1150_cap_blk 0.1,0.2,0.3
.venv\Scripts\python scripts\phase4_turbomachinery\running_line_axi5.py                      # bracket with the NPSS AXI5 map
.venv\Scripts\python scripts\phase4_turbomachinery\plot_operability.py
.venv\Scripts\python scripts\phase4_turbomachinery\rotordynamics_verify.py; .venv\Scripts\python scripts\phase4_turbomachinery\rotordynamics.py
```

### Option B checks (axial-centrifugal) and method benchmark

Report: `docs/phase4_optionB_checks.md`.

```powershell
.venv\Scripts\python scripts\phase4_turbomachinery\impeller_check_ac.py                 # check 1: impeller stress, both AC variants
bash scripts/phase4_turbomachinery/run_centrifugal_map.sh ax90000_opr4_t1150_ax2_pa2_cap_blk   # TurboFlow centrifugal map (.venv-np1); CC_ATR=0.80 + suffix for the throat sensitivity
.venv\Scripts\python scripts\phase4_turbomachinery\ac_operability.py ax90000_opr4_t1150_ax2_pa2_cap_blk [neg_width] [cc map]
.venv\Scripts\python scripts\phase4_turbomachinery\cc_benchmark.py                      # same chain on the JetCat P400 model (idles at 31 %)
.venv\Scripts\python scripts\phase4_turbomachinery\plot_optionB.py
```
