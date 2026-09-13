# Design log — 500 N turbojet + <=25 kg airframe

Running record of every non-trivial decision: tool used, inputs, outputs, and why the
chosen option beat the alternatives. Newest entries at the bottom. IDs: `Dx.y` = decision,
`Ax.y` = assumption, `Fx.y` = finding, where x = phase.

---

## Phase 0 — Setup and tool survey (2026-09-13)

### A0.1 Reference condition for the 500 N thrust target (working assumption, not yet confirmed)
- **Assumed:** 500 N is **uninstalled net thrust at sea-level static (SLS), ISA (288.15 K,
  101.325 kPa), maximum continuous rating**, Jet-A / kerosene fuel.
- **Why this default:** it is the rating convention on every commercial micro-turbojet data
  sheet, so it is the only definition against which a statistical engine-mass database
  (needed for the 25 kg closure) can be built. Phase 1 will state the flight-condition
  thrust requirement separately from this rating.
- **Status:** flagged for the user; not load-bearing until Phase 1.

### D0.1 Python 3.12, not the machine default 3.14
- **Evidence:** Cantera 3.2.0 wheel metadata `requires_python <3.15,>=3.10`; turboflow
  `<4.0,>=3.11`; OpenMDAO/CoolProp untested on 3.14. 3.12.10 already present on the machine.
- **Result:** every candidate installed on 3.12.

### D0.2 Two virtual environments (`.venv` NumPy 2.5, `.venv-np1` NumPy 1.26)
- **Tool:** `uv pip install --dry-run`; import and functional tests.
- **Evidence:** `openmdao 3.45.1` needs `numpy>=2`; `turbodesigner 2.0.0` needs `numpy>=2.4.3`;
  `turboflow 0.1.18` needs `numpy<2`; `ADRpy 0.2.6` fails under NumPy 2 in `twrequired_to`
  (line 1505) and `liftslope_prad` (line 726). A one-line ADRpy patch was tried and exposed
  the second failure; the same ADRpy smoke test passes unmodified under NumPy 1.26.4.
- **Alternatives rejected:** patch ADRpy piecemeal (unbounded); downgrade the whole stack
  to NumPy 1 (breaks OpenMDAO). Tools in the two envs exchange only tabulated data.

### D0.3 pyCycle installed from GitHub, not PyPI
- **Finding F0.1:** PyPI `pycycle 0.0.8` is an unrelated circular-import detector
  (contents: `cli.py`, `utils.py`). Removed.
- **Installed:** `om-pycycle 4.4.1.dev0` @ `ee7e161` (2026-05-20, includes NumPy-2 thermo fix).
- **Verification (`scripts/phase0_tools/smoke_pycycle.py`):** single-spool turbojet, SLS,
  Fn target 11800 lbf, T4 2370 R, PR 13.5: Newton converged in 4 iterations; Fn 11800.0 lbf,
  W 147.33 lbm/s, TSFC 0.7985 lbm/hr/lbf; two off-design points at Fn 11000 lbf converged
  (Nmech 7944 rpm). Off-design capability confirmed, which is the reason to use pyCycle
  over a hand-written ideal-cycle script.

### D0.4 Cantera adopted as thermo cross-check and combustor-limit tool (not as the cycle solver)
- **Finding F0.2:** pyCycle already carries a CEA Gibbs-minimisation thermo (JP-7 default;
  Jet-A tabular). So Cantera's role is independent verification and combustor chemistry,
  not a replacement for pyCycle's gas model.
- **Verification (`smoke_cantera.py`):** n-dodecane surrogate, phi 0.30, T3 470 K, P3 4 bar:
  T_ad 1230.9 K, gamma 1.3065, cp 1231.7 J/kg-K. ISA air gamma 1.4015. Plausible for a
  micro-turbojet combustor (T4 in the 1100-1250 K range on published KJ66/JetCat data).

### D0.5 turbo-design (NASA) installed from GitHub main, pinned, adopted as Phase 4 primary
- **Finding F0.3:** PyPI `turbo-design 1.4.2` (2026-03) has stray `from turtle import down/up`
  lines (`turbine_spool.py:6`, `compressor_spool.py:3`) that require tkinter, absent on this
  Python build. GitHub main `1.4.3 @ 23c2b0b` has the lines removed and adds a dedicated
  `turbodesign.centrifugal` package, `operating_map`, and `shaft_match`.
- **Verification (`smoke_turbodesign.py`, upstream HECC fixture, sourced geometry, no tuning):**

  | quantity | model | NASA measured | error |
  |---|---|---|---|
  | work factor psi | 0.8127 | 0.8100 | +0.3 % |
  | stage PR_tt | 4.7805 | 4.6847 | +2.0 % |
  | stage eta_poly | 0.8540 | 0.8553 | -0.2 % |
  | choke mass flow | ~5.60 kg/s | 5.24 kg/s | +7 % |

  Plot: `plots/phase0_turbodesign_hecc_validation.png`. These error bands are carried
  forward as the uncertainty on any Phase 4 compressor number from this tool.
- **Why over TurboFlow as primary:** NASA-maintained, validated against a NASA test case
  with published geometry, handles both the centrifugal compressor and the axial turbine
  and shaft matching in one framework, Cantera gas model. TurboFlow is kept as the
  independent cross-check (different loss correlations: Oh / Zhang) and for its
  axial-turbine design optimiser.

### D0.6 TurboFlow adopted as Phase 4 secondary (cross-check, turbine design optimisation, maps)
- **Verification (`smoke_turboflow.py`, upstream example):** centrifugal compressor
  0.45 kg/s, 52 krpm, 143 mm impeller, Oh losses: converged 3.4 s, eta_tt 83.8 %, PR_tt 2.664.
  Axial-turbine design optimisation example: converged 99 s, eta_ts 90.8 %, PR_ts 2.298,
  geometry returned. Example machine is within a factor of ~2 of the expected 500 N scale.

### D0.7 Tools rejected or held
- **pyAircraftEngineFramework: rejected.** GitHub only (0 stars, one author, non-commercial
  Prosperity licence). On-design only: single `calculate(h, Ma)` method, fixed
  efficiencies, no maps, no deck export, no airframe coupling. Adds nothing over pyCycle.
- **TurboMAP: does not exist** as a Python turbomachinery package (PyPI and GitHub searched).
- **pyturbo-aero (NASA PyTurbo): held for Phase 6.** Geometry generator (`Centrif`,
  `Airfoil3D`), no performance model. PyPI `pyturbo` is an unrelated 2018 TensorFlow bundle.
- **turbodesigner (OpenOrion): held.** Axial compressor only; efficiency is an *input*.
  Runs at micro scale (0.9 kg/s, PR 3, 70 krpm: mean radius 58.7 mm, inlet Mach 0.45).
  Only relevant if an axial-compressor architecture survives the Phase 3 trade.

### D0.8 Gap-filling methods committed to (details in `tools_survey.md` section 3)
- Centrifugal compressor map for pyCycle off-design: generated in Phase 4 from
  turbo-design / TurboFlow speed lines, converted to pyCycle `MapData`. Placeholder scaled
  `AXI5` map in Phase 3 first pass, flagged as such.
- Engine mass: bottom-up geometry-based estimate plus a cited statistical micro-turbojet
  database; both reported.
- Airframe mass fractions: cited small-UAV weight-fraction data (Raymer, Gundlach).
- Engine deck to mission coupling: own script around pyCycle off-design output.

### F0.4 Early feasibility signal (placeholder inputs; to be redone properly in Phase 2)
ADRpy smoke run with generic small-jet aerodynamics gave required T/W of 0.3-0.6 across
W/S 150-800 Pa, versus T/W = 2.04 for 500 N on 25 kg. The mission definition in Phase 1
must justify roughly 3-6x more installed thrust than a conventional small jet UAV needs,
or the thrust rating vs sizing point must be reconciled. Carried into Phase 1 as the one
possible clarifying question.

---

## Phase 1 — Requirements and mission definition (2026-09-13)

User input resolving F0.4: RC-scale student project; the aircraft must reach and hold
Mach 1 for 7 s (that is why the thrust is high), take off from the ground from standstill,
land, and repeat the sortie once the same day. Airframe drag not yet computed by the user.
Full write-up: `docs/phase1_requirements.md`.

### F1.1 A 500 N *SLS-rated* engine gives only ~310-325 N at Mach 1 below 5 km
- **Tool:** pyCycle, `scripts/phase1_requirements/prelim_thrust_lapse.py` (placeholder
  cycle OPR 4 / T4 1150 K / eta_c 0.78 / eta_t 0.85, scaled NPSS maps; continuation sweep,
  residual-norm convergence check; both RPM-limited and T4-limited max throttle, lower taken).
- **Numbers:** M1 thrust 309 N (0 km), 325 N (1-5 km), 272 N (8 km), 226 N (10 km). RPM
  limit binds everywhere below 8 km; holding T4max at M1 / 0 km would need 104.7 % N.
- **Mechanism:** inlet total temperature 1.2x ambient at M1 -> corrected speed -9.5 % at
  fixed mechanical speed.

### F1.2 Drag-area budget grows with altitude; sea-level Mach 1 is not credible
- Allowable CD*S = Fn/q at M1: 44 cm2 (0 km), 52 (1 km), 66 (3 km), 86 (5 km), 122 (10 km)
  for the SLS-rated engine. A faired 150 mm-diameter body alone is ~35-55 cm2 at M ~ 1
  (Hoerner ch. 16-17). Hence D1.1 and D1.2.

### D1.1 "500 N" is defined at the Mach 1 dash point, not at SLS
- **Tool:** pyCycle, `prelim_design_point_options.py`, like-for-like cycle designs at SLS,
  M1/0 km, M1/3 km, M1/6 km, each re-run at the other points in both limit modes.
- **Numbers:** design at M1 / 5 km for 500 N -> airflow 1.120 kg/s (vs 0.865 for the SLS
  design), SLS thrust 665 N (RPM-limited), M1 thrust 551 / 523 / 500 N at 1 / 3 / 5 km.
- **Why:** the user's thrust is for drag at Mach 1; definition A leaves 65 % of the rating
  at the mission point. Cost: ~30 % more airflow -> engine mass, to be absorbed in Phase 2/4.
- Supersedes A0.1.

### D1.2 Mission profile: Mach 1 dash at 5 km ISA (candidate C of four)
- **Tool:** point-mass energy integration, `prelim_mission_energy.py`, on the D1.1 engine
  table; drag parameterised as 75 % of the thrust-limited CD*S with drag-rise factor 2
  (A1.2, A1.3), sensitivity over 0.6-0.9 and 1.5-3.0.
- **Numbers (1 / 3 / 5 / 10 km):** CD*S budget 88 / 107 / 132 / 156 cm2; q 62.9 / 49.1 /
  37.8 / 18.5 kPa; time to M1 18 / 24 / 31 / 61 s; sortie 60 / 166 / 273 / 553 s; fuel
  incl. reserve 0.82 / 1.10 / 1.40 / 2.09 kg; P3 at dash 558 / 475 / 401 / 216 kPa;
  compressor-inlet Re index 1.36 / 1.12 / 0.92 / 0.53.
- **Why 5 km:** fuel is never the discriminator (<10 % MTOW everywhere). 5 km gives the
  largest drag budget (132 cm2) and the lowest structural q (38 kPa) that still keeps the
  engine out of the low-P3 / low-Re regime of 10 km, with a sortie under 5 min. 3 km is
  the documented fallback (107 cm2) if a lower ceiling is imposed; the same engine covers it.

### A1.x assumptions registered (see `docs/phase1_requirements.md` section 5)
ISA day (A1.1); 25 % acceleration margin at the dash (A1.2); drag-rise 2.0 (A1.3); idle
fuel 10 % (A1.4); 2 min reserve (A1.5); life >= 10 hot cycles / 1 h (A1.6); paved 300 m
sea-level runway (A1.7); kerosene fuel (A1.8); refuel between sorties (A1.9); ground roll
deferred to Phase 2 (A1.10). Non-engineering prerequisite noted: airspace authorization
and telemetry/autopilot for a Mach 1 uncrewed flight at 5 km.

### Derived requirements handed forward
E1-E7 (engine) and A1-A5 (airframe) in `docs/phase1_requirements.md` section 4. The
single hardest one: **airframe CD*S <= 132 cm2 (target 99 cm2) at M 1.0 / 5 km**, to be
demonstrated in Phase 2 with a cited transonic drag build-up, because no surveyed tool
does transonic drag.
