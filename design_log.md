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

---

## Phase 3R — engine redesigned around a centrifugal compressor (2026-09-14)

Write-up: `docs/phase3r_centrifugal.md`. Plots: `plots/phase3r_cc_trade.png`, `phase3r_backsweep.png`,
`phase3r_mission.png`. Data: `data/phase3r/`, `data/phase3r_*`.

### D3R.0 User decision: centrifugal compressor only
The user decided to design the engine around a centrifugal compressor as the configuration suited to this scale, and
asked to go back to Phase 3 with the brief in view. Phase 3 was redone to the brief's Phase 3 scope:
* cycle at the reference point;
* a quantitative trade of 2-3 options with SFC, airflow, mass and size (here OPR, spool speed and backsweep of the
  single-stage centrifugal engine);
* off-design across the mission;
* one recommendation.

Phase 4 not started.

### F3R.1 Tool defect: TurboFlow 0.1.18 Wiesner slip takes cos(degrees) as radians
`centrifugal_compressor/slip_model.py`: `np.sqrt(np.cos(theta_out))`, while `theta_out` is in degrees everywhere else.
* **Evidence** (`verify_turboflow_slip.py`): the slip factor solved on the Phase 3 impeller is 0.9310 against the correct
  0.8366 at -30 deg; at -10 deg the model returns NaN.
* **Consequence:** the Phase 3 impeller gives PR 3.39, not 4.01, at 504 m/s. At the upstream example's -24.5 deg the
  error is only 6 %, which is why Phase 0 passed.
* **Fix:** `turboflow_fixes.py`, imported by `centrifugal_design.py` and `centrifugal_map.py`. The solved σ now equals
  Wiesner exactly.
* **Scope:** every earlier centrifugal result, including the Phase 3b and Phase 4 axial-centrifugal impellers, the gate
  and the P400 / Nike runs.

### F3R.2 The Phase 3 inducer was beyond fielded practice
`inducer_anchor.py`, with the same optimum-inducer rule on 9 database engines: inducer shroud relative Mach 1.10-1.33
(TJ40-G1 highest). At the fielded airflow, 85 000 rpm gives 1.43; 75 000 gives 1.29; 77 500 gives 1.33.
**A3R.1:** M1s,rel <= 1.33 → design speed 75 000 rpm.

### F3R.3 Fielded scaling was wrong for the impeller and unsafe for the turbine
* The √W scaling (A3.6) grew the impeller exit radius with flow, although work sets it. Work-based scaling is used
  instead: -6 to -8 mm where the diffuser sets the OD.
* The √W-scaled turbine tip was about 11 % past its 350 MPa blade-root limit, about 24 % in stress (Phase 3 centrifugal
  included). The turbine is now re-designed by TurboFlow at the fielded cycle: it sits on the limit, and mass drops
  about 0.7 kg.
* At 85 000 rpm the fielded turbine cannot pass the flow within the limit.

### F3R.4 Calibrations re-anchored with the fix
* **Mass model:** P400 3.52 vs 4.01 kg (-12 %); Nike 7.23 vs 9.15 kg (-21 %). Mass ×1.20 (1.14-1.27), length ×1.21.
  The Nike's compressor-set OD is over-predicted (212 vs 201 mm, +5.7 %), so the diffuser rule is conservative.
* **P400 operability benchmark:** steady to 37.5 % against the published 31 % idle (about 5 points pessimistic); design
  SMN 61 %.

### D3R.1 Method: stress inside the design loop
`impeller_stress.py` wraps the verified gate solvers. At MCS 105 %:
* the exducer root thickness is sized to Fty (Kt 1.4, >= 1.6 mm) and its blockage sets the physical exit width;
* boreless disc with the thermal gradient <= Fty;
* burst >= 1.2 × N_MCS.

Other conventions: 12 + 12 splitters (Aungier Z_eff 18), 10 % choke margin, trailing-edge dump loss checked
(<= 0.14 points).

### F3R.5 Trade (13 full-chain cases after the 36-design screen; fielded)
* **OPR:** optimum 4.0 at 75k, where the combustor (170 mm) and the diffuser meet.
* **Backsweep:** from 0 to -30 deg, OD 177 → 199 mm and pessimistic margin +41 → +14 %.
* **Stress:** every case is feasible once the root is sized.
* **77.5k radial:** 172 mm, +48 %, at the inducer limit.
* **85k:** looks best on paper (170 mm, +51 %) but violates A3R.1 and the turbine flow / stress limit.

### F3R.6 Backsweep sets the stability (TurboFlow maps + pyCycle, benchmarked chain)
Design surge margin is 0 / 19 / 28 / 39 % at 0 / -10 / -15 / -20 deg.
* **Radial:** radial blades give work independent of flow, so the characteristic peaks at the design point. The
  running line rides the surge surrogate: not operable.
* **-10 deg:** the SLS line has 12-17 % surge margin, and the engine cannot run steadily below 45 % speed.
* **Criteria:** SMN >= ~20 % needs >= 10.5 deg of backsweep; the 25 % pessimistic thrust margin needs <= 19 deg.

### D3R.2 Recommendation: single-stage centrifugal, OPR 4.0, 75 000 rpm, -15 deg backsweep
Chosen because it sits mid-window on both criteria.

| quantity | fielded | tool |
|---|---|---|
| airflow | 1.326 kg/s | 1.068 kg/s |
| dash TSFC | 0.164 kg/(N h) | 0.138 |
| impeller tip speed | 525 m/s (root 2.2 mm, blockage 9 %) | |
| engine OD | **187 mm**, diffuser-set | 173 mm |
| length / dry mass | **478 mm / 6.74 kg** (6.38-7.09) | 6.21 kg |
| margin nom / pess | **+55 / +29 %** (worst corner +22 %) | +71 / +46 % |
| design surge margin | 28 %; SLS line 22-27 % over 55-100 % | |
| SLS max thrust | 631 N at 98.2 % speed, T4-limited | |
| lowest steady speed / idle for fuel | 35 % / 40 % (37 N, 19 % of max fuel) | |

Impeller disc +86 % yield margin, burst ratio 1.90 at MCS.

**Cantera:** T4 -4 K, γ +0.0002 against pyCycle.

**Sensitivities:**
* OD calibrated to the Nike: 177 mm, +42 %;
* η_c 0.66: 192 mm, +22 %;
* η_c 0.74: 182 mm, +35 %.

Against the Phase 3 centrifugal claim (175 mm, +44 %): 12 mm larger and 15 points lower, because the Phase 3 numbers
were not achievable (F3R.1-F3R.3, plus the gate).

### F3R.7 Mission with the real-map deck (replaces the placeholder maps, A3.8)
* The deck is T4-limited at low Mach; 500 N at the dash point.
* Brake release to M 1.02 / 5 km in 28 s. Minimum transonic excess thrust 115 N (pessimistic drag).
* Sortie fuel 3.05 kg including reserve, against 1.90 kg in the trade's scaling. Idle fuel from the model is 19 % of max;
  fielded engines are 14-18 %, and Phase 2's A1.4 used 10 %.
* **TOGW 20.0 kg, 5.0 kg under 25 kg.**
* The inherited Phase 2 climb is not flight-path-limited at T/W > 1 (small fuel effect).

**Decision (user, 2026-09-14):** "go ahead with the -15° design". D3R.2 is the baseline, and Phase 4 proceeds on
`ce75000_opr4_t1150_b15_cap`.

**Open for Phase 4** (see the Phase 4 centrifugal entries below for what was done):
1. diffuser design (the diameter driver, worth ~13 points of margin);
2. 3D impeller FE, vibration and LCF (the root sits at Fty at MCS by construction);
3. rotor dynamics at 75k;
4. start and acceleration transients;
5. turbine material data (on its 350 MPa limit);
6. compressor map above 105 % corrected speed.

---

## Phase 4 (centrifugal baseline) — turbomachinery preliminary design and Phase 2 ↔ 4 closure (2026-09-14)

Write-up: `docs/phase4r_centrifugal.md`. Plots: `plots/phase4r_td_check.png`, `phase4r_rotor_critmap.png`,
`phase4r_rotor_final.png`. Scripts: `scripts/phase4_turbomachinery/td_check.py`, `hecc_surge_check.py`,
`cc_blade_modes.py`, `cc_rotor*.py`, `cc_transient.py`, `cc_closure.py`.

### F4R.1 Independent compressor check (NASA turbo-design, HECC-validated)
The code was reviewed before use: no unit errors; no shock loss; no diffuser-stall model; its vaned-diffuser loss cannot
size the diffuser.

On the three OPR-4 / 75k impellers, rebuilt from their meanline geometry without tuning:

| impeller | turbo-design PR / η | TurboFlow PR / η |
|---|---|---|
| 0° | 3.96 / 0.786 | 4.00 / 0.810 |
| -15° | 4.05 / 0.803 | 4.01 / 0.818 |
| -20° | 4.07 / 0.808 | 4.00 / 0.819 |

**The design point is confirmed.** A throat estimated from blade angles (0.63 of the eye area) choked 2 % above design
flow, which confirms that the 10 %-margin throat (0.75 of the eye) is needed.

### F4R.2 The surge surrogate fails on a real vaned-diffuser stage
* **NASA HECC measured:** last stable point at 95.1 % of design flow with PR still rising. Design surge margin 8.4 %.
* **turbo-design on HECC:** the characteristic rises down to 61 % flow, so the surrogate gives >= 73 %.
* **On our -15° impeller:** turbo-design's peak is at 0.94 W_d (SMN 6.5 %), against TurboFlow's 0.80 W_d (28 %).

For vaned diffusers, surge is set by diffuser stall, which neither tool models. **The Phase 3R surge margins are
unvalidated (risk R4R.1, top).** The backsweep trend is confirmed by both tools; its magnitude is not.

### F4R.3 Exducer blade vibration (Morley plate modal, verified -1.5 % against a clamped strip)
Static modes: 9.33 / 15.96 / 28.37 kHz. With 19 diffuser vanes, mode 1 crosses 19/rev at 39 % speed (idle) and mode 2 at
67 %; no engine order 1-6 crosses in 35-105 %. 15-17 vanes would move the static crossings away from idle and from
95-100 %. The vane count is to be chosen together with the diffuser's stall range.

### F4R.4 Rotor dynamics: the bending mode is set by the combustor length
The first shaft-bending mode has 4 % of its strain energy in the bearings, so dampers cannot reach it.
* With the Phase 3 combustor (235 mm bearing span): 38-59 krpm for 16-28 mm shafts, and 74-76 krpm for a 32 mm thin
  tube. All inside the 26-79 krpm range; API fail.
* The bending critical rises steeply as the span shortens. A lighter impeller boss lengthens the span.

### D4R.1 Rotor and combustor configuration
* combustor liner 0.8 × the Phase 3 rule (bearing span 192 mm), with the combustor grown radially to the diffuser
  envelope (OD 184 mm, no diameter cost). Volume-corrected theta -0.42 σ of the 7-engine reference spread;
* AISI 4340 tube shaft 32 × 25.6 mm, 12 mm journals (DN 0.95e6 at MCS);
* damped soft supports, k 1.75e6 N/m, c 876 N s/m.

Criticals:

| critical | AF | position |
|---|---|---|
| 8.3 krpm | 2.64 | 68 % below minimum speed |
| 14.4 krpm | 1.28 | critically damped |
| 105.6 krpm (bending) | - | 34 % above MCS (25.8 % required) |

**API pass.** The bending mode is 34 krpm at rest; gyroscopic stiffening from the overhung impeller lifts its crossing.
Rotor 2.11 kg, Ip 2.13e-3 kg m². Open: combustion performance at L/D_ref 2.2; damper mass.

### F4R.5 Acceleration (SLS, T4 <= 1150 K, SMN >= 5 %)
* 40 % → 95 % in 6.6 s; 45 % → 95 % in 3.5 s. The B300F data sheet quotes 37 → 100 % in 4.6 s.
* Acceleration from idle is limited by surge margin, not T4.
* With a 10 % transient margin the engine cannot accelerate from 40 %.

### D4R.2 Phase 2 ↔ 4 closure
* **Engine:** 6.85 kg calibrated (6.49-7.21), against 6.74 kg: shaft +0.24, casing -0.12, liners -0.06 kg raw. Length
  426 mm (-52 mm), OD 187 mm.
* **Mass budget:** accessories 1.60 + structure 3.82 + gear and chute 1.27 + fuel system 0.40 + systems 2.02 + growth
  1.13 + fuel 2.98 kg.
* **TOGW 20.09 kg, 4.91 kg under 25 kg. Closes.**
* **Checks:** dash margin +54.7 / +28.5 %; transonic minimum excess thrust 116 N (pessimistic); take-off roll 46 m.
* **Landing at 17.7 kg:** 175 m with flaps + chute; 316 m with flaps only. The chute stays required for 300 m.

**Decisions for the user before the design freeze:**
1. how to secure the surge margin: diffuser designed for range, vaneless diffuser, -20° backsweep, bleed or variable
   nozzle, or a rig test;
2. the diffuser vane count, together with (1);
3. whether to accept the shorter combustor pending combustor data.

---

## Phase 5 — design freeze: status snapshot for review (2026-09-14)

User request: compile `docs/design_freeze.md` from the current state (Phase 4R, -15° backsweep, with the rotor fix) as
a snapshot for review. Carry the open risks forward explicitly; do not start Phase 6.

### D5.0 Freeze document compiled; sign-off NOT given
No new analysis was run for the freeze; every number comes from the Phase 3R / 4R data files.

Contents:
* architecture, cycle and components (section 1);
* airframe closure: TOGW 20.09 kg, +54.7 / +28.5 % dash margin, 46 m take-off roll, 175 m landing with chute
  (section 2);
* rotor dynamics: API pass and the fix that got there (section 3);
* open risks (section 4);
* what CAD would commit to (section 5);
* decisions for the reviewer (section 6).

Precisions against the request, as the data show:
* the worst-corner margin +21.8 % dates from Phase 3R (before the Phase 4 engine changes) and was not re-run;
* the grown, shortened combustor has 94 % of the Phase 3R liner volume and volume-corrected loading 0.92 × the
  reference mean: near parity, not exact;
* the idle-range surge margin is 8.4-8.7 % at 35-40 % speed and 13 % at 45 % (TurboFlow surrogate).

**Open risks carried, none resolved:**
1. surge margin (no validated method; tools 28 % vs 6.5 %; the surrogate is wrong by ~9× on HECC; the diffuser redesign
   has not been run);
2. idle-range surge margin and acceleration (the start bleed has not been sized);
3. combustor shortened 20 %, unverified;
4. the 19 diffuser vanes excite exducer mode 1 at idle (39 %);
5. no rig or bench validation;
6. carried items (exducer root at Fty at MCS, turbine on its limit, dampers, DN, diffuser sets OD, worst corner < 25 %,
   and others).

**Phase 6 (CAD) not started**, awaiting the user's review and sign-off.

---

## Phase 6 — CAD / 3D: toolchain step (2026-09-14)

**User instruction:** "continue phase 6", given after the Phase 5 snapshot. It is taken as the go-ahead to enter
Phase 6. The freeze's open decisions (surge margin, diffuser vane count, combustor length) were not answered and remain
open. The brief's first Phase 6 step is to propose the CAD toolchain and confirm it with the user **before any geometry
is generated**, and this entry covers only that step.

### D6.0 Toolchain proposed; install verified; awaiting confirmation (`docs/phase6_toolchain_proposal.md`)
* **Separate `.venv-cad`** (Python 3.12.10, NumPy 2.5.3, `requirements-cad.txt`) with CadQuery 2.8.0 (OCCT 7.9.3),
  gmsh 4.15.2 and pyturbo-aero 1.3.8. The frozen `.venv` and `.venv-np1` are untouched.
* **Verified** (`scripts/phase6_cad/smoke_cad.py`, primitives only), all exact to rounding:
  * box volume and STEP round trip;
  * B-spline surface through cylinder points against the analytic area;
  * spline-section loft against the analytic volume, valid solid;
  * gmsh tetra volume.
* **Findings:**
  * pyturbo `Centrif` outputs point clouds only (no solids, no export), and has a shared class-level `patterns` list;
  * the OCP bindings need enum arguments;
  * the smoke process exits non-zero at teardown after passing.
* **Proposed plan:**
  1. parameter sheet with frozen / provisional tags;
  2. 2D meridional layout;
  3. impeller from pyturbo-aero, checked against the analysis;
  4. the other components as conceptual solids, assembled in STEP;
  5. optional 3D impeller FE (gmsh + scikit-fem, verified first).

  Diffuser, combustor, bearing span / shaft and the bleed provision are modelled parametrically.

No engine geometry has been generated.

**User confirmation (2026-09-14):**
* toolchain: CadQuery + pyturbo-aero + gmsh (as proposed);
* scope: **engine + airframe + 3D impeller FE**;
* open items: **provisional parts modelled parametrically**, with the decisions staying open in
  `docs/design_freeze.md`.

Geometry generation starts with the parameter sheet.

### D6.1 Parameter sheet (`scripts/phase6_cad/make_params.py` -> `data/phase6/engine_params.json`, `airframe_params.json`)
* Every CAD dimension is an entry `{value, unit, status, source}`, with status one of: **frozen** (from the freeze),
  **derived** (computed from frozen values), or **provisional** (a construction rule no analysis fixed).
  **29 of 74** engine parameters are provisional. These are the freeze's open items (diffuser, combustor, bearing
  span / shaft) plus the LE radius and the impeller camber law.
* Consistency checks (`params_consistency.json`):
  * eye velocity C1 = 200.2 m/s, β1 hub / rms / shroud 34.3 / 55.6 / 62.8° (zero incidence);
  * component length 352.5 mm against the calibrated envelope 426 mm (the calibration adds length for items not
    modelled; the CAD keeps the calibrated cylinder as a reserved volume).
* **Airframe inputs updated:** capture area 47.5 → 55.1 cm² (Phase 3R fielded flow) and nozzle A8 49.1 → 70.8 cm²
  (the Phase 4 engine's throat). Both were stale Phase 2 values.
  * Re-running the Phase 2 drag model with them gives CDS 81.89 → 81.66 cm² nominal and 98.64 → 97.70 cm² pessimistic
    (−0.3 % / −1.0 %). Negligible; the closure is not re-run.

### D6.2 Engine CAD (`engine_cad.py` -> `cad/engine/*.step`, `cad/engine_assembly.step`)
* 27 parts, all valid solids.
* Construction:
  * revolved profiles for the casings, liners and rings;
  * log-spiral diffuser vanes (19) and 30 placeholder deswirl vanes;
  * NGV (34) and rotor (28) rows built as planar sections with polygon wires and ruled lofts. Spline sections
    self-intersected at the TE cusp (volume off 19 %). Single-vane volume matches area × height to 0.1 %;
  * Stodola turbine disc (engine_mass law), shaft with journals, bearings, housings, tunnel;
  * impeller imported (D6.3).
* **Envelope rule found:** the diffuser OD sets the engine OD (r4 + 3 mm), so the 90° bend into the deswirl annulus
  must turn **inside r4**. The diffuser back plate stops at the deswirl inner radius.
* **Size:**
  * bounding box 382.5 mm long including the 30 mm inlet lip; components 352.5 mm; calibrated envelope 426 mm;
  * OD 186.6 mm, equal to the envelope.
* **Mass** (`mass_compare.py`, CAD against the RAW bottom-up model, since the ×1.20 calibration covers the items the
  CAD does not draw):
  * total: CAD 5.19 kg against 4.92 kg for the model items that are drawn (+5.4 %). The model's starter, fuel manifold
    and 10 % fasteners (0.78 kg) are not drawn;
  * items: impeller +17 %, shroud / inlet +19 %, outer casing +53 %, diffuser + deswirl −49 %, shaft −26 %, turbine
    items within ±20 %;
  * so the calibrated 6.85 kg is not contradicted, but the item split is.

### D6.3 Impeller CAD (`impeller_cad.py`; pyturbo-aero + CadQuery)
* **Inducer throat, found:** the tool-level design ratio 0.75 × eye was not met by the first CAD camber (0.611 × eye).
  * TurboFlow's `area_throat_ratio` multiplies the eye area. Its choke check is isentropic relative flow through
    A_throat, at the mean eye radius.
  * Reproduced by hand at tool level: 0.70 → 1.086, 0.75 → 1.164 × design flow, the same bracket Phase 3R found.
  * On the larger fielded eye, the Phase 3R requirement (10 % choke margin) needs **0.665 × eye**. The first CAD camber
    gave 1.010 × design flow, i.e. ~1 % margin.
* **Camber law replaced (provisional, analysis-traceable):** θ = θ_rf(x) + θ_bs(r).
  * Radial-fibre inducer, θ_rf′(x) = (ω/C1)(1 − x/L)^n. Zero incidence at every LE radius at once; no centrifugal
    bending of the inducer, as the gate's inducer-root estimate assumed.
  * Plus exducer backsweep, linear in r from 0 at 0.7 r2 to 15°: the plate model's own law.
  * The TE metal angle is 15° on every span.
  * pyturbo's 4-point Bezier with one TE θ for all spans could not deliver this. It hooked from 43° to 15° in the last
    10 % of chord at the shroud. Replaced through the `__build_camber__` hook by a 14-point least-squares Bezier
    (fit ≤ 0.6°).
  * **n = 3**, the smallest exponent meeting the 10 % margin (n 2 / 2.5 / 3 → choke 1.040 / 1.072 / **1.102** × design).
    This means fast inducer unloading: shroud metal angle 62.8° at the LE, 42.8° at 30 % chord. The inducer
    diffusion / loading this implies has not been analysed (no CFD) — new open item.
* **Checks:**
  * CAD metal angles within 1.1° of the law along the chord;
  * TE measured 11.6 / 13.1 / 14.2° hub / mid / shroud over the last grid segment against 13.9 / 14.4 / 14.8° target
    there (the TE closure rounds it);
  * thickness 2.23 mm root and 0.80 mm tip (sized 2.235 / 0.8);
  * throat 0.667 × eye, choke **1.102 × design**.
* **pyturbo / OCCT problems met and fixed** (tools_survey section 9):
  * the SS / PS are Beziers through control points (`camber_follow_density = 60`);
  * `splitterblade` sits at the main blade's θ, so every splitter lay inside a main blade until rotated half a pitch;
  * faceted blades: fan caps gave silently failing booleans, and even with ladder caps the sliver-tet meshes followed;
    now **smooth B-spline blade solids** (grid points on the surface to 1e-5 mm).
* **Sector and wheel:**
  * the FE sector is bounded **through the passages** by radial-line ruled surfaces ψ = ψ_main(x) − 22.5° / +7.5°, so
    no blade is cut. Flat cut planes cut every blade, and the slivers made the FE near-singular;
  * 1 solid; volume closure 3e-5; 12 × hub sector = hub to 2e-8;
  * the wheel is 12 copies of the sector.
* **Mass:** wheel 1.082 kg (hub 0.944, blades 0.138).
  * The CAD hub matches the axisymmetric FE's hub to 0.04 %.
  * The stress model's impeller is 1.132 kg (smeared blades at 1.52 mm mean thickness), so its blade pull on the hub
    is ~36 % heavier than the CAD blades: conservative for the hub.
  * Ip 1.287e-3, Id 8.29e-4 kg m², CG 36.2 mm from the nose.

### D6.4 Airframe integration (`airframe_cad.py` -> `cad/airframe/*.step`, `cad/aircraft_assembly.step`)
* **Built:**
  * fuselage OML with the D2.6 area-rule waist (as the drag model assumes), 1.5 mm skin;
  * pitot intake duct straight to the engine face at x = 1.315 m;
  * biconvex wing / tail panels;
  * jetpipe to the tail nozzle;
  * engine assembly plus the calibrated envelope as a reserved volume. All parts valid.
* **Findings** (not in any earlier model):
  1. **engine-to-skin radial gap 8.7 mm**, at x = 1721 mm where the waist is deepest over the envelope. Positive, but
     thin for structure, mounts and insulation around a hot casing;
  2. **jetpipe** 1.09 m long at M 0.34, 64.1 mm radius:
     * friction ΔPt/Pt ≈ 0.64 % (Haaland), not in the cycle (nozzle Cv 0.98 only). Rough thrust effect −1.7 %
       (estimate, not run through the cycle);
     * the turbine exit swirl (−17.8°, TurboFlow) is not recovered in the model, arguably covered by the fielded
       calibration;
     * at the tail the jetpipe wall is the nozzle lip (−0.5 mm "gap" to the boattail skin at the exit);
  3. **fuel:** the forebody annulus around the duct holds 13.75 L gross against 3.72 L of fuel (27 %). It shares that
     space with avionics, batteries and instrumentation (not laid out);
  4. intake duct: area ratio 1.42 over 1.29 m (0.36° equivalent cone), benign.

### D6.5 3D FE of the impeller (`fe3d_impeller.py`; gmsh + scikit-fem P2 tets + cyclic tie; `data/phase6/fe3d_impeller.json`)
* **Model:**
  * the 30° passage-bounded sector (D6.3); centrifugal load at MCS (105 % of 75 000 rpm);
  * Ti-6Al-4V, E 110 GPa, no thermal load;
  * boss held axially within the 6 mm stub-shaft radius; the rigid rotation about x is held by a weak spring and
    subtracted from the reported displacements.
* **Cyclic symmetry:** a tie. Each slave-face DOF is interpolated from the P2 trace of the master face, because gmsh
  `setPeriodic` needs matching face topology.
* **Verification** (same code path):

  | case | FE | reference | difference |
  |---|---|---|---|
  | (A) rotating disc, centre stress | 451.8 MPa | 452.8 MPa (theory) | −0.2 % |
  | (A) outer-band hoop | 185.6 MPa | 185.7 MPa (theory, same points) | −0.05 % |
  | (B) hub alone, flat cuts, peak von Mises | 307.9 MPa | 311.6 MPa (verified axisymmetric FE) | −1.2 % |
  | (B) average hoop | 160.0 MPa | 159.8 MPa | +0.1 % |
  | (B′) same hub, twisted passage cuts | 308.0 / 160.0 MPa | as (B) | tie points within 2e-9 mm of the master face |

  * Hoop stress within 2 mm of the axis: 249 vs 260 MPa (−4 %, sampling of that small region).
* **Solvers:**
  * pyamg converged on (B) (agrees with SuperLU to 1e-7) but stalled with the interpolated tie;
  * SciPy SuperLU paged at 220 k DOF;
  * MKL PARDISO (pypardiso, added to `.venv-cad`): matches SuperLU to 5e-7 on (B′), residual ~1e-11, 8-14 s.
* **Rejected intermediate runs, recorded so they are not reused:**
  * flat-cut sector: near-singular stiffness (AMG stalled at 3 % residual);
  * faceted blades: 15 % sliver tets, 1e6 MPa spurious peaks.
* **Production results at MCS** (mesh 40 k tets baseline / 61 k tets fine, quality median 0.72 / 0.75):

  | quantity | baseline | fine | reference |
  |---|---|---|---|
  | **exducer root** hot spot (0.4 t / 1.0 t extrapolation, > t_root from the blade ends) | 426 MPa | **413 MPa** | Phase 3R plate model nominal 441 MPa |
  | exducer root × Kt 1.4 | 596 MPa | **578 MPa** | plate 618 MPa; **Fty 622 MPa** |
  | **inducer root** hot spot (same rule) | 360 MPa | **355 MPa** | gate estimate 196 MPa (radial-fibre tension, k 0.6) |
  | inducer root × Kt 1.4 | 505 MPa | 497 MPa | Fty 622 MPa |
  | **hub** > 1 mm inside the surface, 99.9th percentile | 331 MPa | **333 MPa** | axisymmetric with smeared blade pull 313 MPa |
  | hub single-point maximum | 336 MPa | 438 MPa | not converged; the percentile holds |
  | blade-end corner peaks, LE / TE (singular) | 581 / 630 MPa | 669 / 470 MPa | mesh-dependent |
  | blade tip closing toward the casing (inducer LE tip) | 0.074 mm | 0.074 mm | cold clearance 0.25 mm |

* **Findings:**
  1. **The exducer root sizing holds.** The 3D root stress is 3-7 % below the plate model, which included no hub
     compliance or membrane load. With Kt 1.4 it is 93-96 % of Fty at MCS. The freeze's "exducer root at Fty at MCS"
     item is confirmed as essentially on the limit, not relieved.
  2. **The inducer root is ~1.8× the gate estimate** (355 vs 196 MPa). The load is carried in-plane (membrane stress
     nearly flat from 0.4 t to 1.0 t), and the hub's meridional strain is imposed on the blade root; the 1D radial-
     tension estimate has neither. It is still inside Fty after Kt 1.4 (~25 % margin). This is new information, not
     a failure.
  3. **The hub peak is 6 % above the axisymmetric model** (333 vs 313 MPa mechanical). With the gate's +22 MPa thermal
     gradient that is ~355 MPa, still ~75 % yield margin.
  4. **The blade-end corners are singular in this CAD.** The LE root sits on the hub's front edge (no nose ahead of
     the blades) and the TE root on the rim edge, with no fillets anywhere. Peaks of 470-669 MPa there change with the
     mesh. A detailed design needs a hub nose extension and root / end fillets. Kt 1.4 is an assumed fillet factor
     that no fillet in the CAD represents.
  5. **Tip closing** is 0.074 mm mechanical (30 % of the clearance). Thermal growth of the wheel and casing is not
     included.
  6. **Deflection:** meridional 0.17 mm; tangential blade deflection 0.44 mm (no clearance effect).
* **Not done:** thermal load, vibration modes of the 3D blade (Phase 4R used the plate model), fillet geometry,
  contact at the stub shaft.

### D6.6 Figures and tool additions
* `render_cad.py` (VTK off-screen, matplotlib) writes:
  * `plots/phase6_engine_cutaway.png`, `phase6_engine_section.png`;
  * `phase6_impeller.png`, `phase6_impeller_sector.png`, `phase6_impeller_fe.png`;
  * `phase6_aircraft.png`, `phase6_aircraft_cutaway.png`, `phase6_aircraft_section.png`.
  * Off-screen VTK dropped translucent actors, so the aircraft interior is shown as a cutaway.
* `.venv-cad` additions (in `requirements-cad.txt`): pyamg 5.3.0, pypardiso 0.4.7 (MKL 2026.1), each checked against
  SciPy's SuperLU before use.
* **Engine specification PDF** (user request, 2026-09-14): `scripts/phase6_cad/spec_sheet.py` → `docs/boomsonic_engine_spec.pdf`, 5 pages.
  * Every number is read from the data files at run time. The constants η_b and the turbine blade-root allowable are
    parsed from `dash_cycle.py` / `turbine_design.py`.
  * Two quantities were dropped rather than printed with an unsourced input:
    * an equivalence ratio (it needed a hand-typed stoichiometric fuel-air ratio);
    * an intake recovery from a γ = 1.4 freestream total (it disagreed with the cycle's documented duct loss).
  * The open risks are stated on page 1 and in section 9.
  * reportlab 5.0.1 added to `.venv-cad`; its dependencies pillow and charset-normalizer were already present. The layout
    was checked page by page, rendered with pypdfium2 in a throw-away `uv run` environment, not installed.
* Documentation correction: the freeze and Phase 3R docs said the physical exit width b2 is "12.0 mm". The data say
  11.796 mm; the text now reads 11.8.

---

## Axial design (option A) taken to its freeze — Phase 3A-R refresh (2026-09-14)

**User instruction:** "search the project folder and you will see an early design concept that uses 6 axial stages
take that design paremeters where we left off and finished it as you did with centrigual one". The concept is the pure
axial baseline (OPR 5, 6 stages, 80 000 rpm; D4.2), last worked in Phase 4 (operability D4.4, rotor dynamics D4.R2)
before the switch to the centrifugal (D3R.0). **User decision (AskUserQuestion): pause at the axial freeze for review
before any axial CAD** (brief rule 4). The centrifugal design is not changed. The axial is Phase 3A-R / 4A / 5A, tags
`ax*_3r`, data in `data/phase3ax/`, `data/phase4ax/`.

### F3A.1 The Phase 3 / 4 axial numbers are stale in three ways
1. **Fielded efficiency.** A3.4 debited the axial tool efficiency by 0.70 / 0.794. The 0.794 is the Phase 3 centrifugal
   tool efficiency, computed with TurboFlow's defective slip (F3R.1).
2. **Compressor scaling.** The √W scaling of the tool-level geometry (A3.6) cannot match both the fielded flow (area
   ~ r²) and the fielded work (~ U²) at fixed speed; F3R.3 found the same flaw for the impeller.
3. **Turbine.** The √W-scaled turbine ran past its 350 MPa blade-root limit (F3R.3 applies to every Phase 3 case).

In addition, the mass / length calibrations were re-anchored in Phase 3R (×1.20 / ×1.21).

### A3A.1 Fielded axial efficiency re-referenced
* η_c,fielded = η_c,tool × 0.70 / η_ref, with η_ref = the Phase 3R centrifugal tool efficiency 0.8175
  (`cct_ce75000_opr4_t1150_b15_cap`), so K_F = 0.856 (was 0.882).
* The axial tool efficiency stays 0.8285 (TurboDesigner + Howell, not touched by the slip defect), so fielded
  **0.709** (was 0.730).
* Still an assumption (A3.4). Phase 3 showed the architecture conclusion does not depend on it.

### D3A.1 Method (`scripts/phase3_cycle/ax_trade.py`)
1. **Fielded compressor re-designed AT the fielded cycle.** TurboDesigner at the fielded W / Tt2 / Pt2 / PR 5, with
   the fielded efficiency setting the work. The Howell loss model is evaluated once; it reports the tool-level
   efficiency of that blading. Phase 3 limits apply: DF ≤ 0.5, de Haller ≥ 0.72, rotor-1 tip M_rel ≤ 1.35, last blade
   ≥ 10 mm.
   * Grid: 70-90 krpm × 5-8 stages × hub/tip 0.40-0.55 × Cx 170-200 m/s. 98 of 240 designs are feasible.
2. **Fielded turbine re-designed by TurboFlow** at the fielded cycle (350 MPa, envelope cap).
3. **Engine and airframe:** θ-scaled combustor, engine_mass, 3R calibration, Phase 2 airframe drag.
4. **Worst corner:** η_c × 0.66/0.70, combustor +1σ, pessimistic drag.

### F3A.2 Results (fielded; best blading at each speed; `data/phase3ax_trade.csv`)

| rpm / stages | tool η of blading | rotor-1 M_rel | turbine tip (on the limit) | L | dry mass cal. | margin nom / pess | worst | TOGW |
|---|---|---|---|---|---|---|---|---|
| 70k / 8 | 0.832 | 1.13 | 65.5 mm | 714 mm | 6.41 kg | +104 / +88 % | +71 % | 18.03 kg |
| 75k / 7 | 0.832 | 1.20 | 61.1 mm | 651 mm | 5.64 kg | +104 / +88 % | +71 % | 17.27 kg |
| **80k / 6** | 0.832 | 1.27 | 57.3 mm | **599 mm** | **5.02 kg** | **+104 / +89 %** | **+71 %** | **16.65 kg** |
| 85k / 6 | 0.827 | 1.32 | 53.9 mm | 593 mm | 4.83 kg | +104 / +89 % | +71 % | 16.46 kg |

* Fielded airflow 1.360 kg/s (was 1.314), TSFC 0.159 kg/(N h).
* Every case is combustor-set at **OD 142.5 mm**, so drag and margins are equal.
* TurboFlow flags the 75k turbine `success=False` at a point on its stress limit to 1e-9 mm (known quirk, tools_survey
  section 8).

### D3A.2 Refreshed baseline: 80 000 rpm, 6 stages, hub/tip 0.40, Cx 200 m/s
* **Why:**
  * margins are equal across the grid, so length and mass decide;
  * 80k is 51 mm shorter and 0.62 kg lighter than 75k;
  * 85k saves only 0.19 kg (1 % of TOGW, inside the ±5 % mass calibration band), but takes rotor-1 to M_rel 1.32 of
    the 1.35 limit, raises bearing DN by 6 %, and has had no rotor-dynamics check.
* Same speed and stage count as the Phase 3/4 baseline.
* **Against Phase 3:** mass 5.74 → 5.02 kg (the turbine re-design), length 611 → 599 mm, OD 142 → 142.5 mm, dash margin
  unchanged.

### F3A.3 Validation attempt for R4.1 (published small-axial test data)
* **NASA-CR-134827** (AiResearch 1976, scaled single-stage transonic axial, 70-110 % speed): tip clearance 1.0 → 2.2 % of
  blade height, both with casing treatment, cost 5.7 − 3.5 = 2.2 efficiency points, ≈ 1.8 points per 1 %. The model
  uses 2.0 points per 1 %, which is consistent.
  * The same test: stall margin 12.8 → 8.7 %. **The stacking model has no clearance effect on stall**; noted for
    operability.
* **NACA TR-758** (8-stage axial, 1943): has speed lines at 5 000-14 000 rpm and stage-by-stage pressures. The text layer
  gives geometry and summary numbers, but the characteristics are scanned figures. A multistage part-speed benchmark of
  the stacking model is possible, but needs the geometry rebuilt and the figures digitised; the machine is large,
  subsonic and lightly loaded. **Not run**; offered as an option at the freeze.
* NASA-TM-106999 (small 2-stage rig, 1995): inlet calibration only, no maps.
* **R4.1 stays open.** Only the clearance sensitivity is supported by data.

### F4A.1 Rotor stress screening (`ax_rotor_stress.py`, 80k blading, MCS 105 %, Ti-6Al-4V Fty 620 / Ftu 681 MPa)
* **Verification:** the rotating-beam FE reproduces the static cantilever (3.5160 / 22.0345) exactly and Wright et al.
  (1982) at speed parameters 1 and 2 (3.6816 / 4.1373) to 0.001 %.
* **Blade roots:** centrifugal + gas bending on a biconvex section, × Kt 1.4.
  * The mass model's constant-section stage-1 blade fails: 677 MPa. U_tip at MCS is 461 m/s.
  * **A 10 % thickness taper** (root 1.65 / tip 1.35 mm, same mass) gives 598 MPa (96 % of Fty). Stage 2 is at 597 MPa
    (96 %); stages 3-6 are at 523-550 MPa.
  * The taper is provisional geometry.
* **Discs:** the mass model's 450 MPa constant-stress discs give a burst ratio of 1.08 at MCS, failing the ≥ 1.20
  criterion used for the impeller. Re-sized to 365 MPa at design speed (402 MPa at MCS), which gives 1.20. Mass
  **+0.009 kg**: the 4 mm minimum rim governs these small discs.
* **Blade vibration** (1F / 2F with centrifugal stiffening, taper included): low-engine-order crossings in the likely
  operating range:
  * stage 1: 1F × 2E at 61 %;
  * stage 2: 1F × 2E at 79 %;
  * stage 4: 1F × 3E at 60 %;
  * stage 5: 1F × 3E at 76 %;
  * **stage 6: 1F × 3E at 95 %**, near maximum speed.

  Vane-passing crossings are only with 2F, at 40-43 %. Carried as an open risk; no retuning done.

### F4A.2 Three model problems found running the operability chain on the refreshed design (fixed; Phase 4 results unchanged)
1. **Wrong triangles for a blading sized at a set efficiency.**
   * `axial_offdesign.Compressor` rebuilt the TurboDesigner triangles at the loss-model efficiency (0.832). The 3A-R
     blading was sized at 0.709.
   * Fix: rebuild at `eta_sizing` when present. Phase 3 designs lack the key; the Phase 3 regression is unchanged
     (PR 5.031, η 0.831).
2. **Tool-level losses on a fielded-work blading.**
   * The stacking design point over-delivered PR, which put the design in the wrong place on its own map.
   * Scaling the WHOLE row loss to the fielded efficiency (stage η −0.103) instead doubled the incidence parabola:
     every flow choked below 80 % speed (row losses so large that the exit could not pass any flow). That is a model
     artefact.
   * **Adopted (`axial_offdesign.fielded`):** stage losses calibrated so the design point gives the fielded 0.709 and
     PR 5.09 at the design flow. Off design, only the tool-level (Howell) part follows the incidence parabola; the
     fielded debit (clearance / Re / finish-type) is a **constant extra loss** (ΔY 0.054-0.058 per row).
   * Howell stall is unchanged (deflection-based).
   * Result: lines at all speeds; design SMN to the peak line ~14 %, as in Phase 4. Rotor 1 is past Howell's stalling
     deflection along the whole line below 85-90 % speed, as Phase 4 found.
3. **pyCycle off-design start.**
   * `cycle_model.set_design` seeds every off-design point with W 2.0 lbm/s, FAR 0.018, turbine PR 2.0. At η_c 0.730
     (Phase 4) that converges; at 0.709 (W 3.0 lbm/s, turbine PR 2.64) Newton diverged to NaN at every point. The
     Phase 4 maps gave the same failure at 0.709 and converged at 0.730, so the maps are not the cause.
   * **Fix:** `cycle_model.seed_od_from_design` copies every implicit state from the design point (map balances from
     the design map location) and re-solves. The off-design point is then marched from the design flight condition.
   * Verified: the off-design point reproduces the design (500 N, 1150 K); SLS 100 % gives 686 N at T4 1169 K.
   * Not used by any Phase 3 / 4 script.

### D4A.1 Operability: combined variable geometry (option A) sized (`ax_operability.py`, `ax_operability_summary.py`)
* **Criteria (Phase 4):** a steady point is acceptable if converged, T4 ≤ 1150 K, no row beyond its Howell stalling
  deflection, and SM to the peak line ≥ 10 % (the transient half of ~20 %). Idle = the lowest speed from which every
  point up to the T4-limited maximum-throttle speed is acceptable.
* **Scheduling corrections during the search** (first batches wasted, recorded):
  * **Bleed and nozzle opening at 95 % speed.** The Phase 4 setting (90 %) acts below the first fixed-geometry failure
    (92.5 %, SM 9.2 %).
  * **VIGV as a scheduled closure** (design swirl at ≥ 95 %, closing linearly by Δ at 60 %). The Phase 4
    stall-index-driven schedule never closed the IGV here, because the binding limit is the surge-surrogate margin.
* **Results at SLS** (max throttle 97.5-98.7 % in every configuration, T4-limited):

  | configuration | idle | idle thrust | idle fuel | limit below idle |
  |---|---|---|---|---|
  | fixed geometry | 95 % | 573 N | 20.3 g/s | SM 9.2 % |
  | 10 % bleed | 87.5 % | 396 N | 16.7 g/s | SM 9.4 % |
  | nozzle ×1.6 | 92.5 % | 500 N | 18.2 g/s | SM 8.4 % |
  | VIGV 15-30° + 10 % bleed | 85 % | 338-348 N | 14.9-15.3 g/s | SM, stator 1 |
  | VIGV 15-30° + 10 % bleed + nozzle ×1.6 (at 40 %) | 80 % | 222-231 N | 11.8-12.2 g/s | SM 7.7-8.9 % |
  | **VIGV 15° + 10 % bleed + nozzle ×2.0, fully open at 80 %** | **77.5 %** | **114 N** | **10.0 g/s** | **stator-1 stall at 75 %** |
  | 15-20 % bleed (any) | none below 97.5 % | | | T4 1159-1207 K at 95 % |

  * At SM ≥ 5 % the best idle is still 77.5 %, with stator-1 stall binding. The VIGV unloads rotor 1 and loads stator 1,
    as Phase 4 found.
  * Nozzle ×2.5 gives 77.5 % / 91 N.
* **Adopted:**
  * VIGV 15° closure (stage-1 swirl 22.4° → 28.7° at idle);
  * 10 % overboard bleed after stage 3, open ≤ 95 % speed;
  * variable nozzle to 2.0 × A8 by 80 % speed.
* **Idle 77.5 % speed:** SM 11.9 %, T4 878 K, 114 N, idle fuel 41 % of the 100 % SLS fuel flow (the centrifugal: ~19 %).
* **Dash line** (VIGV scheduled, bleed closed, nozzle design): acceptable from 100 % down to 87.5 % speed (184 N);
  rotor 1 stalls below.
  * Dash cruise needs ~245 N (throttle 49 %): 90 % speed, SM 12 %, no bleed.
  * The engine cannot be throttled below ~184 N at M 1.02 without the bleed (not analysed).

### F4A.3 Idle thrust makes a powered idle approach impossible
* Approach drag (Phase 2 airframe model, 14-16 kg, M 0.12-0.20): **15-21 N** (L/D 7.5-9).
* Idle thrust: 114 N static (≈ 100 N net in flight after ram drag), **5-6 × the approach drag**; 231 N with the nozzle at
  1.16.
* A conventional descent / approach at idle is not possible. The engine must be **shut down at the top of descent**
  (glide from 5 km at L/D 7-9, dead-stick landing with flaps and the 0.6 m chute), or a thrust spoiler / reverser /
  large airbrake added (not assessed).

### D4A.2 Rotor (`ax_rotor.py`, verified ROSS model; idle 80 % for the assessment)
* The mass-sized Phase 3 rotor passes at 2 of 6 support settings: its bending mode (57-61 krpm, 71-77 % speed) now lies
  below idle. Not robust.
* The stiffened rotor passes at all 24 settings.
* **Adopted:** layout A, 2 mm Ti drum, 24 / 12 mm AISI 4340 shaft, **12 mm journals (DN 1.01e6 at MCS: R4.R2 largely
  resolved)**, supports k 1.75e6 N/m / c 876 N s/m.
  * Criticals 2.8 / 12.4 (AF 2.0) / 19.6 (1.3) / 39.9 (1.2) krpm, all below idle and critically damped; 122.3 krpm
    (46 % above MCS).
  * Rotor 1.60 kg (mass-sized 1.10), Ip 8e-4 kg m².

### D4A.3 Phase 2 ↔ 4 closure (`ax_mission.py`, `ax_closure.py`)
* **Deck:** stacking map with the VIGV schedule, fielded TurboFlow turbine map.
  * SLS max 659 N at 98.7 % (T4-limited, SM 10.5 %).
  * Dash 500 N at 100 %, SM 13.9 %.
* **Engine:** 5.02 → **6.86 kg** calibrated (6.50-7.22), L 599 mm, OD 142.5 mm (combustor-set; liner 157 mm,
  U_ref 29.8 m/s).
  * Raw changes: shaft 24 / 12 (0.95 kg raw), drum 2 mm (0.26), discs +0.009.
  * Variable geometry 0.64 kg raw (geometric estimates + 3 × 75 g servos; not sourced from a fielded design):
    VIGV 0.165, bleed 0.122, nozzle 0.354.
* **Closure with the mission model's powered idle descent:** fuel **5.46 kg**, **TOGW 22.12 kg**, margin 2.88 kg.
  * Dash margin +103 / +88 %; time to dash 29.1 s; ground roll 54 m; landing 177 m (flaps + chute).
  * About 4.5 kg of the fuel is idle-related: the 235 s descent from 5 km, the pattern, and the 120 s reserve, all at
    41 % of max fuel flow. That descent is inconsistent with F4A.3.
* **Engine-off descent variant** (engine shut down at the top of descent, reserve 120 s at idle fuel flow kept): fuel
  **1.88 kg, TOGW 18.54 kg, margin 6.46 kg**, dash margins unchanged.
  * Not a like-for-like comparison with the centrifugal (20.09 kg, flown with a powered descent at its ~19 % idle).

### D4A.4 Acceleration (`ax_transient.py`, `data/phase4ax/accel_<tag>.csv|json`)
* **Method** as `cc_transient.py`:
  * pyCycle NT4 (speed and T4 imposed);
  * VIGV / bleed / nozzle on their schedules;
  * usable excess power under T4 ≤ 1150 K, no Howell stall, SM ≥ 5 % or 10 % to the peak line;
  * dN/dt = P / (I_p ω) with I_p 8.07e-4 kg m² (D4A.2 rotor).
* **Solver fixes needed:**
  * first run: T4 stepped 1150 → 700 K in one jump diverged, and the diverged state poisoned every later point, so no
    speed had a converged point;
  * second run: stepping T4 down from 1150 K in 15 K steps reproduced 80-98.5 %, but still found nothing at 77.5 %;
  * final: speed is marched along the steady line with T4 imposed at its steady value, then T4 is swept up from
    there, and `solve()` restores the last converged output vector after any failure.
  * The excess powers of the second and final runs agree at 80-98.5 % (e.g. 29.28 kW at 90 %).
* **Check:** imposing the steady-line T4 of the N-mode operability run gives a net shaft power of 0.0 kW at every speed
  from 77.5 to 97.5 %.
* **Result (SLS), idle 77.5 % → 98.5 %:** **1.73 s** at SM ≥ 5 %, **2.25 s** at SM ≥ 10 %. Of that, 95 → 98.5 % takes
  1.09 s, because the steady T4 is within 4-25 K of the limit there. At idle with a 10 % reserve only 2.2 kW is usable.
* **Why it is fast:** light rotor (38 % of the centrifugal's Ip) and a short speed span (10.5 kJ of rotor kinetic
  energy). The centrifugal takes 6.6 s from 40 % to 95 %.
* **Not modelled:** actuator rates (the VG is assumed to follow its schedule instantly), the transient when the bleed
  closes at 95 %, fuel-control and heat-soak dynamics, deceleration. The margins are measured against the unvalidated
  surrogate (R4.1).

### D5A.1 Axial freeze snapshot issued; paused for the user's review
* **Documents:**
  * `docs/phase4a_axial.md`: Phase 3A-R / 4A report, with plots `plots/phase4a_operability.png` and
    `plots/phase4a_blade_campbell.png` (`ax_plots.py`);
  * `docs/design_freeze_axial.md`: architecture, closure for both descent concepts, rotor dynamics, open risks,
    Phase 6 starting point, reviewer decisions, and a centrifugal vs axial comparison.
* **Open risks stated, none resolved:**
  * R4.1, the unvalidated axial model (top risk);
  * idle 77.5 %, which forces an engine-off descent (relight and go-around not assessed);
  * start not analysed (below 70 % the model has no steady match);
  * unsourced variable-geometry hardware;
  * dash throttling below 184 N needs the bleed;
  * blade roots at 96 % of Fty;
  * five low-order blade resonances;
  * transient quasi-steady only;
  * no hardware validation;
  * others as carried.
* **Decisions put to the user:**
  1. centrifugal or axial;
  2. the descent concept (engine-off, or a spoiler / reverser assessment);
  3. the NACA TR-758 benchmark;
  4. a like-for-like centrifugal closure with an engine-off descent;
  5. axial Phase 6.
* **No axial CAD started. The centrifugal baseline and its Phase 6 work are unchanged.**

---

## Phase 6A (AXIAL OPTION, EXPLORATORY) — packaging and mass CAD (2026-09-15)

> **Scope banner.** This section is a **separate, exploratory branch on the axial option**
> (`ax80000_opr5_t1150_n6_cap_3r`). It is **not** part of the centrifugal Phase 6 work above, it is **not a build
> release**, and it is **not an architecture decision**: the centrifugal remains the baseline, its Phase 6 status is
> unchanged and still held, and freeze decisions 1-5 of `docs/design_freeze_axial.md` remain open. Phase 6A was run on
> the user's instruction to resolve as much of axial **open risk 4.4 (unsourced variable-geometry hardware)** as
> geometry and mass can, and to test whether the shaft, bearings, bleed ducting and VIGV actuation ring fit inside the
> 142.45 mm engine OD. Scope was packaging and mass only: no manufacturing drawings, no tolerancing, no blade aero
> surfaces. **R4.1 and the other axial open risks are untouched.**
> Report: `docs/phase6a_axial_cad.md`.

### D6A.1 Toolchain and scope confirmed by the user
* **CadQuery 2.8 / OCCT 7.9 in `.venv-cad`** (user choice over FreeCAD): already the Phase 6 stack, `cadlib.py`
  helpers reused, volume-checked booleans, direct mass properties, STEP export, no fourth environment.
* User also confirmed: actuators to be selected from **real published datasheets** (web-sourced, cited), and the
  **bleed discharge path modelled only to the engine OD** (no airframe routing).
* Geometry source rule set by the user and followed: **per-stage numbers, no scaling, no even spacing.** Stages come
  one by one from `data/phase3ax/axt_<tag>.json` `levels.fielded.comp.stages`; the axial stack-up uses the
  compressor's own rule (`axial_design.py:41`, `row_gap_to_chord = stage_gap_to_chord = 0.25`); disc, bearing and
  turbine stations come from `rotor_model.geometry()`, so CAD and rotor model share one layout. Stage pitch runs
  51.6 / 40.7 / 33.1 / 27.6 / 23.4 mm: even spacing would have misplaced the rear stages by ~26 mm.
* New files: `scripts/phase6a_axial_cad/{make_params_axial,ax_flowpath_check,ax_engine_cad,ax_vg_cad,ax_clash,ax_mass_compare}.py`,
  `data/phase6a/*`, `cad/axial/*`. **Nothing under `data/phase3ax`, `data/phase4ax`, `data/phase6` or `cad/engine` was
  modified.**

### A6A.1 Variable-geometry actuation loads (first-order, stated relations)
* **VIGV**: cascade lift `CL = 2 (s/c) cos a_m tan a2` at the 22.4 deg design swirl, q 19.4 kPa at the compressor
  face -> 8.6 N per vane, hinge moment 24.6 N mm per vane (centre of pressure 0.15 c aft of a 0.30 c spindle, bushing
  friction mu 0.2), **unison-ring force 57 N**, stroke 1.57 mm.
* **Bleed**: choked port area 3.34 cm2 (10 % of 1.360 kg/s at 257 kPa / 433 K, Cd 0.8), seal force 68 N,
  **band torque 1.02 N m** (mu 0.3 at r 50.0 mm).
* **Nozzle**: mean flap inner static 82 kPa against 54 kPa ambient -> 56 N per flap, and the linkage-independent
  invariants **27.0 N m total hinge moment over 14.1 deg = 6.7 J of work**. The modelled linkage turns that into
  729 N at the sync ring over 33.9 mm.
* These are conceptual relations, not a validated actuation analysis.

### D6A.2 Actuators selected from datasheets; the nozzle has no compliant part (F6A.1)
`data/phase6a/actuators.json`, transcribed and cited.
* **VIGV: Volz DA 22-12-2615**, 105 g, rated 0.80 N m. Demand 0.285 N m on a 5 mm arm, 18.3 deg travel:
  **36 % utilised, compliant**; ~16 deg C at the compressor face, inside the -30..+70 C rating.
* **Bleed: Volz DA 22-12-2615**, 105 g. Demand 0.51 N m through a 2:1 crank: torque compliant (64 %), but the
  stage-3 manifold is at **433 K (160 C) against a +70 C rating** - **not compliant on temperature**; a thermal
  standoff is required and was not designed.
* **Variable nozzle: NOT COMPLIANT.** Holding 27.0 N m on the DA 22-12-4112's 1.20 N m rated torque needs a
  **22.5:1 reduction**, giving 317 deg of servo travel (reachable only with the optional 330 deg version) and
  requiring a screwjack/gear stage that **is not in the freeze's 0.279 kg estimate**. On peak torque (3.00 N m) a
  9:1 bellcrank holds it with zero margin. It also sits beside a **937 K** jet against a +70 C rating. The alternative
  (Actuonix P16-50-256, 95 g, self-locking) is worse: 300 N lift / 500 N static against 729 N, and -10..+50 C.
* Sources: Volz DA 22 Technical Specification Rev D (02/2016); Actuonix P16 datasheet Rev B (2016).

### F6A.2 The actuation hardware does not fit inside the 142.45 mm OD (R6A.1)
Boolean-confirmed, `data/phase6a/clash_report.json`. The compressor casing is 110.26 mm OD and the engine OD is
142.45 mm, so the variable geometry has a **16.10 mm radial annulus** (free: `engine_mass` puts sheet metal only over
the hot section). **The smallest dimension of a Volz DA 22 case is 22.0 mm.**

| part | r_max | over the OD | volume outside |
|---|---|---|---|
| nozzle actuator | 127.10 mm | **+55.87 mm** | 81 531 mm3 |
| nozzle reduction stage | 104.91 mm | +33.68 mm | 30 000 mm3 |
| nozzle pushrods | 93.36 mm | +22.14 mm | 1 402 mm3 |
| VIGV actuator | 82.48 mm | **+11.25 mm** | 21 850 mm3 |
| nozzle sync ring | 78.83 mm | +7.61 mm | 7 825 mm3 |
| VIGV cranks | 78.38 mm | +7.15 mm | 601 mm3 |
| bleed actuator | 76.56 mm | **+5.33 mm** | 4 591 mm3 |
| VIGV spindles | 72.38 mm | +1.15 mm | 114 mm3 |

The sync ring is outside before any actuator is added: `ax_closure` sizes it at r8_max + 10 mm = 76.83 mm.
**What does fit:** shaft (1.00 mm to the tunnel), tunnel (7.79 mm to the inner liner), **front bearing 28 mm OD inside
the 20.30 mm inlet hub with 6.30 mm clear** (housing 3.30 mm), the whole bleed manifold / valve / full-area collector
duct (reaching exactly the OD line), the VIGV unison ring (9.25 mm clear of the casing), and the flaps at both stops
(0.07 mm inside the OD at fully open). Fix options (local fairing, which changes the airframe cross-section and hence
the wave drag the dash margin rests on, or remote mounting with long pushrods) are **not assessed**.

### F6A.3 The engine is at least 42.5 mm longer once the mechanisms are packaged (R6A.2)
The VIGV row (chord 17.11 mm + the 0.25-chord gap) does not fit in the 15 mm front allowance: it starts **6.38 mm
ahead** of the compressor front face, its actuator 24.75 mm ahead. The nozzle flaps end 28.1 mm **aft** of the raw
length, the actuator and heat shield 36.1 mm aft. Packaged raw length >= **537.6 mm against the frozen 495.1 mm
(+8.6 %)**; the frozen 598.7 mm calibrated length has no allowance at either end.

### F6A.4 The rotordynamic drum geometry is not buildable as modelled (R6A.4)
D4A.2 used a **2 mm Ti drum at a constant r 26.23 mm** (`ax_closure`'s mean of the rotor hub radii). The hub line
rises 20.30 -> 30.19 mm, so the drum (outer radius 27.23 mm) stands **6.93 / 5.79 / 3.50 / 2.73 / 1.11 / 0.56 mm into
the flow path** at the stage-1 rotor through the stage-3 stator, intersecting those stator vanes and inner bands and
swallowing part of the stage-1/2 rotor blade roots. A buildable drum must follow the hub line, which changes its
bending stiffness. **This does not say the API 684 pass is wrong and it is not re-opened here**: the 122.3 krpm
bending critical (46 % above MCS) should be re-run on a hub-following drum before it is relied on.

### F6A.5 The drawn hot end has its minimum area at the turbine exit, not at the nozzle (R6A.5)
`ax_flowpath_check.py`, area/choking capacity at every drawn station.
* **Method verified first:** the choking relation reproduces pyCycle's own A8 sizing to **-0.6 %**.
* Compressor rows: +17.5 % to +56.2 % capacity margin, comfortable everywhere.
* **Turbine exit annulus 66.02 cm2 vs nozzle A8 70.16 cm2 (A8/A = 1.063)**: at the fielded Pt5 151.4 kPa the annulus
  chokes at **1.292 kg/s against the 1.381 kg/s required (-6.5 %)**.
* **Traced cause:** `arch_trade.turb_pout` assumes an **exit Mach of 0.45** to convert the cycle's Pt5 into the static
  pressure handed to TurboFlow. TurboFlow met that static pressure but left the flow at **408 m/s, -19.5 deg swirl,
  M ~ 0.71**, so its own exit total pressure is **184.0 kPa**, not 151.4 kPa. The annulus is sized for the tool-level
  machine (eta_tt 0.917) while the cycle runs the fielded one (eta_t 0.75). The same tool-vs-fielded mismatch as
  F3R.3 and F4A.2, this time as an area.
* **Consequence:** at high speed the controlling area is upstream of the flaps, so the variable nozzle has less
  authority over the running line than `ax_operability` assumed. How much less is **not assessed**.
* **Not fixed and not re-run.** Reported only.

### F6A.6 CAD mass: the core model holds, the variable geometry is 1.76 x its allowance (R6A.3, R6A.6)
Compared against the **raw** bottom-up items (the x1.2025 calibration covers what the CAD does not draw).
* **Core:** blades -3.0 %, discs -3.1 %, stators -3.4 %, liners -0.4 %, hot casing -0.4 %, turbine disc and NGV rings
  exact. Core CAD 4.154 kg vs 4.289 kg of model items, **-3.1 %**.
* **Two core discrepancies, opposite in sign:** the shaft is **+106 g** (the model's `L_shaft = 0.72 x L_total` gives
  356 mm; the layout needs 434 mm), and the tunnel + bearing housings are **-201 g** (the model's flat +0.12 kg
  housing allowance is the more realistic of the two; the CAD housings are thin placeholders). Bearings +13 g (the CAD
  draws solid rings).
* **`engine_mass` double count:** `ngv_rings` and `turbine_shroud` occupy the same space (8 441 mm3 common volume),
  about 67 g of IN-713LC counted twice.
* **Variable geometry (the point of Phase 6A):**

| system | freeze allowance | CAD | delta | ratio |
|---|---|---|---|---|
| VIGV | 165 g | 232 g | +66 g | 1.40 |
| bleed | 122 g | 200 g | +79 g | 1.65 |
| variable nozzle | 354 g | 695 g | **+342 g** | 1.97 |
| **total** | **640 g** | **1127 g** | **+487 g** | **1.76** |

Of the +487 g: **+248 g is hardware the freeze's estimate did not contain at all** (nozzle heat shield 165 g, the
22.5:1 reduction stage 83 g), +117 g is real actuators against 3 x 75 g, +52 g brackets, +18 g bleed duct. The heat
shield is drawn as a full ring, so the nozzle figure is the softest of the three; the actuator masses are datasheet
values and are firm.
* **For scale only, not carried through and no re-closure run:** calibrated dry mass would go 6.863 -> 7.449 kg
  (+586 g), TOGW 22.12 -> 22.71 kg (margin 2.29 kg) in the powered-descent case and 18.54 -> 19.13 kg (margin
  5.87 kg) in the engine-off case. Both stay under 25 kg.

### D6A.3 Status after Phase 6A
* **Partly resolved:** axial open risk 4.4 is no longer "no sourced hardware" - the VIGV and bleed actuators have a
  named in-production part with torque margin, and the variable-geometry mass is a CAD number.
* **Still open inside 4.4:** no compliant nozzle actuator exists at this load and temperature; the bleed actuator is
  outside its temperature rating; actuator rates were not checked against the transient assumption (freeze 4.7); no
  ECU, failure modes, or discharge path beyond the engine OD.
* **New open risks: R6A.1-R6A.6** (packaging, length, no nozzle actuator, drum geometry, turbine-exit area, minor
  `engine_mass` items), listed in `docs/phase6a_axial_cad.md` section 7.
* **Untouched:** R4.1 and everything downstream, idle 77.5 % and the descent concept, start, dash throttling, blade
  roots and resonances, no hardware validation.
* **No architecture decision taken. The centrifugal baseline and its Phase 6 work are unchanged. Freeze decisions 1-5
  remain with the user.**

## Housekeeping — repository split (2026-09-15)

### D0.1 Axial work quarantined under `axial/` (user instruction)
User request: "reorganize folder structure to separate axial work and centrifugal one because later we will continue
the development of centrifugal compressor staged jet engine, I don't want the axial data to mess with it." Structure
and legacy placement chosen by the user from two options each: **quarantine the axial side only** (the centrifugal
files keep their exact paths, so the chain that continues cannot be disturbed) and **superseded option-B work goes
into the axial tree** rather than a separate `legacy/`.

**No engineering result changed.** Only file locations, the paths that address them, and the two small
path-plumbing fixes recorded in F0.3 below. No model, correlation, tolerance or numerical setting was touched.

Moved to `axial/` (`git mv`, history preserved):

| from | to | what |
|---|---|---|
| `scripts/phase3_cycle/{ax_trade,axial_sweep,axicent_sensitivity}.py` | `axial/scripts/phase3_cycle/` | 3 scripts |
| `scripts/phase4_turbomachinery/{ax_*,operability,accel,bleed_sweep,nozzle_sweep,running_line_axi5,plot_operability,axial_blockage_screen,check_turbodesigner_blockage,ac_operability,impeller_check_ac,plot_optionB}.py` | `axial/scripts/phase4_turbomachinery/` | 19 scripts |
| `scripts/phase6a_axial_cad/` | `axial/scripts/phase6a_axial_cad/` | 6 scripts |
| `data/{phase3ax,phase4ax,phase6a}/`, `data/phase3ax_trade.csv` | `axial/data/` | Phase 3A-R / 4A / 6A results |
| `data/phase4/` axial + option-B maps and parts | `axial/data/phase4/` | TurboFlow maps |
| `data/phase4_{running_line,operability_ax,bleed_sweep,nozzle_sweep,axial_blockage_screen,optionB_impeller,rotordynamics*}.*`, `data/phase3_axicent_*.csv` | `axial/data/` | loose axial results |
| `docs/{phase4a_axial,design_freeze_axial,phase4_operability,phase4_rotordynamics,phase4_optionB_checks,phase6a_axial_cad}.md` | `axial/docs/` | 6 reports |
| `plots/{phase4a_*,phase4_operability,phase4_optionB_operability,phase4_campbell,phase4_critical_speed_map,phase4_rotor_*}.png` | `axial/plots/` | 9 figures |
| `cad/axial/` | `axial/cad/parts/` | 67 STEP solids |
| `cad/axial_{core,vg}_assembly.step` | `axial/cad/` | 2 assemblies |

### F0.1 Five axial-named modules could not move — the centrifugal chain imports them
Established with an AST import closure over both trees, not by name. `arch_trade.py` — which `cc_trade.py` is built
on — imports `axial_design` and `axicent_design` at module level; `cc_mission.py` and `cc_benchmark.py` import
`ac_offdesign` (for `PureCC` and `CentrifugalMap`: the **pure centrifugal** off-design model lives in that file),
`axial_map` (for `build_compressor_lines` / `compressor_mapdata` / `turbine_mapdata`, which are generic map → pyCycle
helpers, not axial-specific) and `axial_offdesign` (for the `Choked` exception). `cc_rotor.py` imports `rotor_model`,
`rotordynamics` and `rotordynamics_damped`. All of these therefore stayed in `scripts/`; the table is in `CLAUDE.md`.
Their axial `__main__` studies now write to `axial/data/` and `axial/plots/` via an added `AXROOT`, so no axial number
is produced at the root.

### A0.1 `data/phase3/` and `data/phase3_arch_trade_*.csv` kept at the root, intact
They are the Phase 3 architecture-trade record — both architectures compared in one table — and are read by
`arch_trade.py`, `compile_trade.py`, `reeval_level.py`, `rotor_model.py` and `axial_offdesign.py`. Splitting them would
have broken the shared Phase 3 path for no gain: they are superseded for design use by `data/phase3r/` (centrifugal)
and `axial/data/phase3ax/` (axial). The pre-Phase-3R JetCat P400 benchmark maps likewise stayed in `data/phase4/`,
which `cc_benchmark.py` defaults to.

### D0.2 How the moved scripts address files
Each moved script keeps `ROOT` meaning the repo root and gains `AXROOT` = `axial/`. Shared modules and shared data are
still reached through `ROOT` (nothing was duplicated); every axial artefact is read and written through `AXROOT`. Each
moved script also inserts its original shared directory on `sys.path`, so its imports resolve exactly as before.

### F0.3 Two things the move broke, found and fixed
Both were silent — they only bite on a regeneration path, so neither showed up in a plotting or summary run.

1. **`turbine_map.py` launched by absolute `HERE`.** `ax_operability.py` and `operability.py` regenerate a missing
   turbine map with `subprocess.run([NP1, os.path.join(HERE, "turbine_map.py"), ...])`. `HERE` is now the axial
   directory, but `turbine_map.py` stayed in the shared tree (it serves both architectures). Both call sites now use
   `os.path.join(ROOT, "scripts", "phase4_turbomachinery", "turbine_map.py")`.
2. **`P3_DATA` could only name a directory under `data/`.** `ax_trade.py` sets `P3_DATA=phase3ax` and `arch_trade.py`
   built `OUT = ROOT/data/<P3_DATA>`, so an axial run would have recreated `data/phase3ax/` in the shared tree — the
   exact contamination this reorganisation removes. `arch_trade.py` and `cc_benchmark.py` now accept an **absolute**
   `P3_DATA` and use it as given, a bare name still resolving under `data/` as before; `ax_trade.py` passes the
   absolute `axial/data/phase3ax`. Checked both ways: `P3_DATA=phase3r` → `data/phase3r`, absolute → `axial/data/phase3ax`.

### F0.2 Verification that nothing broke
* `compileall` over `scripts/` and `axial/scripts/`: clean.
* Static import-resolution check over all 112 scripts (evaluates each script's own `HERE`/`ROOT`/`AXROOT` and
  `sys.path.insert` lines, then resolves every repo-local import against that path): every import resolves.
* Import smoke of the centrifugal chain modules (`arch_trade`, `ac_offdesign`, `axial_map`, `axial_offdesign`,
  `rotor_model`, `rotordynamics`, `rotordynamics_damped`, `engine_mass`, `cycle_model`, `impeller_stress`): OK.
* `verify_axisym_fe.py`: sigma_t(center) +0.00 %, sigma_t(rim) +0.35 %, bore case -0.44 % — unchanged.
* `rotordynamics_verify.py` (exercises the two edited shared modules): ROSS 2.3.0 vs closed forms, errors
  0.0001-0.20 % — unchanged.
* `impeller_stress.py` regression against the Phase 4 gate: 3.5 mm root at 100 % speed 656 MPa vs gate 656 MPa — unchanged.
* Moved axial scripts run end to end on the relocated data: `plot_operability.py` and `plot_optionB.py` (the
  latter reads both moved axial results and the P400 benchmark that stayed at the root) regenerate their figures
  into `axial/plots/`, and `ax_operability_summary.py` reproduces its per-configuration idle table.
* `plots/` at the root now contains no axial figure, and `docs/` no axial report.

The full centrifugal solver chain (`cc_trade`, `cc_mission`, `cc_benchmark`) was not re-run end to end: none of its
files were edited, and the reproduction targets (centrifugal dash W 1.32575 kg/s, TSFC 0.16416) are unchanged by a
file move. Re-run them before the next Phase 6 step if a fresh baseline is wanted.

## Phase 7 — Afterburner (2026-09-15)

Report: `docs/phase7_afterburner.md`. Scripts `scripts/phase7_afterburner/`, data `data/phase7/`,
figures `plots/phase7_*.png`. **Nothing in the freeze, in Phase 6 CAD, or under `axial/` was changed.**

### D7.0 Phase 7 started on the user's instruction; purpose and nozzle treatment chosen by the user
User request: "add this design an afterburner". Before any run, a screening calculation was done
(pyCycle prototype reproducing the frozen dash point; overall phi at the dash is **0.244**, so about
76 % of the oxygen leaves the turbine unused) and two load-bearing scope questions were put to the
user, who chose:
1. **purpose — extend the envelope past Mach 1** (over: thrust augmenter on the frozen mission; a
   smaller core behind the afterburner; or studying both);
2. **nozzle — size and compare all three concepts and decide on the numbers** (over: committing to
   a fully variable or a two-position nozzle up front).

### D7.1 The afterburner lives in `cycle_model.py` as an option that is OFF by default
Following the Phase 4 precedent (`comp_bleed`, `nozz_type`), rather than a forked model. New options
`afterburner` (default False) and `ab_mode` ('FAR' = set the added fuel-air ratio, 'T7' = balance it
to an exit temperature), plus `ab_mode_design` so the core is always **sized dry** while an
off-design point runs wet. `read()` gains `eta_ab`; `set_design()` gains `ab_dPqP`, `ab_FAR`, `T7_K`,
each applied only where the point actually has it.

**Verification (`verify_ab_cycle.py`), all passing:**
* **Rayleigh relations** added to `ab_common.py` vs published Rayleigh-flow tables (gamma 1.4),
  Tt/Tt* and Pt/Pt* at M 0.2/0.3/0.5: worst error **2.1e-5**.
* **Regression, afterburner off**: the frozen fielded dash point reproduced — Fn 4.3e-8, W 1.7e-16,
  TSFC 4.3e-8, Tt5/Pt5 < 3e-9, A8 2.3e-9, turbine PR 2.7e-9. CLAUDE.md targets W 1.32575 and
  TSFC 0.16416 met.
* **Null afterburner**: `afterburner=True` with zero AB fuel and zero AB loss equals
  `afterburner=False` to <= 1e-9 on every quantity, Tt7 = Tt5 and Pt7 = Pt5 exactly.
* **Fuel bookkeeping**: pyCycle's tabular `ThermoAdd` references the mix ratio to the incoming
  **dry air** (`thermo/tabular/thermo_add.py`: "for reactant mode, we reference from the incoming
  air"), so a second burner in series accumulates composition. Checked rather than trusted:
  `Wf_ab = W_air x FAR_ab` to 3.5e-16, `FAR_total = FAR_main + FAR_ab` to 1.5e-16. Reading this
  wrong would have corrupted every TSFC in the phase.
* **Energy vs Cantera**: the tabular fuel carries **zero injection enthalpy** in the table's datum,
  so an internal energy balance is vacuous. The heat release is checked against Cantera instead
  (the `cantera_check.py` cross-check extended to a second burn in the vitiated stream):
  **1925.7 K vs pyCycle 1900.0 K, +1.35 %** (main burner was -0.35 % at 1150 K).
* **A8** vs the closed-form choked-throat relation **+0.15 %**; **Fg** vs momentum + pressure with
  Cv debiting the momentum term only (`nozzle.py:117`) **1.2e-6**.
* `smoke_pycycle.py` still passes; the real-map **dry deck reproduces `phase3r_mission_..._deck.csv`
  at 5 km to 0.000 % at all ten Mach numbers** (`ab_envelope.py --regress`).

### A7.1-A7.15 Stated assumptions (none is a tool output)
A7.1 Tt7 = 1900 K. A7.2 eta_AB = 0.90, post-processed on fuel flow as eta_b is. A7.3 AB dry
total-pressure loss — **superseded**: computed from the flameholder blockage relation instead (F7.7).
A7.4 AB duct Mach 0.20. A7.5 petal/plug sheet 0.8 mm. A7.6 12 petals. A7.7 120 C epoxy screening
threshold for skin stagnation temperature (**not** a structural allowable). A7.8 7 deg
equivalent-cone half-angle for an attached diffuser (Idelchik, the source Phase 2 used for the
intake diffuser); 10 and 12 deg swept alongside. A7.9 V-gutter blockage 0.30. A7.10 gutter Cd 1.4.
A7.11 2 gutter rings. A7.12 1200 K sheet Hastelloy-X liner limit. A7.13 igniter 60 g, AB fuel valve
and lines 120 g. A7.14 turbulence intensity u'/U = 0.10 and S_T = S_L + 2u' (Damkohler large-scale,
order-of-magnitude). A7.15 AB fuel system 150 g.

### F7.1 pyCycle's tabular thermo runs out of fuel-air ratio at 0.050, and extrapolates silently
`AIR_JETA_TAB_SPEC` FAR axis: 0 to **0.050**. Stoichiometric Jet-A is 0.068. No error is raised
beyond the edge. **Tt7 ~ 2000 K is the ceiling of the thermodynamic data, not a physical limit.**
The chosen Tt7 1900 K gives FAR_total 0.0460, 8 % inside the edge (A7.1's third justification).

### F7.2 pyCycle's `Combustor` does not model the Rayleigh loss of heat addition
`dPqP` is a fixed fraction applied before the heat addition. Negligible for the main burner at
MN 0.10; in the afterburner at MN 0.20 with a total-temperature ratio of 1.96 the Rayleigh loss is
**2.7 % of Pt**. It is computed in `ab_common.rayleigh_loss` (verified against tables, D7.1) and
handed to the element at every point, recomputed from the point's own AB-duct Mach.

### F7.3 Cantera's n-dodecane mechanism ships two phases; the default one breaks reactors and flames
`nDodecane_Reitz.yaml` default phase is `nDodecane_RK` (Redlich-Kwong), which every reactor and
flame object rejects ("Incompatible phase type 'Redlich-Kwong'"). Use `nDodecane_IG`.
`phase3_cycle/cantera_check.py` works only because `equilibrate()` accepts the RK phase.

### D7.2 Afterburner design point: Tt7 1900 K, duct Mach 0.20 (`ab_design_point.py`)
Core held exactly at the frozen fielded operating point, nozzle throat free, at M 1.02 / 5 km.

| Tt7 K | FAR_total | phi | Fn N | x dry | TSFC | A8 cm2 | A8/A8_dry |
|---|---|---|---|---|---|---|---|
| 971.5 dry | 0.0163 | 0.24 | 500 | 1.00 | 0.1642 | 70.8 | 1.00 |
| 1400 | 0.0289 | 0.43 | 691 | 1.38 | 0.2156 | 89.8 | 1.27 |
| 1700 | 0.0388 | 0.57 | 816 | 1.63 | 0.2467 | 101.3 | 1.43 |
| **1900** | **0.0460** | **0.68** | **896** | **1.79** | **0.2671** | **109.0** | **1.54** |
| 2000 | 0.0498 | 0.73 | 936 | 1.87 | 0.2776 | 112.9 | 1.60 |

**+79 % net thrust for +63 % TSFC.** Gross thrust rises only ~40 % (Vj ~ sqrt(Tt7)); net rises 79 %
because the 434 N of ram drag is already subtracted and does not grow. **The thrust is insensitive
to the eta_AB assumption** (896 N at every eta_AB, by construction of the Tt7 target); only the fuel
moves, TSFC 0.302 to 0.258 across eta_AB 0.75-0.95.

### F7.4 The afterburner duct thermally chokes above about Mach 0.39
Rayleigh flow: the temperature ratio the duct can accept falls with inlet Mach. At Tt7 1900 K the
duct can reach 5743 K at M_ab 0.20, 2862 K at 0.30, 2256 K at 0.35, and **1867 K at 0.40 — below the
1900 K required, i.e. choked.** Computed, not assumed. The chosen duct runs at M_ab 0.20-0.25 over
the whole flight envelope, so the limit is never approached in flight, but it is what stops the duct
being shrunk to save length.

### D7.3 Nozzle schedule: hold the compressor still, and prove it
The wet point is solved at the **dry point's own mechanical speed**, with the throat opened until T4
returns to its dry value. Same speed and same T4 behind a choked NGV is the same compressor point.
An earlier formulation chased the compressor R-line with a secant while also searching the throttle
limit; the N-limit/T4-limit switching made that discontinuous and it failed to converge at most Mach
numbers. **Check: worst compressor R-line shift dry -> wet over the whole envelope is 9.9e-4.**
Surge margin is therefore unchanged by lighting the afterburner at every point — which is the whole
purpose of a variable nozzle, and is why no surge-margin claim is made from this.

### F7.5 The envelope: the afterburner removes thrust as the constraint, and the engine's hot end becomes it
`ab_envelope.py`, real Phase 3R TurboFlow maps, fixed geometry, max throttle, 5 km, 20.09 kg.

| Mach | dry N | wet N | A8/A8_dry | drag A | drag B | turbine-exit margin |
|---|---|---|---|---|---|---|
| 1.02 | 500 | **896** | 1.539 | 326 | 378 | +5.8 % |
| 1.20 | 553 | 1051 | 1.545 | 509 | 509 | +4.3 % |
| 1.30 | 594 | 1160 | 1.544 | 542 | 588 | **+1.2 %** |
| 1.40 | 622 | 1289 | 1.565 | 616 | 671 | **-3.5 %** |
| 1.60 | 718 | 1610 | 1.579 | 777 | 850 | -14.4 % |

| limit | Mach |
|---|---|
| thrust = drag, dry, drag method A / B | 1.42 / 1.31 |
| thrust = drag, with afterburner | never inside M <= 2.0 |
| **turbine exit annulus out of capacity** | **1.33** |
| dynamic pressure = 2 x the frozen dash value | 1.41 |
| stagnation temperature = 120 C | 1.64 |

**The useful answer: about M 1.3, and the afterburner is not what gets you there** — the dry engine
already reaches M 1.31-1.42 against drag. What the afterburner buys is margin: **+174 % thrust margin
at the dash instead of +53 %**, and a supersonic acceleration of 0.22 s instead of 0.66 s.

The turbine-exit margin is **altitude-independent** (+5.7 % at M 1.02 and -3.6 % at M 1.40 at 3, 5,
7, 9 and 11 km alike), because it is set by the compressor match and not by altitude. So M 1.33 is
an envelope-wide cap, not a 5 km one.

**Drag above M 1.05 is outside the Phase 2 model's stated validity** ("subsonic to M 1.05"), so the
top speed is bracketed by two methods (the model as built, and a slender-body wave-drag floor) that
differ by 11 %. Neither contains inlet spillage/additive drag, which is absent from the Phase 2
build-up entirely; the capture stream tube grows 55.1 -> 67.0 cm2 from M 1.02 to 1.6 while pitot
recovery falls 1.000 -> 0.895, so the high-Mach numbers are optimistic by an unquantified amount.

### F7.6 The real turbine exit runs at Mach 0.76, not the cycle's assumed 0.45 — the centrifugal F6A.5
`cycle_model` sets `turb.MN = 0.45` at design. The real annulus from TurboFlow's own geometry is
**75.12 cm2** (hub 36.67, tip 61.12 mm) and at the cycle's Pt5/Tt5 has to run at **M 0.761**, with
17.8 deg of residual swirl. `arch_trade.turb_pout` used the 0.45 assumption to convert the cycle's
Pt5 into the static pressure handed to TurboFlow (130.8 kPa), so the turbine was designed against a
back pressure inconsistent with its own annulus. **This is Phase 6A's F6A.5 repeated on the
centrifugal engine. It is PRE-EXISTING in the frozen design; Phase 7 found it, did not create it,
and did not fix it.** It is the cause of the M 1.33 cap in F7.5.

### F7.7 A fixed nozzle turns +79 % into +9.6 % and halves the surge margin
Real engine on its real maps at the dash point, A8 held fixed:

| A8 scale | dry Fn | dry SM | wet Fn | wet SM |
|---|---|---|---|---|
| 1.00 (sized dry) | 500 N | 0.282 | **548 N** | **0.121** |
| 1.30 | 257 N | 0.467 | 755 N | 0.199 |
| 1.45 | 152 N | 0.531 | 841 N | 0.236 |
| 1.54 (sized wet) | will not run | - | 896 N | 0.282 |

**The variable nozzle is not optional.** A dry-sized fixed nozzle halves the surge margin into the
region open risk 4.1 says cannot be predicted; a wet-sized one destroys the dry engine. This is also
what makes the afterburner's benefit conditional on the nozzle's **transient** behaviour, which was
not analysed (R7.2).

The flameholder blockage relation (dPt/q = Cd B/(1-B)^2, B 0.30, Cd 1.4) gives a dry loss of
**2.2 % of Pt**, which is what A7.3's assumed 2 % was; A7.3 is therefore superseded by a computed
value rather than carried as an assumption.

### D7.4 Nozzle concept: translating plug, chosen on the actuation load
`ab_nozzle_trade.py`. Duty: throat 70.77 -> 111.74 cm2 (D 94.9 -> 119.3 mm), ratio 1.579 over the
whole envelope. Loads are integrated from a quasi-1D internal static-pressure solution along each
moving surface, not assumed.

| | iris (concepts A and B) | translating plug (C) |
|---|---|---|
| travel | 22.63 -> 14.45 deg (8.18 deg) | 51.0 mm stroke |
| worst load | **112.7 N m** hinge moment -> **1198 N** sync-ring force | **123 N** axial |
| mass | 0.557 kg | 0.850 kg |
| sourced actuator | **none compliant**: best rotary (Volz DA 22-12-4112, 1.20 N m) needs a 4.8x reduction; linear P16 needs 3.9x | **Actuonix P16-50-256 at 41 % of rated load**, self-locking |

**9.7x less actuation load decides it.** The iris's 0.29 kg mass advantage disappears into the
reduction stage and heavier actuator it forces — the same trap Phase 6A hit on the axial nozzle
(D6A.2). Concept B (two-position iris) carries the identical 112.7 N m, so it inherits the problem
without solving it. **Both need the actuator mounted forward**: the tailpipe skin is at 698 C and the
jet at 1900 K against +50/+70 C ratings; the only cool site is the compressor casing at 36 C, reached
by a pushrod that is **not designed**. Two unresolved items on the plug: the stroke is 51.0 mm
against the sourced part's 50 mm (2 % over), and the plug's support, cooling and thermal growth on
the centreline of a 1900 K stream are not designed.

### F7.8 Length is the afterburner's real cost, and the diffuser is most of it
The flow leaves the turbine at M 0.76 in 75.12 cm2 and must be diffused before anything can burn.
At the 7 deg attached-diffuser limit the diffuser alone is **270.8 mm at duct Mach 0.20** — 64 % of
the whole 426 mm engine — falling to 155.9 mm at duct Mach 0.30. Burn length is **102.7 mm**.
Packaged engine length **426.2 -> 909.6 mm (+484 mm, +113 %)**.

### F7.9 Flame stabilisation: not autoignition, but blowout is not a constraint either
The first model assumed a 972 K turbine exit would make the afterburner autoignition-stabilised.
Cantera says otherwise: the **autoignition delay of a fresh stoichiometric pocket is 15.8 ms**
against a 0.62 ms recirculation residence time — **Da 0.039**. At 1.45 bar the mixture does not
light itself, so the afterburner needs a flameholder **and an igniter**. Once lit it holds easily:
a well-stirred-reactor blowout search (Longwell & Weiss; **continuation**, see F7.10) gives
**tau_blowout 0.039 ms against 0.62 ms available, Da 15.8**, and a minimum gutter of 1.6 mm against
the 25 mm assumed. Burn length is set by turbulent flame spreading (103 mm), not by autoignition
(which would need 1917 mm).

### F7.10 Two Cantera traps in the stirred-reactor blowout search
* A PSR is **bistable**. Bisecting on residence time from a freshly equilibrated initial state lands
  on the burning branch at every tau and reports no blowout at all. Continuation downwards, each
  solve restarted from the previous burning state, is required.
* Sharing one `Solution` object between the inlet reservoir and the reactor (`clone=False`) makes
  the "fresh" feed **track the reactor**, so the reactor is fed its own hot products and the answer
  is meaningless. Give each object its own `Solution`.
Also **F7.11**: `nDodecane_Reitz.yaml` carries **no gas-phase transport data for c12h26**, so a
laminar flame speed cannot be solved with it at all. The turbulent flame speed used is
S_T ~ 2u' = 24 m/s, turbulence-dominated, so a missing S_L of 1-3 m/s changes the burn length by a
few per cent.

### F7.12 Liner cooling is the least-resolved part: required film effectiveness 0.754
A turbojet afterburner has **no cold air**. The only coolant is turbine-exit gas already at 972 K,
against a 1900 K flame. For a 1200 K sheet Hastelloy-X limit,
eta_film = (1900-1200)/(1900-972) = **0.754**. Above ~0.5 conventional single-slot film cooling will
not do it; a continuously-injecting corrugated (screech) liner is needed, which is what the mass
model assumes. **No cooling design was done and no liner temperature was computed** (R7.3).

### D7.5 Closure: it fits under 25 kg, but how it is flown decides whether it fits
`ab_closure.py`. Added mass **4.082 kg** (AB module 2.928 + plug nozzle 0.850 + actuator/linkage
0.155 + AB fuel system 0.150). Fuel flow **0.0665 kg/s wet vs 0.0228 dry, 2.91x**.

| usage | wet time | extra fuel | TOGW | margin |
|---|---|---|---|---|
| supersonic acceleration + the 7 s hold | 7.2 s | +0.325 kg | **24.78 kg** | **+0.22 kg** |
| the whole 27.7 s brake-release acceleration + hold | 34.7 s | +1.560 kg | **26.02 kg** | **-1.02 kg, fails** |
| duct Mach 0.30 / 10 deg build, used throughout | 34.7 s | +1.560 kg | 24.72 kg | +0.28 kg |
| duct Mach 0.30 / 10 deg build, brief use | 7.2 s | +0.325 kg | 23.49 kg | +1.52 kg |

The supersonic acceleration is very short — M 1.00 -> 1.02 at 5 km takes **0.66 s dry and 0.22 s
wet** — so "hold only" and "acceleration + hold" are nearly the same number, and the failing case is
using the afterburner through the whole subsonic/transonic climb and acceleration.

Dash margin at the closed 24.78 kg: dry **+53.0 %** (pessimistic wave drag +37.5 %), afterburner lit
**+174.2 %** (+146.4 %).

**A7.16 / model limitation:** the Phase 2 fuselage is fixed-geometry (L_fus 2.70 m,
D_fus = D_engine + 30 mm), so a 484 mm longer engine moves the modelled zero-lift drag area only
81.9 -> 82.6 cm2. That is a limitation, not a result: centre of gravity, tail arrangement, structure
and the nozzle/boattail junction are **not modelled** (R7.5). Separately, correcting the frozen
closure's leftover Phase 2 placeholder nozzle and capture areas (49.1 -> 70.8 and 47.5 -> 55.1 cm2)
by itself moves the dash margin +54.70 % -> +55.13 %.

### R7.1-R7.7 New open risks
| id | risk |
|---|---|
| R7.1 | **Turbine exit annulus chokes at M 1.33**, altitude-independent; traced to `turb.MN = 0.45` in `arch_trade.turb_pout`. Pre-existing, not fixed. It caps the very envelope extension Phase 7 was asked for. |
| R7.2 | **No compliant nozzle actuator installation.** Load fits a sourced part; stroke is 2 % over its travel, forward mounting needs an undesigned pushrod, and no plug support/cooling/thermal-growth design exists. **No afterburner light-up or shut-down transient was analysed** — a nozzle that lags the light drives the compressor to the F7.7 fixed-nozzle condition. |
| R7.3 | **Liner cooling unresolved** (F7.12). No cooling design, no liner temperature, no screech-liner acoustic design. |
| R7.4 | **Airframe drag above M 1.05 is outside its model's validity** and inlet spillage/additive drag is absent entirely. |
| R7.5 | **Engine length +113 % is not carried into the airframe** (CG, tails, structure, boattail). |
| R7.6 | **eta_AB 0.90 assumed**, unvalidated at 1.45 bar and this scale. Thrust is insensitive; **fuel is not**, and fuel decides the 25 kg closure. |
| R7.7 | **Afterburner-on results above M 1.33 are not physically valid** (beyond the turbine-exit choke). The M 1.4-1.6 rows are trend only. |

### D7.6 What Phase 7 makes worse, and status
**Worse:** freeze risks **4.1/4.2** (the entire benefit now rests on the variable nozzle, including
its transients, and the fixed-nozzle column shows what a lagging nozzle does to the surge margin) and
**4.4** (an afterburner adds a 1900 K heat-release zone and a bluff-body flameholder just downstream
of the turbine; **screech** is a known excitation source and was not checked against the impeller
modes already crossing at idle). **4.3, 4.5 unchanged.**

**Untouched:** the freeze's open decisions 1-5, Phase 6 CAD, everything under `axial/`.
**No architecture or freeze decision is taken here.** Decisions handed to the user in
`docs/phase7_afterburner.md` section 10: whether the afterburner earns its 4.08 kg and 484 mm at
0.22 kg of margin; whether to adopt the lighter duct-Mach-0.30 build (needs the envelope and nozzle
trade re-run); and whether to fix R7.1, which re-opens Phase 3R/4R and the freeze.

### D7.7 Afterburner CAD built ON the Phase 6 engine (user instruction, 2026-09-15)
User request: "can you designed CAD for the afterburner added engine ... you can either build on it
or redesign from scratch and named as engine_with_afterburner_assembly.step", with "we can
overlooked the weight a bit but still track it".

**Built on**, not redesigned: `scripts/phase7_afterburner/ab_cad.py` imports all of `cad/engine/*.step`
unchanged — **25 Phase 6 parts carried over bit-for-bit** — and drops only the two the afterburner
physically replaces, `nozzle_outer_cone` and `tail_cone`. Nothing upstream of the turbine exit is
re-drawn, so the compressor, combustor, turbine, shaft and impeller are the geometry Phase 6 already
checked. **17 new parts**, plus the plug exported a second time in its dry position so the stroke is
visible in CAD. **42/42 solids pass `BRepCheck_Analyzer`.** Every new dimension is read from
`data/phase7/*.json` and `data/phase6/engine_params.json`; nothing is typed into the CAD script.
Outputs `cad/engine_with_afterburner_assembly.step`, `cad/afterburner/*.step`,
`data/phase7/ab_cad_mass.csv` and `ab_cad.json`; figures `plots/phase7_ab_section.png` and
`plots/phase7_ab_cutaway.png` (`ab_render.py`, reusing the Phase 6 renderer's helpers).

| section | x from the impeller nose | geometry |
|---|---|---|
| turbine exit | 296.4 mm | hub 36.67, tip 61.12 mm |
| diffuser | 296.4 -> 567.2 mm (270.8) | outer wall 64.02 -> 82.09 mm (3.82 deg), hub 36.67 -> 3.0 mm (7.65 deg) |
| burn section | 567.2 -> 669.9 mm (102.7) | duct r 82.09, corrugated liner 76.09, 2 gutter rings |
| nozzle cowl | 669.9 -> 779.9 mm (110.0) | 82.09 -> 62.00 mm |
| plug | shoulder 40.5 mm into the cowl (wet) | dry 91.4 mm, 51 mm stroke, tip at x 810.3 mm |

**F7.13 Length, corrected by the CAD.** The dry engine's nozzle ended at x 352.5 mm and the
afterburner replaces it, so the engine grows by **457.9 mm**, not by the 483.5 mm module length the
closure charged. The closure used the conservative figure, which is the right way round.

### F7.14 The afterburner fits inside the engine envelope; its nozzle actuator has nowhere to go (R7.8)
Part-by-part radial extent against the 93.31 mm envelope radius:

| part | r_max | over the envelope |
|---|---|---|
| nozzle actuator | 118.31 mm | **+25.00 mm** |
| nozzle pushrod | 110.31 mm | **+17.00 mm** |
| nozzle radial link | 107.31 mm | **+14.00 mm** |
| igniter | 98.09 mm | **+4.78 mm** |
| fuel manifold | 91.09 mm | -2.22 mm |
| AB duct and casing | 83.09 mm | -10.22 mm |
| everything else | <= 82.09 mm | inside |

**The flow path fits with room to spare** (10.2 mm free annulus) because the compressor diffuser sets
the engine diameter and the afterburner is slimmer than the combustor it follows. **The actuator has
nowhere to go:** a Volz DA 22 case is 22.0 mm on its smallest side and the P16 body about 20 mm,
against a 10.2 mm annulus over the AB duct, **no annulus at all** over the compressor casing (where
D7.4 puts it for temperature), and the **8.7 mm** engine-to-fuselage-skin gap Phase 6 measured.
**This is Phase 6A's F6A.2 repeated on the centrifugal engine.** The two fixes — a local fairing
(which changes the airframe cross-section and hence the wave drag the dash margin rests on) or a
longer remote linkage — are **not assessed**. The actuation train is drawn where it actually lands,
proud of the engine line, not tucked away.

### F7.15 CAD mass is 0.298 kg over the bottom-up model, and that is enough to fail the 25 kg closure
Mass is tracked as the user asked, group by group against the Phase 7 model:

| group | CAD | model | delta |
|---|---|---|---|
| diffuser + tail cone + struts | 1.373 | 1.244 | +10.3 % |
| burn casing | 0.450 | 0.447 | +0.5 % |
| screech liner | 0.243 | 0.303 | -19.7 % |
| flameholder + struts | 0.455 | 0.339 | +34.1 % |
| spray bars + manifold | 0.144 | 0.147 | -2.4 % |
| igniter | 0.032 | 0.060 | -47.3 % |
| nozzle cowl + plug + struts | 0.712 | 0.649 | +9.7 % |
| actuation | 0.332 | 0.255 | +30.2 % |
| **drawn total** | **3.741** | **3.446** | **+8.5 %** |

Plus the allowances the CAD does not draw (AB fuel valve and lines 0.120, plug slide bearing 0.040,
actuator linkage 0.060, AB fuel system 0.150, flanges/fasteners at 10 % of the drawn module 0.270):
**4.380 kg against the model's 4.082 kg, +0.298 kg.** With its growth allowance that takes TOGW
**24.780 -> 25.100 kg, 0.100 kg OVER the 25 kg ceiling.** The recommended duct-Mach-0.30 / 10 deg
build is 1.210 kg lighter in the module alone and comes out at about **23.804 kg (+1.196 kg margin)**
on the same drawing basis. The CAD does not change D7.5's conclusion, it sharpens it: **the
conservative 7 deg-diffuser afterburner does not fit the mass budget and the shorter one does.**
(Per the user, weight is not binding for this study but is tracked; it is tracked here.)

**A7.17 What the CAD is not** (same convention as Phase 6 — provisional, shape only): straight
conical diffuser walls rather than a contour; a screech liner drawn with 25 mm-pitch, 2 mm-amplitude
corrugations as a **drawing convention** with no acoustic design and no cooling holes (R7.3); V-gutters
as 25 mm bluff bodies at the analysed blockage rather than designed gutters; a **schematic** actuation
linkage (bellcrank, pushrod buckling and thermal growth not designed, R7.2); no thermal growth,
mounts, joints or manufacturing features anywhere. Radial parts are drawn on +y so they appear in the
meridional section, following the Phase 6 deswirl-vane convention.

**R7.8 (new):** the nozzle actuator and its linkage do not fit inside the engine envelope, and the
engine-to-skin gap cannot take them either. Unresolved; both fixes touch the airframe cross-section
the dash margin depends on.
