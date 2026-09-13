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

---

## Phase 2 — Constraint sizing, drag, mass budget (2026-09-13)

Full write-up: `docs/phase2_airframe.md`. All outputs regenerate with
`python scripts/phase2_airframe/run_phase2.py`.

### F2.0 External requirement: the Boom Prize (https://boomsupersonic.com/prize, read 2026-09-13)
The brief's mission (25 kg incl. fuel, Mach 1 held, two flights in one day, land) matches
the Boom Prize rules. Additional rules adopted as requirements: Mach 0.8 -> >1 level or
climbing with no altitude loss; >= 5 s continuous above Mach 1 by true airspeed;
reciprocal headings; wheeled OR belly landing, reflyable; human pilot with instant abort;
calibrated pitot-static + TAT + sealed loggers + GPS. No altitude limit is stated, so D1.2
stands. Eligibility on the page: US citizens / permanent residents, amateur teams.

### D2.0 Tools for Phase 2
- ADRpy (NumPy-1 env) for the constraint equations; bugs found: default quarter-chord sweep
  operator precedence (`constraintanalysis.py:392`, lift slope 1.23 vs 2.87/rad), turn uses
  climb weight fraction. Worked around, documented.
- AeroSandbox 4.2.10 added (verified helpers only); radius-form Sears-Haack function returns
  CD on frontal area despite docstring (39x off) -> not used.
- Own slender-body wave-drag integral, verified to 0.07 % (Sears-Haack) and exactly against
  an analytic parabolic-area body (0.9607).
- No surveyed tool does transonic drag -> Raymer build-up + area-rule wave drag, with the
  E_WD uncertainty carried as a 1.8 / 3.0 bracket.

### D2.1 Drag design point M 1.02 at 5 km
Holding M >= 1.00 for 5+ s with +-0.02 air-data uncertainty. The drag-rise fairing gives
0.49 (M 1.00) vs 0.71 (M 1.02) of the fully developed wave drag, so this is not a free
margin: dash drag at 1.02 is 16 % above M 1.00 (83.1 vs 71.8 cm2).

### D2.2-D2.6 Configuration shaping (numbers at S 0.30 m2, M 1.02 / 5 km)
- C1: body of revolution, sharp-lip nose pitot inlet, AR 3, taper 0.2, 5 % section,
  all-moving HT + fin (Raymer tail volume 0.40 / 0.07).
- Forebody 30 -> 40 % and LE sweep 45 -> 55 deg: 91 -> 73 cm2 (150 mm placeholder engine).
- D2.3 engine envelope from 26-engine database at 665 N SLS: 6.83 kg, 188 mm, 453 mm ->
  body 218 mm -> 97.5 cm2 at 2.4 m. D2.4 length 2.7 m, forebody 45 %: 91.6 cm2.
- D2.6 aft closure 22 -> 28 % + half-wing-area waist: 83.1 cm2 nominal, 100.5 cm2 at
  E_WD 3.0. A waist alone did nothing nominally (geometric E_WD 1.97 -> 2.84).
- Rejected: 60 deg sweep (-2 cm2 only, worse low-speed lift); 3.0 m body (-4 cm2 for
  +0.17 m2 wetted area and mass).

### D2.5 Landing: plain flaps + 0.6 m drag chute, wheeled
Constraint diagram: dash needs S <= 0.383 m2 (25 % margin, nominal, 25 kg); a 300 m runway
without a chute needs S >= 0.44 m2 (flaps) -> no overlap. At S 0.30 m2: flaps only 396 m,
flaps + chute 209 m, no-flap + chute 235 m (mu_brake 0.3). Chute +0.20 kg. Fallbacks:
>= 500 m runway (flaps, no chute) or belly landing (prize-legal).

### D2.7 Wing area S = 0.30 m2
S range 0.24-0.38 m2 from the dash margin. 0.30 m2: dash throttle 0.67 nominal / 0.81 at
E_WD 3 (50 % / 24 % margin), V_LOF 47 m/s at TOGW, landing 209 m with chute. 0.35 m2 drops
the pessimistic margin to 17 %; 0.25 m2 raises V_LOF to 51 m/s.

### D2.8 Mass budget closes: TOGW 18.7 kg (margin 6.3 kg); 21.4 kg (margin 3.6 kg) high-engine case
Engine 6.83 + accessories 1.60 + structure 3.84 + gear/chute 1.27 + fuel system 0.40 +
systems/instrumentation 2.02 + growth 1.13 + fuel 1.58. RC-jet statistics give 6.7 kg for
airframe + systems vs 7.5 kg bottom-up (8.7 with growth): the bottom-up value is used.

### F2.4 Mission with the drag polar (S 0.30 m2, 18.7 kg)
Brake release to M 1.02 at 5 km in 26 s; transonic pinch minimum excess thrust 167 N
nominal / 99 N pessimistic (level flight, prize-compliant); M 1.02 hold needs 328 / 396 N
of 492 N installed; sortie fuel 1.29 + 0.24 reserve (+3 % unusable) = 1.58 kg.

### F2.5 Engine diameter is a first-order airframe driver
+10 mm engine diameter -> +5.5 / +8 cm2 dash drag area (+20-30 N). 150 mm engine: -23 % /
-29 % dash drag. Carried into the Phase 3 architecture trade (centrifugal vs axial).

### F2.6 Flutter screening passes
NACA TN 4197 closed form: minimum V_f / V = 2.5 (wing) with 2+2 ply carbon skins; tails
3.6-5.9. Screening only; modal analysis in Phase 4/5.

### Process note
The background data-collection agent wrote an early 8-row engine table and a fit script
(12:43) before replacing the table with the final 26-engine version; the orphaned script
read the old columns and was rewritten (`engine_database_fit.py`). No committed file was
affected.

---

## Phase 3 — Engine cycle and architecture trade (2026-09-13)

Full write-up: `docs/phase3_engine.md`. User instruction: do not carry the Phase 2 catalog-fit
engine (6.83 kg / 188 mm); derive mass and diameter from a designed geometry. Done: no Phase 3
number uses the catalog fit.

### F3.1 Tool findings (ground rule 3)
- NASA turbo-design cannot predict axial-compressor efficiency: `loss/compressor/lieblein.py` is
  empty, OTAC classes are zero-returning placeholders, `DiffusionLoss` is an ad-hoc ramp.
- TurboDesigner: efficiency is an input; its rotor diffusion factor uses absolute velocities
  (0.03 vs 0.40 for the matched stator) -> recomputed; last stator `next_flow_station` asserts.
- TurboFlow turbine design optimisation: ignores the operating-point omega (85 000 rpm requested,
  104 000 returned) -> omega equality constraint added; has no structural constraint (optimum had a
  688 m/s tip, ~716 MPa blade-root stress) -> 350 MPa blade-root limit added as a tip-radius constraint.
- TurboFlow and the Howell model both predict component efficiencies far above what fielded
  engines achieve (next entry) -> two technology levels carried.
- Next-best method for the axial compressor: Howell cascade method (Saravanamuttoo ch. 5) + Re,
  tip-clearance and shock penalties on TurboDesigner triangles; verified at 0.90-0.92 row
  efficiency for conventional-scale cases.

### F3.2 Real-gas and calibration anchors
- Cantera vs pyCycle at the combustor exit: T4 -3.3 K (0.3 %), gamma +0.0002, cp +0.6 %.
- Vendor (W, PR, Fn, Wf) sets are inconsistent with vendor EGT limits (need T4 1330-1450 K) ->
  published airflows treated as nominal. Vendor SLS TSFC 0.145-0.167 kg/(N h) requires
  eta_c ~0.66-0.70, eta_t ~0.70-0.75. Phase 1 placeholder gave 0.110 (40 % optimistic).
- Fielded level adopted: eta_c 0.70 (centrifugal), eta_t 0.75, eta_b 0.95 (A3.1).

### D3.1 Dash design-point cycle
Fn 500 N at M 1.02 / 5 km, T4 1150 K (D1.1), convergent nozzle; intake inside the cycle:
normal shock 0.99998 + 1.32 m duct 3.3-3.4 % Pt loss (replaces A2.3). Burner dP/P 0.05, eta_b 0.95.

### F3.3 The combustor sets the diameter; pressure ratio shrinks it
Lefebvre theta scaling from 7 reference engines (theta_ref 7.24e7, log-sigma 0.20): at OPR 4 the
combustor OD is 163-170 mm, at OPR 5 136-143 mm, at OPR 6 117-125 mm. The architecture decides
how much pressure ratio is affordable within rotor stress limits.

### D3.2 Convergent nozzle kept
C-D nozzle gains 2 % (tool) / 0.2 % (fielded) thrust at NPR 2.8-3.7: not worth its mass.

### Architecture trade — both options side by side (dash, Fn 500 N, T4 1150 K)

Engine mass = bottom-up geometry/materials model x 1.24 validation factor (F3.6).

| | Centrifugal, 1 stage, OPR 4, 85 000 rpm | Axial, 5 stages, OPR 5, 65 000 rpm (turbine inside casing) |
|---|---|---|
| compressor tool used | TurboFlow (Oh losses) | TurboDesigner geometry + Howell loss model |
| stage count | 1 compressor stage + 1 turbine stage | 5 compressor stages (253 blades) + 1 turbine stage |
| compressor efficiency, tool / fielded | 0.794 / 0.70 | 0.841 / 0.741 |
| turbine efficiency, tool / fielded | 0.935 / 0.75 | 0.925 / 0.75 |
| airflow, tool / fielded | 1.084 / 1.326 kg/s | 1.052 / 1.293 kg/s |
| **outer diameter, tool / fielded** | **163 / 175 mm** | **136 / 151 mm** |
| diameter set by | combustor / compressor diffuser | combustor + turbine / turbine + compressor |
| length (calibrated), tool / fielded | 444 / 474 mm | 615 / 663 mm |
| **engine dry mass, calibrated, tool / fielded** | **5.52 / 6.57 kg** (fielded range 6.15-6.94) | **5.96 / 7.28 kg** (fielded range 6.81-7.69) |
| dash drag nominal / pessimistic (fielded) | 296 / 348 N | 253 / 282 N |
| **thrust margin nominal / pessimistic, tool** | **+83 % / +60 %** | **+109 % / +97 %** |
| **thrust margin nominal / pessimistic, fielded** | **+69 % / +44 %** | **+98 % / +77 %** |
| 25 % target | holds in all four cases | holds in all four cases |
| worst corner (eta_c 0.66, combustor +1 sigma, E_WD 3) | +32 % | +61 % |
| TOGW (calibrated), fielded | 18.6 kg | 18.9 kg (19.6 at equal compressor efficiency) |
| rotor stress | impeller 464 MPa (tool) -> 526 MPa (fielded) vs 450 allowable | within allowables by construction |
| modelling confidence | chain validated on 2 real centrifugal engines | axial efficiency unvalidated at this scale; operability unquantified |

Also evaluated and rejected: centrifugal 75 000 rpm (fielded pessimistic margin 18 %),
centrifugal OPR 5 (impeller 548 MPa; fielded pessimistic 19 %), axial OPR 4 at 55 000 rpm
(turbine-set 183 mm, 7.7 kg raw fielded), axial OPR 6 uncapped (193 mm, pessimistic 21 %),
axial OPR 6 capped (155 mm, +93 % / +72 %, but 7 stages and 720 mm long).

### F3.4 Centrifugal impeller stress is the conditional in its pass
Same PR at lower efficiency needs more tip speed: 504 -> 537 m/s. If limited to its tool-level
tip speed, fielded PR falls to 3.48, the combustor grows to 190 mm and the pessimistic margin
drops to 24 %.

### F3.5 Transonic acceleration is not binding
Centrifugal fielded deck (placeholder maps): excess thrust +259 % at M 0.70, +150 % at M 0.95;
the minimum is the M 1.02 dash point.

### F3.6 Mass-model validation
JetCat P400-PRO: 3.45 vs 4.01 kg (-14 %), 319 vs 390 mm, 145 vs 148 mm. AMT Nike: 6.98 vs 9.15 kg
(-24 %), 430 vs 524 mm, 203 vs 201 mm. Calibration x1.24 mass (1.16-1.31), x1.22 length.

### D3.3 Recommendation: axial, 5 stages, OPR 5, 65 000 rpm, turbine inside the casing
Why, with numbers: fielded margin +98 % / +77 % vs +69 % / +44 %; worst corner +61 % vs +32 %;
151 vs 175 mm; no stress allowable exceeded (the centrifugal needs its impeller qualified ~17 %
above the conceptual allowable, otherwise 24 % margin); cost +0.71 kg engine, +0.3 kg TOGW.
Against it: +190 mm length, 253 blades down to 10 mm chord, unvalidated efficiency model,
unquantified part-speed stall and start behaviour, no sub-1 kN all-axial precedent.
Fallback: centrifugal OPR 4 / 85 000 rpm if its impeller clears ~530 MPa in Phase 4 FE.
Phase 4 not started, as instructed.

---

## Phase 3b — Axial-centrifugal option, evaluated before Phase 4 (2026-09-13)

User request: evaluate 1-2 axial stages + 1 centrifugal stage with the same tools and the same
stress allowable as the pure centrifugal; state whether it closes the impeller-stress problem
while staying shorter than the 5-stage axial. Write-up: `docs/phase3_engine.md` section 13.

### Method (unchanged from Phase 3)
Axial stages: TurboDesigner + Howell loss model. **The Phase 3 caveat applies unchanged:**
textbook method verified only at conventional scale, not validated at micro scale, with the
fielded debit assumed (A3.4); the front stage is transonic (tip M_rel ~1.30). Centrifugal stage:
TurboFlow with identical settings. Turbine: TurboFlow, stress-limited and envelope-capped.
Combustor: theta-scaled. Mass: bottom-up x 1.24 (P400 / Nike calibration). Impeller allowable:
450 MPa Ti-6Al-4V solid-disc, as for the pure centrifugal. Not modelled: transition-duct loss,
residual swirl at the impeller eye.

### F3b.1 The front axial stage caps the spool speed at ~70 000 rpm
Same limits as the pure axial (tip M_rel <= 1.35, hub/tip >= 0.40): feasible to 70 000 rpm
(M_rel 1.33-1.34), infeasible from 72 000 rpm (1.36). 68 000 rpm used. No feasible front stage at
75 000 or 85 000 rpm in the screening.

### F3b.2 Impeller load and stress by split (screening at 65 000 rpm, W 1.08 kg/s)
| front stages | axial PR | OPR | impeller PR | U2 tool / fielded | Ti stress factor tool / fielded |
|---|---|---|---|---|---|
| 1 | 1.5 | 4.0 | 2.67 | 421 / 452 m/s | 1.39 / 1.20 |
| 1 | 1.5 | 4.5 | 3.00 | 448 / 481 | 1.23 / 1.07 |
| 1 | 1.3-1.5 | 5.0 | 3.85-3.33 | 494-471 / 529-506 | 1.01-1.11 / 0.88-0.96 (fails fielded) |
| 2 | 2.0 | 4.0 | 2.00 | 364 / 393 | 1.86 / 1.60 |
| 2 | 2.0 | 5.0 | 2.50 | 421 / 454 | 1.39 / 1.19 |
| pure centrifugal | - | 4.0 | 4.00 | 504 / 537 (85k) | 0.97 / 0.86 |

### Comparison (fielded level; tool level in `data/phase3_arch_trade_summary.csv`)
| | Centrifugal OPR 4 85k | Axial 5-st OPR 5 65k | AC 1ax OPR 4 68k | AC 1ax OPR 4.5 68k | AC 2ax OPR 4 68k | AC 2ax OPR 5 68k |
|---|---|---|---|---|---|---|
| OD (set by) | 175 (diffuser) | 151 (turbine) | 182 (diffuser) | 195 (diffuser) | 169 (combustor) | 185 (diffuser) |
| length, calibrated | 474 mm | 663 | 641 | 632 | 704 | 680 |
| dry mass, calibrated | 6.57 kg | 7.28 | 8.73 | 9.17 | 8.90 | 9.51 |
| drag nom / pess | 296 / 348 N | 253 / 282 | 312 / 373 | 344 / 422 | 285 / 331 | 320 / 385 |
| margin nom / pess | +69 / +44 % | +98 / +77 % | +60 / +34 % | +45 / **+19 %** | +75 / +51 % | +56 / +30 % |
| worst corner | +32 % | +61 % | +23 % | - | +32 % | +15 % |
| impeller stress factor | 0.86 | - | 1.20 | 1.06 | 1.58 | 1.19 |
| TOGW, calibrated | 18.6 kg | 18.9 | 20.8 | 21.3 | 20.8 | 21.5 |

### D3b.1 Verdict
It closes the impeller-stress problem (every variant >= 1.06 fielded), but it does NOT stay shorter
than the 5-stage axial (632-704 vs 663 mm), it is the heaviest option (+2.2 to +2.9 kg over the pure
centrifugal), and only its 2-axial-stage OPR-4 variant improves on the centrifugal's margin
(+51 % vs +44 % pessimistic; worst corner equal at +32 %). The 1-stage OPR-4.5 and 2-stage OPR-5
variants fail the 25 % pessimistic target. Mechanism: the front stage limits the shaft to
~70 000 rpm, so the impeller, diffuser and turbine disc grow, and the diffuser sets the diameter.
**It relocates the risk (to mass, diameter and the unvalidated axial stages) rather than removing it.**
Recommendation unchanged (pure axial OPR 5). New order of fallbacks: AC 2 axial + cc at OPR 4
(stress-safe, +51 % margin, 8.9 kg), then the pure centrifugal if its impeller is qualified at
~530 MPa (lightest and shortest). Phase 4 not started.

---

## Phase 4 entry gate: impeller stress check, pure centrifugal at 537 m/s (2026-09-13)

User request: a fast, cheap decision gate. Run a detailed stress check of the pure-centrifugal
impeller (OPR 4, 85 000 rpm, fielded U2 537 m/s), covering the blade root and disc burst, and
report the real margin at about 530 MPa. If it passes, flag the centrifugal as likely preferred.
If it fails, proceed with Phase 4 on the pure axial. Write-up: `docs/phase4_impeller_stress_gate.md`.

### D4.0 Tool: scikit-fem 12.0.2 (added to `.venv`), verified before use
Axisymmetric rotating-body FE (`axisym_fe.py`, P2 triangles, centrifugal + traction + thermal)
checked against Timoshenko & Goodier closed forms:
* solid disc: centre +0.00 %, rim +0.35 %
* bored disc: bore -0.44 %
* parabolic-temperature disc: centre -0.02 %, rim -0.35 %

Morley-element Kirchhoff plate for the exducer blade: +5 % over cantilever theory (conservative).
No approved tool does 3D solid FE of a bladed impeller, so 3D effects such as rake and lean are
out of scope.

### Inputs (sourced)
* Material: Ti-6Al-4V at about 250 C, from the ATI Grade 5 data sheet typical curves (Fty ~100 ksi,
  Ftu ~111 ksi at 480 F; E 98 GPa; CTE 9.2e-6 /K), scaled to a minimum basis by the AMS 4928
  minimum/typical ratios: Fty 620, Ftu 681 MPa.
* Burst: 14 CFR 33.27 (120 % speed, 5 min, no burst), so N_burst/N >= 1.2 by the Robinson
  average-hoop criterion with k 0.85.
* Blade/hub fillet: Kt 1.4 (Peterson).
* Thermal field: eye 309 K to exit 520 K, from the Phase 3 fielded dash cycle.

### F4.0 Results
| part | result | status |
|---|---|---|
| hub with 12 mm through-bore, best shape (boss A 18 mm, p 2) | 529 MPa (+18 % yield margin); with thermal 580-601 MPa (+3.5 to +7 %) | marginal |
| hub boreless, same shape | 304 MPa; with thermal 319-326 MPa (+90 %) | pass |
| burst | N_burst/N 1.71 (bored), 1.92 (boreless), required >= 1.2 | pass |
| exducer blade root, 30 deg backsweep, Kt 1.4 | 1016 / 656 / 421 MPa at 2.5 / 3.5 / 5 mm root; passes only at >= 5 mm, with 32 % root blockage (5 % assumed in the aero design) | **fail** |
| inducer blade root tension | 220 MPa | pass |

Blade sensitivity at a 3.5 mm root:
* backsweep 20 deg: 444 MPa
* backsweep 10 deg: 224 MPa
* backsweep starting at 0.85 r2 instead of 0.7 r2: 517 MPa

The aero side of any of these is not evaluated.

### D4.1 Verdict: the impeller as designed FAILS the stress check (blade root, not disc)
The disc passes if boreless, and burst passes. The backswept exducer blade root fails at every
aerodynamically acceptable thickness. Per the user's instruction, **Phase 4 proceeds on the pure
axial (5 stages, OPR 5, 65 000 rpm, capped turbine)**, starting with low-speed operability and
stall, then shaft dynamics.

The centrifugal is not ruled out in principle. A redesigned exducer (about 20 deg backsweep or
tip-concentrated backsweep, boreless hub) would likely pass the stress check. But it needs a new
aero design, cycle point and a 3D FE check, which is outside this gate and is the user's decision.

**Open risk carried forward (R4.1):** the axial-stage efficiency comes from the Howell cascade
method, which has been checked only at conventional scale. Revisit it with a micro-axial validation
source if one becomes available, for example published micro-axial compressor test data.

---

## Phase 4 — axial compressor input error found and corrected (2026-09-13)

### F4.2 Phase 3 error: TurboDesigner blockage input doubled every axial annulus area
**The error.** `axial_design.build` passed `inlet_blockage=0.98 / outlet_blockage=0.96`, intended
as effective/physical area ratios. TurboDesigner 2.0.0 computes
`physical_area = flow_area * (1 + blockage)` (`flow_station.py`), and its README example uses 0.0.
So the Phase 3 axial annuli were 1.96-1.98 x too large.

**How it was found.** The Phase 4 stage-stacking model needed effective/geometric area 0.52 to
reproduce the design axial velocity. Evidence: `check_turbodesigner_blockage.py` (inlet tip radius
63.8 mm with the old input vs 45.8 mm with the corrected one).

**Effect.** The velocity triangles and loss-model efficiency were consistent. Radii, blade heights,
the turbine envelope cap, spool-speed feasibility and masses were not. The pure axial and the
axial stages of the axial-centrifugal are affected; the centrifugal and the impeller gate are not.

### D4.2 Correction and re-run
**Fix.** Blockage input set to 0.02 / 0.04 (the intended 2 % / 4 %).

**Re-run.** The trade was re-run with unchanged method, limits and calibrations:
* the rpm grid was extended to 90k;
* fixed-rpm cases were added (75k / 80k / 85k), because compressor efficiency is flat in rpm;
* 60k and 70k turned out infeasible (last blade height / DF).

**Corrected results, fielded, calibrated:**

| case | OD | length | dry mass | margin nom / pess |
|---|---|---|---|---|
| **axial OPR 5, 6 stages, 80k (new baseline)** | 142 mm, combustor-set | 611 mm | 5.74 kg | +104 / +89 % (worst corner +71 %) |
| was: 5 stages, 65k | 151 mm | 663 mm | 7.28 kg | +98 / +77 % (worst +61 %) |
| axial OPR 4 | 169 mm | 689 mm | 6.99 kg | +76 / +52 % |
| axial OPR 6 | infeasible with <= 7 stages | | | |
| AC 2 axial + cc, 90k | 170 mm | 610 mm | 6.11 kg | +75 / +50 % |
| AC 1 axial + cc, 90k | 170 mm | 564 mm | 6.14 kg | +75 / +50 % |

The AC front-stage speed limit is now 95-100k, not ~70k. The Phase 3b mechanism was an artifact.

**Decision.** The Phase 3 recommendation (pure axial, OPR 5) stands and is strengthened; the
baseline becomes 6 stages at 80 000 rpm. The fallback order becomes AC (90k), then the pure
centrifugal (not qualified as designed). Written up in `docs/phase3_engine.md` section 14, with a
banner at the top of that doc.

**Tool defect logged (TurboFlow 0.1.18, performance analysis):**
* With `stop_on_failure=False`, a failed point leaves None in the timing list and
  `print_simulation_summary` crashes; worked around by disabling that summary.
* After a failed point, every later point in the same call fails ("'list' object has no attribute
  'keys'", because the failed solution is used as the next initial guess). Worked around by sweeping
  each speed line outward from the design pressure ratio in two calls.

---

## Phase 4 — low-speed operability and stall of the pure axial (2026-09-14)

Write-up: `docs/phase4_operability.md`. Plot: `plots/phase4_operability.png`.

### D4.3 Tools and models (no approved tool gives axial maps)

**Compressor map:** own mean-line stage-stacking model, `axial_offdesign.py`. It extends the Phase 3
Howell design model:
* frozen geometry, constant deviation, fixed IGV (implied by the 50 %-reaction design);
* loss parabola calibrated to the Phase 3 stage efficiencies;
* stall at Howell's stalling deflection eps_s = eps*/0.8, with nominal
  tan(in*) - tan(out*) = 1.55/(1 + 1.5 s/c) (*Gas Turbine Theory*, ch. 5);
* surge surrogate = the peak of each speed line.

Verified: design point reproduced (PR 5.031 vs 5.000, eta 0.831 vs 0.828). Not validated
(open risk R4.1).

**Turbine map:** TurboFlow performance analysis of the Phase 3 turbine geometry (`turbine_map.py`).
The design point is reproduced exactly (1.077 kg/s, eta_tt 0.9306). Two TurboFlow defects were
worked around (F4.2).

**Engine match:** pyCycle with both maps (`operability.py`). Added to `cycle_model.py`, all default
off, with Phase 3 results re-checked unchanged (centrifugal dash W 1.32575 kg/s, TSFC 0.16416):
* map options;
* nozzle-area scale;
* overboard bleed port;
* transient mode NT4.

**Surge-margin criterion:** about 20 % for an HP compressor and 15 % for an LP one, up to half of it
for transients, defined as dR/R (Rolls-Royce patent CN112081683A).

**Bracket:** the same match with pyCycle's NPSS AXI5 map (5-stage PR 5.2 axial; provenance
undocumented).

### F4.3 Results (fixed geometry, dash-sized convergent nozzle)
* **Design point (dash):** surge margin 14 % at constant speed (18 % at constant flow), short of
  about 20 %. At the dash the nozzle stays choked and SMN stays at 13-15 % down to 70 % speed, but
  the first rotor passes its Howell stalling deflection below about 87 % corrected speed.
* **SLS:** the nozzle is unchoked (NPR at or below 1.65). SMN falls from 12 % at 100 % to 2.5 % at
  85 %, and the running line meets the peak line at about 83 %, below which there is no steady
  match. The first rotor is stalled from about 87 %. At 100 % SLS, T4 is 1163 K, so the speed limit
  sits at about 99 % for about 680 N.
* **AXI5 bracket:** stall-free to about 55 % (SMN 20-27 % over 70-95 %), meeting the stall line at
  about 52 %.
* **Remedies on the stacking map, singly:**

  | remedy | lowest steady speed | penalty |
  |---|---|---|
  | variable IGV (21 -> 49 deg) | about 80 % | stator 1 stalls |
  | nozzle x1.3 to x2 | about 80 % | costs 220-410 N of SLS thrust if left open |
  | 20 % bleed after stage 3 | about 70 % | - |
  | 30 % bleed | about 65 % | T4 up to 1250 K, over the limit |

* **No configuration reaches a conventional 30-35 % idle.** Acceleration time was not computed:
  there is no idle, and the steady SLS margin at 85-95 % is below the roughly 10 % transient
  allowance.

### D4.4 Verdict and decision point (not taken autonomously)
The Phase 3 "operability not quantified" risk of the pure axial is real. A workable pure axial would
need combined variable geometry and bleed (VIGV + start bleed + probably a variable nozzle), and
still idles at or above about 55-65 %.

Recommendation to the user: before more Phase 4 work on the pure axial, run the same two cheap checks
on the corrected axial-centrifugal (1-2 axial stages + cc, 90 000 rpm; 6.1 kg, +75 / +50 %):
1. impeller exducer blade root at 409-471 m/s;
2. operability with the TurboFlow centrifugal map.

Options A (pure axial with variable geometry), B (AC) and C (redesigned centrifugal) are laid out in
`docs/phase4_operability.md` section 3. Phase 4 mechanical design and CAD have not been started.

**Open risk R4.1 (carried, as instructed):** axial-stage efficiency and off-design loss/stall
correlations are checked only at conventional scale. Revisit them with published micro-axial
compressor test data. The AXI5 bracket shows the low-speed answer is map-sensitive.

---

## Phase 4 — rotor dynamics of the pure axial (2026-09-14)

Write-up: `docs/phase4_rotordynamics.md`. Done by a parallel sub-task on the corrected geometry.
Its assumed idle (35 %) is superseded by the operability result: idle at or above 55-65 %, which
means the damped 36 krpm mode is crossed only during start and shut-down.


### D4.R1 Tool: ROSS 2.3.0 (ross-rotordynamics, PyPI, added to `.venv`), verified before use
It was installed with uv. It added packages only; no existing package changed version. The new
packages include ross-rotordynamics 2.3.0, numba 0.67.0, ccp-performance 0.4.1, pint, control and
scikit-learn; refreeze `requirements-np2.txt`.

Two import work-arounds are in `scripts/phase4_turbomachinery/ross_shim.py`. Neither affects the
FE matrices:
* plotly 7 removed the `scattermapbox` template key, so the ROSS theme is created with skip_invalid;
* numba 0.67 cannot type ROSS's orbit helper, so it runs with `NUMBA_DISABLE_JIT=1`.

Verification (`rotordynamics_verify.py`) against closed forms:

| case | error |
|---|---|
| simply supported shaft, Euler-Bernoulli | -0.0001 % (Timoshenko -0.30 %) |
| Jeffcott rotor | -0.0001 % |
| overhung disc with gyroscopics, 0-60 krpm, forward and backward whirl | -0.13 to -0.20 % |
| project lateral eigen-solver vs ROSS run_modal | 0.000 %, same whirl labels |
| forward synchronous critical | -0.19 % |
| damped solver vs single-DOF k-c | +0.003 % frequency, -0.006 % damping ratio |

Mesh convergence: 10 mm → 5 mm changes the criticals by at most 0.04 %.

### Inputs (sourced)
* **Geometry and masses** from the corrected trade
  `data/phase3/trade_ax0_opr5_t1150_cap_blk_fielded.json` (6 stages, 80 000 rpm), through
  `arch_trade.scaled_comp` + `engine_mass`. The model reproduces the engine_mass disc and blade
  masses exactly (`rotor_model.py`). An earlier scratch run on the superseded pre-blockage-fix
  geometry was discarded.
* **Bearing and support stiffness:**
  * 1.9e7 N/m: 10 x 26 mm angular-contact ball bearing at 63 krpm (Wang, Lv & Luo, *Sensors* 2023);
  * 4.4e7 N/m: ball bearing on rigid supports (Gunter 2023);
  * 1.75e6 N/m and 876 N s/m: optimum damper cartridge of a ball-bearing turbocharger (Gunter 2023);
  * 6e5 N/m: micro gas turbine bearing suspension (ASME JEGTP 146(10) 101002, 2024).
* **Criteria:** API 684 (2003) statement of the API 617 AF-dependent separation margins (AF < 2.5
  none; 2.5-3.55: 15 % / 5 %; > 3.55: formulas capped at 26 % above MCS and 16 % below minimum
  speed). MCS = 105 % = 84 000 rpm; idle 35 % = 28 000 rpm.
* **Support damping in jet engines:** San Andrés, TAMU Notes 13 (2010), squeeze-film dampers with
  rolling bearings.

### F4.R1 The rotor as mass-sized in Phase 3 is not dynamically acceptable
The Phase 3 rotor has a 16/8 mm shaft and a 0.32 mm drum (the tie allowance). Layout A is the
front bearing at the compressor inlet hub and the rear bearing under the NGV, span 409 mm, turbine
overhang 20 mm. Its forward criticals:

| support stiffness | criticals |
|---|---|
| 1.9e7 N/m | 11.9 / 40.0 / 57.0 / 99.8 krpm |
| 1.75e6 N/m | 10.7 / 14.1 / 35.4 / 76.4 krpm |

Bending modes fall inside 28-84 krpm at every stiffness from 6e5 to 1e9 N/m, and in the damped
check at every damping level up to 2000 N s/m. Layout B (both bearings in the tunnel, 181 mm
compressor overhang) is similar or worse.

### F4.R2 Neither hard bearings nor a stiffer rotor alone can fix it
* **Hard bearings (1.9e7 N/m):** a bearing-dominated mode sits at 40-41 krpm for any shaft of
  16-32 mm OD and any drum of 0.3-3 mm.
* **Soft supports:** the free-free bending mode of the 0.43 m rotor stays at 23-53 krpm, against the
  106 krpm (MCS + 26 %) target. The shaft OD is capped at about 24 mm by the 14 mm-radius tunnel
  inside the combustor hub (Ri 17.4 mm).

### F4.R3 Soft, damped supports plus a stiffened rotor pass the API AF rules
Configuration: layout A, 2 mm Ti drum, 24/12 mm shaft with 16 mm journals, k 1.75e6 N/m,
c 876 N s/m. Damped criticals:

| critical | AF | where |
|---|---|---|
| 11.1 krpm | 1.9 | below idle |
| 17.9 krpm | 1.8 | below idle |
| 35.6 krpm | 1.1 | inside the range, critically damped |
| 120.0 krpm | 6.2 | 43 % above MCS |

It passes over k 0.6-5e6 N/m with c 876-2000 N s/m. Layout B passes only at c 2000 N s/m.

### D4.R2 Rotor-dynamic recommendation (screening)
* Layout A.
* Squeeze-film or O-ring damper cartridges at both ball bearings, k about 1-2e6 N/m and c about
  900-2000 N s/m. Hard-mounted bearings are ruled out.
* Stiffen the rotor beyond the Phase 3 mass sizing: 2 mm drum, 24/12 mm shaft, 16 mm journals.
  This costs **+0.53 kg of rotor mass (uncalibrated)**, taking the rotor from 1.39 to 1.91 kg.

Numbers for the transient work:

| quantity | value |
|---|---|
| **Ip** | **1.12e-3 kg m²** (9.31e-4 kg m² as mass-sized) |
| static bearing loads, 1 g | 6.2 / 12.5 N |
| gyroscopic bearing load | 23 N per rad/s of pitch or yaw rate (38-46 N per rad/s in layout B) |

### Open rotor-dynamic risks
* **R4.R1 Damper dependence.** The design relies on the dampers to make the free-free bending mode
  at about 36 krpm (45 % speed) critically damped. Damper realisation, temperature and nonlinearity
  are not modelled; neither are the damped unbalance response and the aero cross-coupling stability.
* **R4.R2 Bearing speed.** 16 mm journals at 80 krpm give DN 1.28e6, above the references (micro
  gas turbine DN 1e6; Wang bearing about 0.7e6).
* **R4.R3 Drum stiffness.** The drum is modelled as a continuous shell; joint flexibility
  (tie-bolt or curvic) is ignored, which is optimistic.
* The 85 000 rpm variant was not analysed.

---

## Phase 4 — option B checks: axial-centrifugal impeller stress and operability (2026-09-14)

User request: run the two checks proposed for option B. Write-up: `docs/phase4_optionB_checks.md`.
Plot: `plots/phase4_optionB_operability.png`.

### D4.5 Method (unchanged from options A / C, plus a benchmark)
**Check 1.** The gate solvers and criteria were applied to both AC impellers (`impeller_check_ac.py`):
* Phase 3 TurboFlow geometry, scaled to the fielded engine, at 90 000 rpm;
* tip speed 419 / 486 m/s.

**Check 2.** Combined compressor model (`ac_offdesign.py`):
* front stage(s) from the stage-stacking model;
* impeller from a TurboFlow off-design map (`centrifugal_map.py`, 10 x 21 points; design runs reproduced exactly);
* TurboFlow turbine maps and pyCycle running lines (`ac_operability.py`).

**Method benchmark** (`cc_benchmark.py`): the unchanged chain applied to the Phase 3 model of the JetCat
P400-PRO-LN, which idles at 30 000 rpm / 31 %, 14 N (database, jetcat.de).

### F4.5 Results
**Check 1: exducer blade root fails**, worse than the pure centrifugal:

| variant | root stress at 3.5 mm (limit 620) | root needed for Fty | hub blockage at that root |
|---|---|---|---|
| 2 ax + cc | 1105 MPa | 5.8 mm | 49 % |
| 1 ax + cc | 936 MPa | 4.9 mm | 36 % |
| pure centrifugal (for comparison) | 656 MPa | 3.7 mm | 23 % |

* Cause: tall exit blades, b2/r2 0.43 / 0.30 against 0.19.
* The disc and burst pass easily: boreless 208-276 MPa with the thermal gradient, burst ratio 2.1-2.4.
* About 10 deg of backsweep would pass (320-377 MPa); not evaluated aerodynamically.

**Check 2: operability no better than the pure axial.**
* Design-point SMN 11 %.
* SLS steady running line meets the surge surrogate at about 90 % speed.
* At 100 % SLS, T4 is about 1185 K (ECU limit about 97-98 %).
* Dash: 10-21 % margin over 70-100 %, once the impeller throat is opened (area ratio 0.65 -> 0.80). Phase 3 had
  sized it "just unchoked", leaving zero choke margin. TurboFlow PR and efficiency are unchanged by it.
* Robust to doubling the axial loss width.
* The combined peak is set by the axial stage(s): axial PR peaks 5 % below design flow and collapses 3 % above;
  the impeller characteristic is flat.

**Benchmark:**
* the chain predicts the P400 runs steady down to 35 % speed (27 N, EGT 740 C inside the published 480-750 C
  range), with 38-53 % surge margin, losing the match just below about 34 % (published idle 31 %);
* the rest of the chain is sound for centrifugal machines, so the decisive, unvalidated element in options A and B
  is the axial-stage model (R4.1).

**Correction.** The impeller gate said the pure-centrifugal root "survives at 5 mm or more (32 %)". The interpolated
threshold is 3.7 mm (23 % hub blockage, no margin). The gate doc is corrected; the verdict is unchanged.

### D4.6 Verdict
**Option B fails both checks as designed.** It does not cure the impeller problem it was meant to cure: the disc
passes but the blade root is worse. In the same model its operability is no better than the pure axial.

The pure centrifugal (option C) is the only architecture the benchmarked chain supports at low speed, and its only
failed item is the exducer blade root.

**Suggested next step (awaiting the user):** redesign the pure-centrifugal exducer, with about 10-20 deg backsweep
or tip-concentrated backsweep, then:
1. re-run the TurboFlow design, dash cycle and thrust margin;
2. run the stress gate and this operability chain on it.

Phase 4 mechanical design and CAD have not been started.
