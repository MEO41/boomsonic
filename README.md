# boomsonic_v0 — 500 N-class turbojet + ≤25 kg MTOW airframe conceptual design study

Integrated engine/airframe conceptual sizing study. See `turbojet_500N_mission_brief.md`
for the brief, `tools_survey.md` for the Phase 0 tool survey, `design_log.md` for the
running decision log, and (at the Phase 5 gate) `design_freeze.md`.

![Alt text](https://github.com/MEO41/boomsonic/blob/main/plots/phase6_engine_cutaway.png?raw=true)


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

## Phase 6 (CAD / 3D; started on the user's instruction, freeze decisions still open)

Report: `docs/phase6_cad.md`. Engine, impeller and airframe CAD in STEP (`cad/`), an item-by-item mass check against
the analysis model, a 3D cyclic-sector FE of the impeller, and the airframe integration checks. Findings:
* the inducer throat needed a new camber law to keep the 10 % choke margin;
* the exducer root stays on its limit in 3D;
* the inducer root runs 1.8 × the 1D estimate (inside the limit);
* the engine-to-skin gap is 8.7 mm;
* the jetpipe loses ~0.6 % total pressure.

The freeze's open risks are carried unchanged. Environment: `.venv-cad` (`requirements-cad.txt`).

```powershell
.venv-cad\Scripts\python scripts\phase6_cad\smoke_cad.py          # CAD toolchain primitives
.venv\Scripts\python scripts\phase6_cad\make_params.py            # parameter sheet (frozen / derived / provisional)
.venv-cad\Scripts\python scripts\phase6_cad\impeller_cad.py       # impeller + FE sector (~10 min); IMP_THROAT_ONLY=1 for the camber scan
.venv-cad\Scripts\python scripts\phase6_cad\engine_cad.py         # engine parts + assembly
.venv-cad\Scripts\python scripts\phase6_cad\airframe_cad.py       # airframe + integration checks
.venv-cad\Scripts\python scripts\phase6_cad\fe3d_impeller.py A,B,BT,P,PF   # 3D FE: verifications, production, mesh check
.venv\Scripts\python scripts\phase6_cad\mass_compare.py           # CAD vs bottom-up mass model
.venv-cad\Scripts\python scripts\phase6_cad\render_cad.py         # plots/phase6_*.png
.venv-cad\Scripts\python scripts\phase6_cad\spec_sheet.py         # docs/boomsonic_engine_spec.pdf (engine specification, all numbers from data)
```

## Phase 5 design freeze (status snapshot)

`docs/design_freeze.md`: the current design with its open risks stated explicitly (surge margin, idle-range transient
margin, shortened combustor, diffuser-vane/exducer resonance at idle, no hardware validation). Formal sign-off was not
recorded; Phase 6 started on the user's instruction with the freeze decisions left open.

## Phase 4 on the centrifugal baseline (turbomachinery, rotor, closure)

Report: `docs/phase4r_centrifugal.md`. Engine 6.85 kg / 426 mm / 187 mm; TOGW 20.1 kg; top open risk: compressor surge
margin (vaned-diffuser stall not modelled; the peak-PR surrogate fails on NASA HECC).

```powershell
.venv\Scripts\python scripts\phase4_turbomachinery\td_check.py                  # NASA turbo-design check of the impellers
.venv\Scripts\python scripts\phase4_turbomachinery\hecc_surge_check.py          # surge surrogate vs NASA HECC measured
.venv\Scripts\python scripts\phase4_turbomachinery\cc_blade_modes.py            # exducer blade modes / Campbell screening
.venv\Scripts\python scripts\phase4_turbomachinery\cc_rotor.py                  # rotor model, critical-speed map (~7 min)
.venv\Scripts\python scripts\phase4_turbomachinery\cc_rotor_stiffening.py       # levers on the bending critical (~15 min)
.venv\Scripts\python scripts\phase4_turbomachinery\cc_rotor_final.py            # chosen rotor: Campbell, API check
.venv\Scripts\python scripts\phase4_turbomachinery\cc_transient.py ce75000_opr4_t1150_b15_cap 0.00213   # acceleration
.venv\Scripts\python scripts\phase4_turbomachinery\cc_closure.py                # engine update + Phase 2 <-> 4 mass closure
```

## Phase 3R (centrifugal-only redesign)

Report: `docs/phase3r_centrifugal.md`. Recommended engine: single-stage centrifugal, OPR 4, 75 000 rpm, 15 deg
backsweep (187 mm, 6.74 kg, +55 / +29 % dash margin, TOGW 20.0 kg). Outputs in `data/phase3r/` and `data/phase3r_*`.
TurboFlow's centrifugal slip model is patched at run time (`scripts/phase3_cycle/turboflow_fixes.py`).

```powershell
.venv-np1\Scripts\python scripts\phase3_cycle\verify_turboflow_slip.py              # evidence for the TurboFlow slip defect + fix
$env:P3_DATA="phase3r"; $env:P3_CC_OPTS='{"Z": 12, "Z_split": 12, "split_frac": 0.5, "effective_width": true, "choke_margin": 0.10}'; $env:P3_OUT_SUFFIX="_3r"; .venv\Scripts\python scripts\phase3_cycle\validate_mass_model.py
.venv\Scripts\python scripts\phase3_cycle\inducer_anchor.py                          # fielded inducer relative Mach range
.venv\Scripts\python scripts\phase3_cycle\impeller_stress.py                         # regression vs the Phase 4 gate
.venv\Scripts\python scripts\phase3_cycle\cc_screen.py                               # 36-design screen (OPR x rpm x backsweep)
.venv\Scripts\python scripts\phase3_cycle\cc_trade.py run 4.0:75000:-15              # one full-chain case (run cases in parallel)
.venv\Scripts\python scripts\phase3_cycle\cc_trade.py reeval                         # re-evaluate saved designs without re-design
.venv\Scripts\python scripts\phase3_cycle\cc_trade.py compile                        # data/phase3r_cc_trade.csv + plot
$env:CC_SRC="data/phase3r/ce75000_opr4_t1150_b15_cap_cc_out.json"; $env:MAP_DIR="data/phase3r/maps"; $env:CC_GROUPS="1.0,0.6 1.05,0.5 0.95,0.4 0.9,0.7 0.85,0.8 0.35,0.3"; bash scripts/phase4_turbomachinery/run_centrifugal_map.sh ce75000_opr4_t1150_b15_cap
$env:TT_SRC="data/phase3r/ce75000_opr4_t1150_b15_cap_tt_out.json"; $env:TMAP_NS="1.0 1.1 0.9 0.8 0.7 0.6 0.5 0.4 0.3 0.25"; bash scripts/phase4_turbomachinery/run_turbine_map.sh ce75000_opr4_t1150_b15_cap
.venv\Scripts\python scripts\phase3_cycle\cc_mission.py ce75000_opr4_t1150_b15_cap   # running lines, deck, sortie ('lines' = running lines only)
.venv\Scripts\python scripts\phase3_cycle\cc_sensitivity.py ce75000_opr4_t1150_b15_cap
.venv\Scripts\python scripts\phase3_cycle\plot_phase3r.py
```

Map generation is memory-hungry. Running the compressor groups and turbine lines of more than two maps at once on a
14 GB machine crashed processes with `MemoryError`; re-run failed groups under their original part numbers.

## Phase 3 (engine cycle and architecture trade; superseded by Phase 3R)

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
