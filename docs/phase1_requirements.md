# Phase 1 — Requirements, operating point and mission definition (2026-09-13)

Context (from the user): RC-scale student project to learn about transonic/supersonic
flight hands-on. Engine target 500 N. Mission: wheeled take-off from standstill, accelerate
and climb to Mach 1, hold Mach 1 for 7 s, descend and land; fly the same sortie a second
time on the same day. Airframe drag is not yet known, so the study is run "engine first"
and the airframe gets a drag budget it must meet in Phase 2.

Scripts: `scripts/phase1_requirements/` (all pyCycle runs use the placeholder cycle of
`prelim_turbojet_model.py`: OPR 4, T4 1150 K, eta_c 0.78, eta_t 0.85, convergent nozzle,
scaled NPSS maps. Phase 3 replaces these; the conclusions below are about *ratios* and
*trends*, which are far less sensitive to those placeholders than absolute values.)

## 1. The physics that drives everything: thrust lapse at Mach 1

At Mach 1 the inlet total temperature is 1.2 x ambient. At a fixed mechanical speed limit
this lowers the compressor corrected speed by ~9.5 %, and thrust falls with it. The ECU of
every real micro-turbojet limits RPM first and EGT second, so the realistic thrust
available is the *lower* of the RPM-limited and T4-limited values. pyCycle sweep,
500 N SLS-rated engine, max throttle (`data/phase1_thrust_available.csv`,
`plots/phase1_thrust_lapse.png`):

| Mach 1 at altitude | thrust available | binding limit | T4-limited value (needs N %) | q at Mach 1 | allowable CD*S = Fn/q |
|---|---|---|---|---|---|
| 0 km | 309 N | RPM | 545 N (104.7 %) | 70.9 kPa | 44 cm2 |
| 1 km | 325 N | RPM | 505 N (103.9 %) | 62.9 kPa | 52 cm2 |
| 3 km | 325 N | RPM | 428 N (102.7 %) | 49.1 kPa | 66 cm2 |
| 5 km | 325 N | RPM | 367 N (101.3 %) | 37.8 kPa | 86 cm2 |
| 8 km | 272 N | RPM | 279 N (100.7 %) | 24.9 kPa | 109 cm2 |
| 10 km | 226 N | RPM | n/a | 18.5 kPa | 122 cm2 |

**Finding F1.1:** an engine *rated* 500 N at SLS delivers only ~310-325 N at Mach 1 below
5 km. The 500 N the mission actually needs is the thrust at the dash, not the static rating.

**Finding F1.2:** the drag-area budget the airframe may have (CD*S = Fn/q) grows with dash
altitude because q falls faster than thrust: 44 cm2 at sea level vs 86 cm2 at 5 km for the
same engine. For scale, a 150 mm engine has a frontal area of 177 cm2; a well-faired body
at Mach 1 has a frontal-area drag coefficient of ~0.2-0.3 (Hoerner, *Fluid-Dynamic Drag*,
ch. 16-17, slender bodies of revolution at M ~ 1), i.e. 35-55 cm2 for the fuselage alone
before wings, tails, inlet spillage and interference. A sea-level Mach 1 dash on a 500 N
SLS engine is therefore not credible; altitude and re-defining the rating point are needed.

## 2. Decision D1.1 — operating-point definition of "500 N"

Two definitions were run like-for-like (`prelim_design_point_options.py`,
`data/phase1_design_point_options.csv`):

| definition | design airflow | thrust at SLS | thrust at M1 / 0 km | M1 / 3 km | M1 / 5 km |
|---|---|---|---|---|---|
| A: 500 N at SLS (data-sheet convention) | 0.865 kg/s | 500 N | 309 N | 325 N | 325 N |
| B: 500 N at M1 / 3 km (cycle design point there) | 1.183 kg/s | 562 N | 548 N | 500 N | 383 N* |
| B: 500 N at M1 / 5 km (cycle design point there) | 1.120 kg/s | 665 N | 548 N | 523 N | 500 N |

(*3-km-designed engine at 5 km is RPM-limited at 383 N.)

**Chosen: definition B — 500 N = uninstalled net thrust at the Mach 1 dash point, ISA,
with the compressor at 100 % corrected speed and T4 at its maximum there (that point is the
cycle design point).** SLS thrust becomes a derived output (~665 N for a 5 km dash).

Why: the user's stated purpose of the thrust is to overcome drag at Mach 1. Under
definition A the mission point gets only 65 % of the rating and the airframe budget is
44-86 cm2; under B it gets the full 500 N and 88-132 cm2. The cost is a ~30 % larger
airflow engine (1.12 vs 0.87 kg/s), which is a mass penalty Phase 2/4 must absorb inside
25 kg. That trade is explicit rather than hidden in a rating convention.

## 3. Decision D1.2 — mission profile: candidates and selection

Four dash altitudes were integrated with a point-mass energy model
(`prelim_mission_energy.py`) using the definition-B engine table
(`data/phase1_thrust_available_dash5km.csv`). The airframe drag is parameterised as 75 %
of the thrust-limited CD*S at the dash (assumption A1.2) with a transonic drag-rise factor
of 2 (A1.3). Profile: level acceleration at 300 m to M 0.7, constant-Mach climb, level
acceleration to M 1.0, 7 s hold, idle descent, 2 min idle reserve.

| candidate | dash alt | Fn at M1 | q at M1 | CD*S budget | time to M1 | sortie time | ground track | fuel incl. reserve | P3 at dash | Re index at dash |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 1 km | 551 N | 62.9 kPa | 88 cm2 | 18 s | 60 s | 6.3 km | 0.82 kg | 558 kPa | 1.36 |
| B | 3 km | 523 N | 49.1 kPa | 107 cm2 | 24 s | 166 s | 7.5 km | 1.10 kg | 475 kPa | 1.12 |
| **C** | **5 km** | **500 N** | **37.8 kPa** | **132 cm2** | **31 s** | **273 s** | **9.1 km** | **1.40 kg** | **401 kPa** | **0.92** |
| D | 10 km | 289 N | 18.5 kPa | 156 cm2 | 61 s | 553 s | 15.5 km | 2.09 kg | 216 kPa | 0.53 |

(Re index = compressor-inlet Reynolds number relative to SLS static; P3 = compressor
delivery pressure at the dash, relevant to combustor stability.)

Sensitivity (`data/phase1_mission_sensitivity_dash5km.csv`): across drag margin 0.6-0.9 and
drag-rise factor 1.5-3.0, total fuel stays within 0.7-0.9 kg (A), 1.0-1.3 kg (B),
1.2-1.6 kg (C), 1.8-2.4 kg (D). Fuel is never the discriminator: every candidate needs
under 10 % of MTOW.

**Chosen: candidate C, Mach 1 dash at 5 km ISA.** Rationale with numbers:
- Drag budget is the binding constraint of this whole project (F1.2). C gives 132 cm2,
  24 % more than B and 50 % more than A, for +0.3 kg fuel over B.
- Structural/aeroelastic load at the dash is q = 37.8 kPa, 40 % below A. This matters for
  a hobby-built airframe (flutter and skin loads scale with q).
- The engine stays in a benign regime: P3 401 kPa and Re index 0.92. Candidate D drops to
  216 kPa and 0.53, where micro-turbojet combustors and small blades lose efficiency and
  stability margin (documented in small-engine altitude testing, e.g. NASA/TM small-engine
  studies; to be quantified with Cantera loading checks in Phase 3 if D is ever revisited).
- D also needs 60 s and 15 km just to reach Mach 1 and a 9-minute sortie; C is under 5 min.
- Fallback: if practical or regulatory reasons force a lower dash, candidate B (3 km) is
  the documented fallback with a 107 cm2 budget; the same engine covers it (523 N there).

## 4. Derived requirements handed to Phases 2-4

Engine (Phase 3/4):
- E1: Fn = 500 N uninstalled at M 1.0, 5000 m ISA (T2 = 306.8 K, P2 = 100.2 kPa with 0.98
  recovery), at 100 % N and T4max simultaneously. Placeholder cycle implies ~1.12 kg/s.
- E2: mechanical speed margin: the T4-limited RPM at M1 / 1 km is 102.2 % of design speed
  and 106.5 % static at 5 km (table). The ECU limit (100 %) governs; Phase 4 rotor stress
  must cover 105 % overspeed transients.
- E3: derived SLS thrust ~665 N (RPM-limited) — drives take-off ground roll in Phase 2
  and must be checked against the engine-mass database (rating used by vendors).
- E4: operating envelope: 0-6 km, M 0-1.05, ISA-15 to ISA+20 (hot-day check in Phase 3).
- E5: fuel flow at the dash ~0.019 kg/s; sortie fuel ~1.4 kg (+ reserve) -> tank 2.0 kg
  Jet-A/kerosene placeholder until Phase 2 closes the budget.
- E6: life: 2 sorties/day without inspection is the stated need; design assumption
  A1.6 = at least 10 hot cycles / 1 h at max rating before overhaul, to cover test flights.
- E7: convergent nozzle, NPR at the dash ~3.4 (choked, under-expanded). A C-D nozzle is a
  Phase 3 trade item (thrust gain vs mass).

Airframe (Phase 2):
- A1: MTOW <= 25 kg; take-off from a paved runway, wheeled landing (gear mass, stall speed).
- A2: **drag-area budget CD*S <= 132 cm2 at M 1.0, 5 km**, with 25 % of thrust reserved
  for acceleration through the drag rise (i.e. target CD*S <= 99 cm2). This is the
  requirement Phase 2 must demonstrate with a cited transonic drag build-up (Raymer /
  Hoerner / DATCOM methods), since no tool in the survey does transonic drag.
- A3: q_max = 38 kPa design dynamic pressure (dash), q at low-altitude acceleration up to
  ~45 kPa at M 0.8 / 300 m — structural design condition.
- A4: energy height 10.2 km; sortie ~4.5 min; ground track ~9 km + return — implies an
  autopilot with telemetry (not visually flyable) and airspace authorization.
- A5: fuel 2.0 kg + engine (from database) + structure + systems <= 25 kg (Phase 2 budget).

## 5. Assumptions register (Phase 1)

| id | assumption | status |
|---|---|---|
| A0.1 (superseded by D1.1) | 500 N at SLS | replaced: 500 N at M1 / 5 km |
| A1.1 | ISA standard day for all sizing; hot day checked in Phase 3 | user to confirm |
| A1.2 | airframe CD*S at the dash = 75 % of thrust-limited value (25 % acceleration margin) | design choice, revisited in Phase 2 |
| A1.3 | transonic drag-rise factor 2.0 between M 0.8 and 1.0 | placeholder; Phase 2 drag build-up replaces |
| A1.4 | idle fuel flow = 10 % of max SLS fuel flow | typical micro-turbojet ECU idle (~35-40 % RPM); Phase 3 off-design replaces |
| A1.5 | reserve = 2 min idle | design choice |
| A1.6 | engine life >= 10 hot cycles / 1 h at max rating | assumption, covers test flying before the two "real" sorties |
| A1.7 | runway: paved, >= 300 m, sea level | user to confirm (drives Phase 2 take-off constraint) |
| A1.8 | Jet-A / kerosene with turbine oil mix, as per micro-turbojet practice | user to confirm |
| A1.9 | refuelling between the two sorties is allowed; tank sized for one sortie + reserve | user to confirm |
| A1.10 | ground roll not integrated in Phase 1 (starts airborne at 40 m/s, 300 m) | Phase 2 |

## 6. Non-engineering prerequisites (stated once, not designed here)

A Mach 1 flight by an uncrewed 25 kg aircraft at 5 km altitude requires airspace
authorization and a range with telemetry/flight-termination provisions in every
jurisdiction. This does not change the engineering, but it is a hard prerequisite to
flying the mission and should be checked early by the user.

## 7. Items the user may adjust (non-blocking)

1. Dash altitude: 5 km chosen; 3 km fallback quantified. Lower than 3 km makes the drag
   budget unlikely to close (F1.2).
2. Runway length / launch site elevation (A1.7).
3. Whether a C-D nozzle or an afterburner-free design is acceptable (assumed: no reheat).
