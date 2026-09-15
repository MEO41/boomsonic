# Running the code

Per-phase command reference for `boomsonic_v0`. Everything runs **from the repo root**.
See [README.md](../README.md) for what the project is and what it found, and [axial/README.md](../axial/README.md) for the axial branch.

## Environments (three, on purpose)

Python 3.12.10 via `uv`. Three venvs because ADRpy and TurboFlow are NumPy-1-only while
OpenMDAO/pyCycle and turbodesigner require NumPy ≥ 2 (details in `tools_survey.md`).

```powershell
uv venv --python 3.12 .venv      ; $env:VIRTUAL_ENV="$PWD\.venv";     uv pip install -r requirements-np2.txt
uv venv --python 3.12 .venv-np1  ; $env:VIRTUAL_ENV="$PWD\.venv-np1"; uv pip install -r requirements-np1.txt
uv venv --python 3.12 .venv-cad  ; $env:VIRTUAL_ENV="$PWD\.venv-cad"; uv pip install -r requirements-cad.txt
```

| env         | packages                                                        | used for                              |
|-------------|-----------------------------------------------------------------|---------------------------------------|
| `.venv`     | openmdao, om-pycycle (git), cantera, turbo-design (git), turbodesigner, aerosandbox, scikit-fem, ROSS | cycle, combustion, turbomachinery, drag build-up, rotor dynamics |
| `.venv-np1` | ADRpy, turboflow, CoolProp                                       | airframe constraint sizing, centrifugal/axial meanline design and maps |
| `.venv-cad` | CadQuery 2.8 (OCCT 7.9), gmsh, pyturbo-aero, scikit-fem, meshio, pypardiso, VTK | CAD, meshing, 3D FE, rendering |

`.venv-cad` has no pip; install with `uv pip` as above. Its Python processes exit non-zero at
teardown after finishing (an OCP quirk), so check outputs, not exit codes.

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

## Phase 7 (afterburner; run on the user's instruction, freeze decisions still open)

Report: `docs/phase7_afterburner.md`. The afterburner lives in `cycle_model.py` behind
`afterburner=False`, so with it off the Phase 3/4 model is unchanged — `verify_ab_cycle.py` proves
that and must keep passing before any Phase 7 number is used. Findings:
* **+79 % net thrust** at the dash (500 → 896 N at Tt7 1900 K) for +63 % TSFC;
* the envelope is capped at **M 1.33 by the turbine exit annulus**, not by thrust — the afterburner
  is never thrust-limited up to M 2.0, and the cap is altitude-independent;
* a **fixed nozzle turns +79 % into +9.6 % and halves the surge margin**, so the variable nozzle is
  not optional;
* the **translating plug** wins the nozzle trade on actuation load (123 N vs the iris's 1198 N) and
  is the only concept a sourced actuator covers;
* it costs **+4.08 kg and +484 mm** (the engine more than doubles in length), and TOGW closes at
  24.78 kg **only for brief afterburner use** — 26.02 kg, over the 25 kg limit, if the afterburner
  runs through the whole acceleration.

New open risks R7.1–R7.7; freeze risks 4.1/4.2 and 4.4 are made **worse**, not better.

```powershell
.venv\Scripts\python scripts\phase7_afterburner\verify_ab_cycle.py       # run this first: Rayleigh vs tables,
                                                                         # afterburner-off regression, null-AB identity,
                                                                         # fuel bookkeeping, Cantera heat release, A8, Fg
.venv\Scripts\python scripts\phase7_afterburner\ab_envelope.py --regress # dry deck vs data/phase3r_mission_<tag>_deck.csv (0.000 %)
.venv\Scripts\python scripts\phase7_afterburner\ab_design_point.py       # Tt7 sweep, duct-Mach trade, thermal choking, eta_AB
.venv\Scripts\python scripts\phase7_afterburner\ab_envelope.py           # envelope on real maps (~15 min); --alt-only reuses the 5 km line
.venv\Scripts\python scripts\phase7_afterburner\ab_hardware.py           # turbine exit, diffuser, flameholder, Cantera stability, mass
.venv\Scripts\python scripts\phase7_afterburner\ab_nozzle_trade.py       # iris / two-position / plug + the fixed-nozzle reference
.venv\Scripts\python scripts\phase7_afterburner\ab_closure.py            # mass, fuel and the 25 kg closure matrix
.venv-cad\Scripts\python scripts\phase7_afterburner\ab_cad.py            # CAD on top of the Phase 6 engine (~2 min)
.venv-cad\Scripts\python scripts\phase7_afterburner\ab_render.py         # cutaway and meridional-section figures
```

Run them in that order: `ab_envelope.py` needs `ab_design_point.json`, `ab_nozzle_trade.py` and
`ab_closure.py` need both, and `ab_cad.py` needs all three plus `cad/engine/*.step` from Phase 6.
The two CAD steps run in `.venv-cad` and, like every `.venv-cad` script, can exit non-zero at
teardown — check the outputs, not the exit code.

CAD findings (design_log D7.7, F7.13–F7.15): the afterburner flow path fits inside the 186.6 mm
engine envelope with a 10.2 mm annulus to spare, but **the nozzle actuator fits nowhere** (+25.0 mm
over the envelope, against an 8.7 mm engine-to-skin gap — Phase 6A's F6A.2 repeated, risk R7.8); and
the CAD mass is +0.298 kg over the bottom-up model, which puts TOGW at 25.10 kg, just over the
ceiling, where the recommended duct-Mach-0.30 build would be 23.80 kg.

## Axial option (Phase 3A-R / 4A / 5A / 6A) — see `axial/README.md`

The axial and axial-centrifugal work lives under `axial/`, with its own README, commands, data,
docs, plots and CAD. It is **not** the baseline; which engine goes forward is still an open
decision of `docs/design_freeze.md`.

The 6-stage pure axial (OPR 5, 80 000 rpm, tag `ax80000_opr5_t1150_n6_cap_3r`) was taken to its own
freeze, `axial/docs/design_freeze_axial.md`: engine 6.86 kg / 599 mm / 142.5 mm with VIGV + bleed +
variable nozzle; dash margin +103 / +88 %; idle 77.5 % speed (idle thrust 5-6 × approach drag, so an
engine-off descent is needed); TOGW 22.1 kg (powered descent) or 18.5 kg (engine-off descent). Every
compressor result depends on the unvalidated stage-stacking model (R4.1). Phase 6A added exploratory
packaging CAD and risks R6A.1-R6A.6 (`axial/docs/phase6a_axial_cad.md`).

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

## Phase 4 on the early axial engine, and the option-B checks — see `axial/README.md`

Phase 3's blockage erratum (`docs/phase3_engine.md` section 14), the axial low-speed operability
study, the axial rotor dynamics and the axial-centrifugal option-B checks moved to `axial/`:
reports `axial/docs/phase4_operability.md`, `axial/docs/phase4_rotordynamics.md` and
`axial/docs/phase4_optionB_checks.md`, commands in `axial/README.md`.

Two pieces of that work stayed here because both architectures rely on them:

```powershell
.venv\Scripts\python scripts\phase4_turbomachinery\rotordynamics_verify.py   # ROSS verified vs closed forms (both architectures)
.venv\Scripts\python scripts\phase4_turbomachinery\cc_benchmark.py           # full operability chain on the JetCat P400 model (idles at 31 %)
```
