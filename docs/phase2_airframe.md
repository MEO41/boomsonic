# Phase 2 — Aircraft-level constraint sizing, drag, mass budget (2026-09-13)

Scripts: `scripts/phase2_airframe/` (regenerate everything with `run_phase2.py`).
Inputs from Phase 1: D1.1 engine (500 N at M 1.0 / 5 km, pyCycle deck
`data/phase1_thrust_available_dash5km.csv`), D1.2 mission (Mach-1 dash at 5 km).

## 0. External requirement found during Phase 2: the Boom Prize

Your mission matches the published Boom Prize rules almost exactly (source:
https://boomsupersonic.com/prize, read 2026-09-13; details in `data/rc_jet_speed_records.md`):

| Rule (quoted or paraphrased from the page) | Effect on this design |
|---|---|
| MTOW 25 kg / 55 lb **including fuel**; fixed-wing; air-breathing only (turbojet/turbofan/ramjet) | Same as the brief. |
| True airspeed above local speed of sound, **5+ continuous seconds** | Brief's 7 s gives a 2 s margin. Drag design point set to **M 1.02** (air-data margin, see D2.1). |
| **Mach 0.8 to past Mach 1 must be flown level or climbing, no altitude loss** ("a dive to accelerate doesn't qualify") | Mission accelerates level at 5 km (segment 3). A dive-assisted profile is not allowed, so the transonic thrust pinch must be met in level flight. |
| Two qualifying flights, same calendar day, **reciprocal headings** | Same airframe must be turned around in one day (A1.9 refuel allowed). |
| **Controlled landing, wheeled or belly**, on the designated area; reflyable without replacing major components | A belly landing is permitted: this relaxes the runway landing constraint (D2.5). |
| Human remote pilot with **continuous command and instant abort authority** | Telemetry and flight-termination mass carried (mass budget). |
| Verification: calibrated pitot-static + total air temperature, sealed data loggers, GPS, reciprocal runs | 0.30 kg instrumentation line item. |
| No altitude limit stated; venue coordinated with Boom | D1.2 (5 km) stands; airspace is arranged with the organiser. |

## 1. Tool gap and verification (ground rule 3)

ADRpy has no transonic drag capability and a constant-CD0 assumption, so the drag model
is a separate, cited build-up; ADRpy keeps the constraint equations.

- **AeroSandbox 4.2.10** added to `.venv` (pip, MIT). Used only for three cited helper
  models: `approximate_CD_wave` (Raymer 12.5.10 + Mason/Lock transonic drag-rise shape),
  `critical_mach` (fit to Raymer Fig. 12.28), `fuselage_base_drag_coefficient`
  (MIL-HDBK-762 fit). Verified (`verify_aero_tools.py`):
  - `sears_haack_drag_from_volume` = analytic Sears-Haack wave drag exactly (ratio 1.0000).
  - **Finding F2.1:** `sears_haack_drag(radius, length)` returns the drag coefficient on
    frontal area (off by 1/A_max; 39x in the test), although its docstring says drag area.
    Not used.
- **Own slender-body wave-drag integral** (Fourier-sine form of von Karman's result),
  verified: Sears-Haack body ratio 1.0007; parabolic-area body 0.9607 vs exact analytic
  2048/(216 pi^2) = 0.9607. Any kink in the area curve makes the series diverge
  logarithmically, so shape comparisons use harmonics n <= l/d (documented in the code).
- **Finding F2.2, ADRpy bug:** `AircraftConcept` default quarter-chord sweep
  (`constraintanalysis.py:392`) is `2*LE + 5*MT/7` instead of `(2*LE + 5*MT)/7` -> 143.6 deg
  for this wing -> lift slope 1.23/rad instead of 2.87/rad. Worked around by passing
  `sweep_25_deg` explicitly; ADRpy then agrees with DATCOM (2.75/rad) and our Raymer eq.
  12.6 value (2.62/rad, with exposed-area and fuselage factors) within 9 %.
- **Finding F2.3, ADRpy quirk:** the sustained-turn constraint uses the *climb* weight
  fraction; handled by building a separate concept per constraint.
- ADRpy's generic turbojet thrust lapse (bpr = 0, throttle ratio 1) is far more pessimistic
  at M 1 than the pyCycle deck (dotted line on the diagram); the pyCycle deck is used.

## 2. Engine envelope from the sourced database (D2.3)

26 manufacturer-rated engines, 160-1250 N (`data/microturbojet_database.csv`, URL per row;
`engine_database_fit.py`, `plots/phase2_engine_database.png`). Power-law fits at the D1.1
engine's derived SLS thrust of 665 N:

| quantity | fit | at 665 N | 1-sigma band |
|---|---|---|---|
| dry mass | 0.0035 F^1.164 | **6.83 kg** | 6.0-7.8 kg |
| diameter | 11.06 F^0.436 | **188 mm** | 181-196 mm |
| length | 43.5 F^0.361 | **453 mm** | 410-501 mm |
| airflow | 0.0037 F^0.877 | 1.10 kg/s | 1.02-1.18 (pyCycle: 1.166) |
| accessories (ECU, pump, valves, battery) | AMT published system masses | 0.235 x engine (Nike) nominal, 0.43 (Titan) high | |

Vendor SLS specific thrust is 590-634 m/s for the 300-1100 N class vs 571 m/s for the
Phase 1 placeholder cycle, i.e. the placeholder is slightly conservative on airflow and
therefore on diameter. Phase 3 will set this properly.

## 3. Configuration and drag (D2.2, D2.4, D2.6)

Configuration C1: slender body of revolution around the engine, sharp-lip nose pitot inlet
(no spillage at the dash, capture stream-tube 47.5 cm2), engine near the CG under the wing,
convergent nozzle at the tail; trapezoidal wing AR 3, taper 0.2, LE sweep 55 deg, 5 %
NACA 64A-type section; all-moving horizontal tail and fin sized with jet-fighter tail
volume coefficients (Raymer Table 6.4: 0.40 / 0.07).

Drag build-up (`airframe_model.py`): Raymer eq. 12.27-12.31 friction/form with smooth
molded composite roughness, MIL-HDBK-762 base drag, 5 % leakage and protuberance, and
transonic-area-rule wave drag (whole-aircraft normal-cut area distribution minus inlet
stream-tube plus the fully-expanded jet plume), E_WD = max(1.8, geometric E) nominal,
3.0 pessimistic.

Shaping trades (numbers at S = 0.30 m2, M 1.02 / 5 km):

| step | change | CD*S nominal | CD*S E_WD 3.0 |
|---|---|---|---|
| D2.2 | forebody 30 -> 40 % of length, sweep 45 -> 55 deg (placeholder 150 mm engine) | 91 -> 73 cm2 | |
| D2.3/2.4 | database engine 188 mm (body 218 mm); length 2.4 -> 2.7 m, forebody 45 % | 97.5 -> 91.6 | 109.3 |
| D2.6 | aft closure 22 -> 28 % of length + half-wing-area waist (10 mm engine clearance kept) | **83.1** | **100.5** |

A waist alone gave no nominal gain (A_max -16 % but the steeper aft closure raised the
geometric E_WD from 1.97 to 2.84); the aft-body closure is the dominant wave-drag term.

Design point breakdown (S = 0.30 m2, `data/phase2_baseline_breakdown.csv`):

| condition | fuselage | wing | tails | base + L&P | wave | total CD*S |
|---|---|---|---|---|---|---|
| M 0.70 / 300 m | 35.2 | 14.9 | 3.7 | 3.5 | 0 | 57.5 cm2 |
| M 0.90 / 5 km | 35.3 | 15.7 | 4.0 | 3.6 | 0 | 58.6 cm2 |
| M 1.00 / 5 km | 34.2 | 15.5 | 3.9 | 3.6 | 14.5 | 71.8 cm2 |
| **M 1.02 / 5 km (design)** | 34.0 | 15.4 | 3.9 | 3.6 | 26.1 | **83.1 cm2** (100.5 at E_WD 3.0) |
| M 1.05 / 5 km | 33.7 | 15.4 | 3.9 | 3.6 | 40.5 | 97.0 cm2 |

Phase 1 budget was 132 cm2 (target 99 cm2 with 25 % acceleration margin): met nominally,
at the target in the pessimistic case.

**Engine-diameter sensitivity (input to the Phase 3 architecture trade,
`data/phase2_engine_diameter_sensitivity.txt`):** +10 mm of engine diameter costs
+5.5 cm2 (nominal) / +8 cm2 (pessimistic) of dash drag area, i.e. +20-30 N. A 150 mm
engine would drop dash drag from 327 N to 251 N nominal (-23 %) and from 395 N to 280 N
pessimistic (-29 %).

## 4. Constraint diagram (ADRpy) (D2.5)

`plots/phase2_constraint_diagram.png`, `data/phase2_constraints.csv`. All T/W are
sea-level-static equivalents via the pyCycle lapse; drawn at the 25 kg ceiling
(conservative; estimated TOGW is 18.7 kg). Available: 665 N x 0.97 installed / 25 kg = 2.63.

| constraint | condition | binding? |
|---|---|---|
| take-off | 150 m ground roll, alpha_rot 12 deg, mu_R 0.05 | only above W/S ~1500 Pa |
| climb | 50 m/s at M 0.70, 2.5 km | no (T/W req ~1.1 at the design point) |
| **dash** | **M 1.02 / 5 km, 25 % thrust margin** | **yes: S <= 0.383 m2 nominal, <= 0.24 m2 pessimistic** |
| sustained turn | 3 g at M 0.90 / 5 km (turn-back) | no |
| service ceiling | 6 km at M 0.70 | no |
| **landing** (added, integrated braked roll) | alpha_TD 12 deg, 60 m air segment, mu_brake 0.2-0.3 | **yes without a chute:** 300 m runway needs S >= 0.44 m2 (plain flap) or 0.55 m2 (no flap) -> conflicts with the dash |

The dash (upper bound on S) and landing (lower bound on S) cannot both be met on a
300 m runway with wheel brakes alone. Resolutions, quantified at S = 0.30 m2 and 25 kg
(`data/phase2_landing_distances.csv`):

| option | landing distance (mu_brake 0.3) | comment |
|---|---|---|
| plain flap only | 396 m | needs >= 400 m runway |
| **plain flap + 0.6 m drag chute** (CD0 0.75, Knacke) | **209 m** | fits 300 m; chute common on fast RC jets; +0.20 kg |
| no flap + chute | 235 m | fits 300 m |
| 500 m runway, flap, no chute | fits for S >= 0.22 m2 | |
| belly landing (prize allows) | roll not a constraint | touchdown energy/abrasion becomes the issue; gear mass saved ~1 kg |

**D2.5 chosen: plain flaps + drag chute; wheeled landing on >= 300 m.** Belly landing is
the documented fallback.

## 5. Wing area selection (D2.7)

Feasible range S = 0.24-0.38 m2 (dash margin) with a chute. Candidates run through mission,
mass and landing (`data/phase2_mass_budget.csv`, `data/phase2_mission_vs_wing_area.csv`):

| S [m2] | dash throttle nom / E3 | margin nom / E3 | V_LOF at TOGW | TOGW nom | landing flap+chute (25 kg) |
|---|---|---|---|---|---|
| 0.25 | 0.62 / 0.76 | 60 % / 32 % | 51 m/s | 18.5 kg | 223 m |
| **0.30** | **0.67 / 0.81** | **50 % / 24 %** | **47 m/s** | **18.7 kg** | **209 m** |
| 0.35 | 0.71 / 0.86 | 40 % / 17 % | 44 m/s | 18.9 kg | 199 m |

**Chosen S = 0.30 m2** (span 0.95 m, root chord 0.53 m, MAC 0.36 m): it keeps a 25 %
thrust margin in the nominal case and essentially 25 % (24 %) in the pessimistic E_WD = 3
case, while lift-off speed stays below 50 m/s at the estimated TOGW. W/S = 611 Pa at
18.7 kg (817 Pa at the 25 kg ceiling).

## 6. Mission segment thrust requirements (design point)

S = 0.30 m2, TOGW 18.7 kg, installed thrust = 0.97 x pyCycle deck
(`data/phase2_design_point_segments.csv`; the 25 kg case is also in the file):

| segment | time | fuel | max thrust required (nom / E3) | min thrust available | min excess thrust (nom / E3) |
|---|---|---|---|---|---|
| 0 ground roll to V_LOF 47 m/s | 1.5 s (40 m) | 0.03 kg | 21 N | 616 N | 595 N |
| 1 level accel 300 m to M 0.70 | 7.2 s | 0.15 kg | 193 N | 567 N | 385 N |
| 2 climb at M 0.70 to 5 km | 10.1 s | 0.19 kg | 193 N | 406 N | 291 N |
| 3 level accel M 0.70 -> 1.02 at 5 km | 7.1 / 7.4 s | 0.12 kg | 324 / 393 N | 406 N | **167 / 99 N (transonic pinch)** |
| 4 hold M 1.02 for 7 s | 7.0 s | 0.09 / 0.11 kg | **328 / 396 N** | 492 N | 164 / 96 N |
| 5 turn-back (3 g at M 0.90) + idle descent | 235 s | 0.47 kg | 184 N (turn) | 449 N | 265 N |
| 6 pattern + landing | 60 s | 0.24 kg | | | |

Brake release to M 1.02 at 5 km: 26 s at 18.7 kg (35 s at 25 kg). Sortie fuel 1.29 kg + 0.24 kg reserve,
+3 % unusable -> **1.58 kg (1.97 L)**.

## 7. First-pass mass budget (D2.8)

`mass_budget.py`, `plots/phase2_mass_budget.png`, S = 0.30 m2, nominal engine and drag:

| item | kg | basis |
|---|---|---|
| engine, dry | 6.83 | 26-engine database fit at 665 N |
| engine accessories | 1.60 | 0.235 x engine (AMT Nike system mass) |
| structure (fuselage 2.60, wing 0.52, tails 0.23, duct 0.13, mounts 0.35) | 3.84 | ply-count areal densities (0.39 kg/m2 per carbon ply) + frame/joint allowances |
| landing gear + drag chute | 1.27 | 4.3 % W0 (Raymer Table 15.2 order) + 0.20 kg chute |
| fuel system | 0.40 | tank, hopper, lines |
| systems, avionics, prize instrumentation | 2.02 | itemised (9 servos, FC/GPS/telemetry, batteries, wiring, pitot/TAT/loggers, FTS) |
| growth allowance 15 % on structure + systems | 1.13 | conceptual allowance |
| fuel (mission + reserve + 3 % unusable) | 1.58 | mission integration at iterated TOGW |
| **estimated TOGW** | **18.7** | |
| **margin to 25 kg** | **6.3** | |

Sensitivities: high engine mass (+1-sigma) with the highest accessory fraction ->
TOGW 21.4 kg (margin 3.6 kg). Pessimistic drag adds only +0.03 kg fuel.
Statistical cross-check: large RC jets (14 kits) give 2.61 kg per m2 of length x span for
airframe + systems -> 6.7 kg for this aircraft vs 7.5 kg bottom-up (8.7 kg with growth);
the budget uses the higher, bottom-up value. The aircraft is below the database span
range, so the statistical value is an extrapolation.

**Closure: the 25 kg ceiling is met with 3.6-6.3 kg margin.** The engine system is 45 %
of TOGW (8.4 of 18.7 kg), so engine mass remains the dominant closure risk and Phase 3/4
must beat or confirm the database value.

## 8. Structural screening

Flutter (NACA TN 4197 closed form, screening only; `flutter_screening.py`): with 2+2 ply
carbon skins (G_skin 20 GPa, +-45 woven, CLT basis) the minimum flutter-speed ratio is
**2.5** (wing, all three conditions) vs a required 1.25. The tails are at 3.6-5.9. A modal
flutter analysis is a Phase 4/5 item. Design dynamic pressure: 39 kPa at the dash,
~34 kPa at M 0.70 / 300 m.

## 9. Assumptions added in Phase 2

| id | assumption | status |
|---|---|---|
| A2.1 | drag design point M 1.02 (holds M >= 1.00 with +-0.02 air-data error for 5+ s) | design choice |
| A2.2 | E_WD nominal = max(1.8, geometric); pessimistic 3.0 (Raymer range) | carried as a bracket |
| A2.3 | installation loss 3 % of thrust (inlet duct, lip, power extraction) | Phase 3 replaces with a duct loss in pyCycle |
| A2.4 | extended gear drag area 30 cm2 | estimate |
| A2.5 | touchdown alpha 12 deg, air segment 60 m, brake mu 0.2-0.3 (no RC brake data found) | user/test to confirm |
| A2.6 | runway 300 m paved (A1.7 carried) | user to confirm with the venue |
| A2.7 | growth allowance 15 % | conceptual |
| A2.8 | the pessimistic engine accessory fraction 0.43 (Titan) | bracket |

## 10. Open items handed to Phase 3/4

1. Engine diameter is now a first-order airframe driver (section 3). The Phase 3
   architecture trade must include diameter: centrifugal (database class, ~188 mm) vs
   axial or mixed-flow compressor.
2. Engine system mass is 45 % of TOGW; Phase 4 bottom-up mass must confirm 6.8 kg.
3. Replace A2.3 with an inlet-duct pressure loss inside the cycle model; nose pitot inlet
   recovery at M 1.02 is ~1.0 (normal shock at M 1.02 is weak).
4. The Phase 1 placeholder cycle gives 50 % dash thrust margin at nominal drag. Phase 3
   may trade some of it for a smaller, lighter engine, but only while the pessimistic
   (E_WD 3) case keeps positive excess thrust through the transonic pinch (currently 99 N).
