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
