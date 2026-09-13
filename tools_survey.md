# Phase 0 — Tool survey (2026-09-13)

Platform: Windows 11, Python 3.12.10 (uv-managed venvs). The machine default is Python
3.14.3; it was **not** used because Cantera's wheel metadata caps at `<3.15` and several
candidates (OpenMDAO, CoolProp, turboflow `<4.0,>=3.11`) have no proven 3.14 support.
3.12 was the newest interpreter with wheels for every candidate. The 3.12 build on this
machine has no `tkinter`, which surfaced one packaging bug (see turbo-design).

Every status below is from an actual install + import + functional run in this session.
Smoke-test scripts: `scripts/phase0_tools/smoke_*.py`. Frozen envs: `requirements-np2.txt`,
`requirements-np1.txt`.

## 1. Summary table

| Candidate (brief name) | What it actually is | Install | Functional check | Verdict / role |
|---|---|---|---|---|
| **NASA pyCycle** | `om-pycycle` 4.4.1.dev0 from `git+https://github.com/OpenMDAO/pyCycle` @ ee7e161 (2026-05-20). **The PyPI package `pycycle` 0.0.8 is an unrelated circular-import linter** (installed, identified, removed). | OK (git) | Single-spool turbojet example: design point converged (Fn 11800 lbf target met, TSFC 0.7985, W 147.3 lbm/s, OPR 13.5) plus 2 off-design points (Fn 11000 lbf, Nmech 7944 rpm). Upstream example's print viewer crashes under NumPy 2 (`only 0-dimensional arrays...`); the solver is unaffected. | **ADOPT: Phase 3 cycle tool.** Has built-in CEA chemical-equilibrium thermo (JP-7 default, Jet-A tabular option), so real-gas combustion products are native rather than an ideal-gas assumption. |
| **Cantera** | 3.2.0 (PyPI wheel) | OK | `nDodecane_Reitz.yaml` (100 species) kerosene surrogate: phi=0.30 at T3=470 K, P3=4 bar gives T_ad 1230.9 K, gamma_products 1.3065, cp 1231.7 J/kg-K. ISA air cp 1001.8, gamma 1.4015. | **ADOPT: Phase 3.** Independent check of pyCycle's CEA thermo (T4, gamma, cp at turbine entry), flame-temperature / lean-limit envelope for combustor sizing, real-gas properties for turbomachinery hand checks. |
| **ADRpy** | 0.2.6 (PyPI, last release and commit 2024-01-26; upstream dormant, single tag) | OK only under NumPy 1.26 | Under NumPy 2: fails in `twrequired_to` and `liftslope_prad` (1-element array to scalar). Under NumPy 1.26 (`.venv-np1`): full jet (bpr=0) constraint diagram runs, 5 constraints x 14 wing loadings. | **ADOPT: Phase 2**, in the NumPy-1 env. Has `JetDeck` and a bpr/throttle-ratio thrust-lapse model appropriate to a turbojet. No mass-breakdown tool inside ADRpy, so the mass budget is a scripted statistical/parametric estimate (see gaps). |
| **pyAircraftEngineFramework** | `rmalpica/pyAircraftEngineFramework` (GitHub only, 0 stars, created 2026-01, Prosperity Public License = non-commercial). 176-line `TurbojetEngine.calculate(h, Ma)`: fixed component efficiencies, NASA-7 polynomials, on-design only. | cloned, inspected | No component maps, no off-design, no engine-deck export, no airframe coupling (grep for map/deck/airframe/mission: nothing). | **REJECT.** Duplicates pyCycle at lower fidelity and provides none of the engine-deck-to-airframe coupling implied by the brief. Coupling will be our own script: pyCycle off-design deck (thrust, SFC vs Mach/alt/throttle) feeding the ADRpy/mission script. |
| **TurboMAP** | Not found. PyPI: no package. GitHub: only unrelated hits (ORB-SLAM mapping, a C# object mapper, a 3-star C# "TurboMapCalculator" from 2021). | n/a | n/a | **NOT AVAILABLE.** Compressor-map generation is covered by TurboFlow / turbo-design (below), converted into pyCycle `MapData` format by a script we write. |
| **NASA PyTurbo** | = `pyturbo-aero` 1.3.8 (PyPI; GitHub `nasa/pyturbo-aero`, 91 stars, pushed 2026-09-01). **PyPI `pyturbo` 18.7.27 is an unrelated 2018 TensorFlow/OpenCV bundle**, not installed. | OK | Imports; `pyturbo.aero.Centrif` (centrifugal impeller + splitter builder), `Airfoil2D/3D`, `passage2D`. Geometry generation only, no performance prediction. | **HOLD for Phase 6** (3D blade/passage geometry after freeze). Not used for sizing. |
| **NASA Turbo-Design** | = `turbo-design` (GitHub `nasa/turbo-design`, 94 stars, pushed 2026-09-01). PyPI 1.4.2 (2026-03) is stale: stray `from turtle import ...` lines give `ModuleNotFoundError: tkinter`. Installed **GitHub main, v1.4.3 @ 23c2b0b** instead: bug gone, adds `turbodesign.centrifugal` (inducer/impeller/vaneless/vaned diffuser, Oh loss set, Wiesner slip), `operating_map`, `shaft_match`. | OK (git) | Ran the upstream NASA HECC validation fixture (NASA/CR-2014-218114 geometry, no tuned coefficients): work factor 0.8127 vs 0.8100 measured (+0.3 %), PR_tt 4.7805 vs 4.6847 (+2.0 %), eta_poly 0.8540 vs 0.8553 (-0.2 %). Speed line: `plots/phase0_turbodesign_hecc_validation.png`. Upstream states its own limits: choke flow 7-11 % high, vaned-diffuser diffusion factor outside correlation range, constant cp inside the solve. | **ADOPT: Phase 4 primary** for centrifugal compressor and axial turbine meanline (radial-equilibrium streamline solver; Ainley-Mathieson / Kacker-Okapuu / Craig-Cox turbine losses, Lieblein/OTAC compressor losses; Cantera-backed gas). |
| **TurboFlow** | `turboflow` 0.1.18 (PyPI; GitHub `turbo-sim/TurboFlow`, 56 stars, MIT, pushed 2026-05). Pins `numpy<2`, uses CoolProp. | OK, NumPy-1 env only | Centrifugal example (0.45 kg/s, 52 krpm, 143 mm impeller, Oh losses): converged in 3.4 s, eta_tt 83.8 %, PR_tt 2.664. Axial-turbine **design optimisation** (SLSQP; specific speed and blade-jet ratio as variables): converged in 99 s, eta_ts 90.8 %, PR_ts 2.298, full geometry returned. Performance-map mode exists for both machines. | **ADOPT: Phase 4 secondary**: (a) independent cross-check of turbo-design compressor numbers with a different loss set (Oh / Zhang), (b) axial-turbine design optimisation, (c) speed-line map generation for pyCycle off-design. Its example machine is close to our scale. |
| **TurboDesigner** | `turbodesigner` 2.0.0 (PyPI; GitHub `OpenOrion/turbodesigner`, 220 stars, MIT, pushed 2026-06). | OK | 2-stage axial compressor at 0.9 kg/s, PR 3, 70 krpm: runs, mean radius 58.7 mm, inlet Mach 0.45, stage PR 1.82 / 1.65. **Takes isentropic efficiency as an input**: free-vortex velocity triangles + Johnsen-Bullock metal angles + CadQuery STEP export, no loss model. Axial compressors only. | **HOLD**: geometry/CAD generator for an *axial* compressor option only. Used in Phase 3/4 only if the axial-compressor architecture survives the trade; otherwise Phase 6. Not a performance predictor. |
| numpy / scipy / matplotlib / pandas | 2.5.3 / 1.18.1 / 3.11 / 3.0.5 (main); 1.26.4 / 1.17.1 / 3.11 / 2.3.3 (np1) | OK | n/a | free use |

## 2. Environment decision: two venvs

`openmdao 3.45.1` requires `numpy>=2`; `turbodesigner 2.0.0` requires `numpy>=2.4.3`;
`turboflow` requires `numpy<2`; `ADRpy 0.2.6` breaks under NumPy 2 in at least two
independent code paths (take-off T/W and lift slope). Patching ADRpy line by line was
tried (the first fix exposed a second failure) and abandoned as unbounded. Isolating the
two NumPy-1 tools in `.venv-np1` costs nothing: the Phase 2 (ADRpy) and Phase 4
cross-check (TurboFlow) steps exchange only tabulated numbers (CSV/JSON) with the cycle model.

| env | packages | phases |
|---|---|---|
| `.venv` (NumPy 2.5) | openmdao, om-pycycle (git), cantera, turbo-design (git), turbodesigner, pyturbo-aero | 3, 4, 6 |
| `.venv-np1` (NumPy 1.26) | ADRpy, turboflow, CoolProp | 2, 4 (cross-check) |

## 3. Gaps and fallback plans

| Gap | Why it matters | Plan |
|---|---|---|
| **No centrifugal compressor map ships with pyCycle.** Built-in maps are NPSS large-engine maps: `AXI5` (axial, PR 5.2), `HPCMap` (E3-class, PR 10.9), `LPCMap`, `FanMap`, `NCP01` (a *fan*-scale map, Wc 1100-2100 lbm/s). None is a small centrifugal characteristic. | Off-design (Phase 3) needs a map whose shape (surge line, choke, efficiency islands) matches a small backswept centrifugal stage. | Phase 4 generates a speed-line map with turbo-design `operating_map` and/or TurboFlow performance-map mode; a converter script writes it into pyCycle `MapData` (Nc, R-line, Wc, PR, eta arrays). Until then, Phase 3 on-design and first-pass off-design use pyCycle's scaled `AXI5` / `HPT1269` maps, explicitly flagged as placeholders. |
| **No tool estimates engine mass or envelope.** | Engine mass is the largest single driver of the 25 kg closure. | Two independent estimates, both logged: (1) bottom-up from Phase 4 geometry (impeller, diffuser, turbine disc, shaft, combustor liner, casing volumes x material densities, plus bearings/starter/ECU/fuel pump from vendor data sheets); (2) statistical fit of thrust vs mass and diameter for commercial micro-turbojets in the 100-1000 N class, compiled from published data sheets into `data/microturbojet_database.csv` with a source per row. Any discrepancy between (1) and (2) is reported, not averaged away. |
| **No airframe mass-breakdown tool** (ADRpy has none). | Phase 2 mass budget. | Scripted parametric breakdown for small jet UAVs (structure fraction, systems, fuel, payload) using published small-UAV weight-fraction data (Raymer Ch. 3; Gundlach, *Designing Unmanned Aircraft Systems*), cited in the log, with fuel mass from pyCycle SFC x mission integration. Sensitivities reported. |
| **Engine deck to airframe coupling** (pyAircraftEngineFramework rejected). | Mission fuel and thrust lapse across the Phase 1 profile. | Own script: pyCycle off-design runs on a (Mach, altitude, throttle) grid -> `data/engine_deck.csv` -> mission integrator feeding ADRpy weight fractions. |
| **ADRpy dormant since 2024-01.** | Risk of further NumPy/SciPy breakage. | Pinned in `requirements-np1.txt`; the constraint equations are simple enough that a from-scratch reimplementation (Raymer / Gudmundsson forms) is the fallback if it breaks. |
| **turbo-design is pre-release and under active development** (GitHub main pinned to commit 23c2b0b; PyPI stale). Upstream lists unresolved choke-flow and diffuser-loss limitations. | Phase 4 compressor numbers. | Pinned commit; every result cross-checked against TurboFlow (independent loss models) and read against the HECC validation error band (eta +-0.5 pt, PR +-2 %, choke +7-11 %). Choke margin will be taken from TurboFlow as well before trusting either. |
| **pyCycle example code is NumPy-2-fragile** (viewer/print helpers). | Cosmetic. | Our scripts read outputs with `prob.get_val()` and index `[0]`; `OPENMDAO_REPORTS=0`. |

## 4. Preliminary observation to carry into Phase 1

From the ADRpy smoke run (placeholder inputs, not a result): with generic small-jet
aerodynamics (AR 6, CDmin 0.030, 60 m ground run, 1500 fpm climb, 150 kt cruise at 1 km,
2 g turn) the constraint diagram asks for T/W of about 0.3-0.6 over W/S 150-800 Pa,
while 500 N on 25 kg is T/W = 2.04. Either the mission is far more demanding
(high-subsonic dash, steep climb, high altitude, very short launch) or the 500 N reference
point is not the rating at which the 25 kg airframe is sized. This is the load-bearing
question for Phase 1 and is flagged there rather than resolved here.

## 5. Phase 2 additions (2026-09-13)

| Tool | Status | Role |
|---|---|---|
| **AeroSandbox** 4.2.10 (`.venv`, PyPI, MIT) | installed; `approximate_CD_wave`, `critical_mach`, `fuselage_base_drag_coefficient`, `sears_haack_drag_from_volume` verified or traced to cited sources | cited transonic helper models inside our drag build-up. `sears_haack_drag(radius, length)` returns CD on frontal area although documented as drag area (39x off in the test): not used. |
| **ADRpy** 0.2.6 | two more defects found in use: default quarter-chord sweep has an operator-precedence bug (`constraintanalysis.py:392`, lift slope 1.23 instead of 2.87/rad for our wing); the sustained-turn constraint uses the climb weight fraction | both worked around (explicit `sweep_25_deg`, one concept object per constraint); results cross-checked against DATCOM and our own mission model (dash drag 361.1 vs 361.3 N) |
| own slender-body wave-drag integral (`scripts/phase2_airframe/aero_utils.py`) | verified: Sears-Haack ratio 1.0007, parabolic-area body 0.9607 = exact analytic | shaping comparisons of the area distribution |
