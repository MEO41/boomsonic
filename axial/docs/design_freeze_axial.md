# Design freeze, axial option (Phase 5A): status snapshot for review (2026-09-14)

**What this document is.** The Phase 5 snapshot of the **pure axial engine** (6-stage axial compressor, OPR 5,
80 000 rpm, tag `ax80000_opr5_t1150_n6_cap_3r`), compiled from `axial/docs/phase4a_axial.md` for the user's review. The user
asked for the early 6-stage axial concept to be finished "as you did with the centrifugal one", and chose to pause here
for review before any axial CAD (brief rule 4).

* **It does not claim the design is closed.** Section 4 states the open items with their current status. Several of
  them decide whether this engine is workable at all.
* **It does not replace the centrifugal baseline.** The current baseline is still the centrifugal
  (`docs/design_freeze.md`, Phase 6 started on it). Which of the two goes forward is a decision for the reviewer
  (section 6), and section 7 compares them.
* Every number comes from a tool run or a cited relation (sources: `axial/docs/phase4a_axial.md`, `design_log.md` F3A.1-D4A.4).
  Nothing has been measured on hardware. Numbers are **fielded** (η_c 0.709, η_t 0.75, η_b 0.95) unless marked "tool".
* **Every compressor efficiency, off-design and operability number rests on the project's own axial stage-stacking
  model, which is not validated at this scale (R4.1, section 4.1).**

---

## 1. Final architecture

Single-spool turbojet: 6-stage axial compressor with a variable inlet guide vane, an overboard bleed after stage 3,
annular combustor, single-stage axial turbine, and a variable-area convergent nozzle, in the Phase 2 nose-pitot
fuselage.

### 1.1 Cycle (design point: Fn 500 N at M 1.02 / 5000 m ISA, T4 1150 K)

| quantity | fielded |
|---|---|
| net thrust / T4 | 500 N / 1150 K |
| compressor pressure ratio | 5.0 (overall 4.85 including the 3.0 % intake-duct loss) |
| airflow | 1.360 kg/s |
| fuel flow / TSFC | 22.0 g/s / 0.159 kg/(N h) |
| compressor inlet / exit | 309 K, 102.1 kPa / 559 K, 511 kPa |
| turbine inlet / exit | 1150 K, 485 kPa / 937 K, 151 kPa |
| turbine pressure ratio | 3.20 |
| nozzle | convergent, A8 70.2 cm² at design (variable to 2.0 ×), NPR 2.80, Vj 556 m/s |
| sea-level static maximum | 659 N at 98.7 % speed, limited by T4 |

### 1.2 Compressor: 6-stage axial

| item | value |
|---|---|
| spool speed | 80 000 rpm; MCS (105 %) 84 000 rpm |
| blading | TurboDesigner, sized at the fielded cycle; hub/tip 0.40, Cx 200 m/s; rotors 14/17/21/26/30/35, stators 14/18/22/26/32/36 (291 blades); Ti-6Al-4V |
| size | casing 110.3 mm; rotor-1 tip radius 52.4 mm; length 196 mm; last blade 11.8 mm |
| loading | rotor-1 tip M_rel 1.27 (limit 1.35); worst DF 0.46; de Haller 0.72 |
| efficiency | tool (Howell) 0.832; fielded 0.709 (A3A.1: same debit as the centrifugal) |
| blade roots at MCS | stages 1-2: **598 / 597 MPa = 96 % of Fty 620 MPa**, with a provisional 10 % thickness taper (Kt 1.4); stages 3-6: 523-550 MPa |
| discs | re-sized to 365 MPa at design speed: burst ratio 1.20 at MCS |
| surge margin (stacking peak-line surrogate, unvalidated) | 13.9 % at dash, 10.5 % at SLS maximum |

### 1.3 Variable geometry (option A)

| system | schedule | raw mass |
|---|---|---|
| VIGV | on corrected speed (design inlet = 100 %): design swirl 22.4° at ≥ 95 %, closing linearly by 15° at 60 % (28.7° at SLS idle) | 0.165 kg (vanes, spindles, levers, unison ring, 75 g servo) |
| overboard bleed after stage 3 | 10 % of inlet flow, open at ≤ 95 % speed | 0.122 kg (manifold, band valve, 75 g servo) |
| variable nozzle | 1.0 × A8 at ≥ 95 %, opening linearly to 2.0 × by 80 % speed | 0.354 kg (flaps, sync ring, hinges, heat-shielded 75 g servo) |

The masses are geometric estimates with hobby-class servos, **not sourced from a fielded design** (section 4.4).

### 1.4 Turbine, combustor, rotor, envelope

| item | value |
|---|---|
| turbine | single-stage axial, IN-713LC; hub 34.4 / **tip 57.3 mm, exactly on the 350 MPa blade-root limit** (A3.2); chord 11.5 mm; ~33 NGV / ~27 rotor blades; tool η_tt 0.917 |
| combustor | annular, casing OD 142.5 mm (sets the engine diameter), liner 157 mm (Phase 3 rule), reference velocity 29.8 m/s; η_b 0.95 and dP/P 0.05 assumed |
| rotor | layout A: Ti drum 2 mm, AISI 4340 shaft 24 / 12 mm, 12 mm journals (DN 1.01e6 at MCS), two hybrid ball bearings on damped soft supports (k 1.75e6 N/m, c 876 N s/m); rotor 1.60 kg, Ip 8.0e-4 kg m² |
| **engine envelope** | **OD 142.5 mm** (combustor; compressor 110, turbine 119) × **length 599 mm** |
| **engine dry mass** | **6.86 kg** calibrated (bottom-up 5.71 kg × 1.20; range 6.50-7.22 kg); accessories carried separately, 1.60 kg (A3.7) |

Largest raw mass items (kg): shaft 0.95; fasteners / seals / balancing 0.52; outer casing 0.46; compressor casing 0.46;
combustor liners 0.42; shaft tunnel and bearing housings 0.37; variable nozzle 0.35; compressor discs 0.28; drum 0.26.

---

## 2. Airframe closure (S 0.30 m², Phase 2 airframe; `ax_closure.py`, `axial/data/phase4ax/closure_<tag>.json`)

Fuel comes from the Phase 2 sortie flown on the engine's own deck (stacking compressor map with the VIGV schedule,
TurboFlow turbine map, T4-limited maximum throttle). TOGW is iterated on that fuel. **Two descent concepts are shown,
because the one the centrifugal was flown with is not physically possible for this engine** (section 4.2).

| | powered idle descent (as the centrifugal) | engine-off descent (glide, dead-stick landing) |
|---|---|---|
| fuel (incl. 120 s reserve at idle, 3 % unusable) | 5.46 kg | 1.88 kg |
| **TOGW** | **22.12 kg** | **18.54 kg** |
| **margin to 25 kg** | **2.88 kg** | **6.46 kg** |

| performance check | nominal wave drag | pessimistic wave drag |
|---|---|---|
| **dash thrust margin at M 1.02 / 5 km** (target 25 %) | **+103 %** | **+88 %** |
| brake release to M 1.02 at 5 km | 29.1 s | 29.2 s |
| 3 g sustained turn at M 0.9 / 5 km, excess thrust | +292 N | +292 N |

* **Worst corner** (η_c 0.66, combustor +1σ, pessimistic drag): +71 % in Phase 3A-R, before the Phase 4A engine
  changes (diameter and cycle unchanged, mass +1.84 kg). Not re-run.
* Take-off ground roll 54 m (V_LOF 51 m/s). Landing 177 m with flaps and the 0.6 m drag chute (300 m runway assumed,
  A1.7), in the powered-descent case.
* Of the 5.46 kg fuel in the powered-descent case, about 4.5 kg is burned at idle (descent, pattern, reserve), because
  idle fuel flow is 41 % of maximum.
* Dash hold: ~245 N (throttle 49 %) at 90 % speed, SM 12 %, bleed closed.

---

## 3. Rotor dynamics (`ax_rotor.py`, verified ROSS model)

**Result: API 684 separation criteria met** (operating range idle 77.5 % to MCS 105 %, i.e. 62.0-84.0 krpm):

| critical | amplification factor | position | requirement |
|---|---|---|---|
| 2.8 krpm | 0.56 | far below idle | none (AF < 2.5) |
| 12.4 krpm | 2.04 | below idle, critically damped | none |
| 19.6 krpm | 1.28 | below idle, critically damped | none |
| 39.9 krpm | 1.18 | 36 % below idle, critically damped | none |
| **122.3 krpm** | 5.88 | **46 % above MCS** | 23.9 % |

**What it took.** The Phase 3 mass-sized rotor passed at only 2 of 6 support settings: its bending mode (57-61 krpm,
71-77 % speed) sits just below idle. The stiffened rotor (2 mm drum, 24 / 12 mm shaft, 12 mm journals) passes at all
24 settings of the sweep, for +0.50 kg of rotor (1.10 → 1.60 kg). Unlike the centrifugal, the axial's pass does not
hang on a few millimetres of bearing span: the combustor was not shortened and the bending critical is 46 % above MCS.

---

## 4. Open risks (current status; none of these is resolved)

### 4.1 The axial compressor model is unvalidated at this scale (R4.1). OPEN, top risk.
* Efficiency, off-design loss, Howell stall and the peak-line surge surrogate come from the project's own
  stage-stacking model. It is verified against its own equations and reproduces the Phase 3 design point, but **no
  micro-scale multistage axial has been used to test it**.
* The only external check (NASA-CR-134827) supports its tip-clearance efficiency sensitivity (1.8 vs 2.0 points per 1 %
  of blade height). The same test shows clearance cutting the stall margin 12.8 → 8.7 %, **an effect the model does
  not have**.
* The peak-line surge surrogate failed by an order of magnitude on the one real stage it was checked against (a
  vaned-diffuser centrifugal, NASA HECC). It has no axial validation.
* The fielded loss split (section 5 of the report) is a modelling choice made to avoid an unphysical choke. It sets the
  shape of every speed line below design.
* **Everything in 4.2 to 4.5 inherits this.** The idle speed could be better or worse than 77.5 % on a real machine.
* **Mitigation available but not run:** a part-speed benchmark on NACA TR-758 (8-stage axial, 1943, stage-by-stage
  data; needs its geometry rebuilt and scanned figures digitised; large, subsonic and lightly loaded, so it would test
  the multistage matching logic, not micro-scale losses). Micro-scale validation needs a rig test.

### 4.2 Idle at 77.5 % speed, and the descent concept it forces. OPEN.
* Even with all three variable-geometry systems, the lowest acceptable steady speed at SLS is **77.5 %** (stator-1 stall
  below it). Idle thrust is **114 N**, idle fuel **10.0 g/s, 41 % of maximum** (the centrifugal: ~19 %; fielded
  micro-turbojets: 14-18 %).
* Idle thrust is **5-6 × the approach drag** (15-21 N). **The aircraft cannot descend or approach at idle.**
* The closure therefore needs **an engine-off descent** (shut down at the top of descent, glide from 5 km at L/D 7-9,
  dead-stick landing with flaps and the chute), or a thrust spoiler / reverser / large airbrake (not assessed).
* **Not assessed for the engine-off concept:** in-flight relight or restart (no windmill / starter analysis), a
  go-around capability (there is none without a relight), the rules' acceptance of a dead-stick landing, and the
  landing distance for a glide approach with no power.
* Relaxing the surge-margin criterion to 5 % does not lower the idle (stator 1 binds).

### 4.3 Start. NOT ANALYSED. OPEN.
* Below 70 % speed at SLS the model finds no converged steady point with the adopted geometry, and the front rows are
  beyond their Howell stalling deflection below 75 %. A start has to carry the rotor through that region.
* The starter is the centrifugal's 0.18 kg allowance. **Its adequacy for this duty (torque and power to well above
  half speed through a stalled front stage) has not been computed**, and the project has no start or rotating-stall
  model.

### 4.4 Variable-geometry hardware is unsourced. OPEN.
* Masses are geometric estimates plus three 75 g hobby-class servos (0.64 kg raw in total).
* **Not checked:** actuator loads (VIGV aerodynamic and friction torque, nozzle flap loads at NPR 2.8), a servo next to
  a 937 K exhaust, the ECU scheduling and failure modes (e.g. the nozzle stuck open costs thrust, the bleed stuck
  closed puts the engine into stall below 95 %), the bleed discharge path through the airframe.
* No fielded micro-turbojet with this variable geometry was found to anchor it.

### 4.5 Throttling at the dash condition. OPEN.
* At M 1.02 / 5 km with the bleed closed, the engine is acceptable only down to 87.5 % speed (184 N); rotor 1 stalls
  below. The dash hold (~245 N) is inside that range.
* Anything lower (a deceleration, descent from the dash, a thrust cut) needs the bleed open at altitude, which was not
  analysed.

### 4.6 Blade roots at 96 % of yield and five low-order resonances. OPEN.
* Stage 1 and 2 roots: 598 / 597 MPa at MCS against Fty 620 MPa, **only with a provisional 10 % thickness taper**. No
  margin for low-cycle fatigue (start-stop), foreign-object damage or tolerances.
* Blade 1F crossings: stage 1 × 2E at 61 %, **stage 2 × 2E at 79 %** and **stage 5 × 3E at 76 %** (both at idle, where
  the engine dwells), stage 4 × 3E at 60 %, **stage 6 × 3E at 95 %** (near maximum). No forced response, damping or
  inlet-distortion estimate; no retuning done.

### 4.7 Acceleration and transient margin: computed, quasi-steady only. OPEN.
* Idle 77.5 % → 98.5 % at SLS: **1.7 s** with a 5 % surge-margin reserve, **2.2 s** with 10 % (`ax_transient.py`).
  It is fast because the rotor is light (Ip 8.1e-4 kg m²) and the engine never crosses the low-speed range.
* At idle with a 10 % reserve only **2.2 kW** of excess power is usable: the steady margin there is 11.9 %.
* **Assumed, not shown:** the three variable-geometry systems follow their speed schedules instantly (actuator rates
  unknown, 4.4); the bleed closing at 95 % is a step whose transient is not modelled; no fuel-control, heat-soak or
  combustor dynamics. The reserves are measured against the unvalidated surge surrogate (4.1).
* Deceleration (the running line moving toward choke and the front stages toward stall as speed falls) is not
  analysed.

### 4.8 Nothing has been validated by a rig or bench test. OPEN.
Every number in this document is tool-predicted: cycle, efficiencies (fielded level borrowed from the centrifugal
debit), maps and operability, stresses, rotor dynamics, mass (calibrated on two centrifugal engines), mission.

### 4.9 Other open items (carried)
| item | status |
|---|---|
| **turbine on its 350 MPa blade-root limit** | conceptual allowable (A3.2); IN-713LC life data needed |
| **damped bearing supports** | cartridge design, temperature, nonlinearity not modelled |
| bearing DN 1.01e6 at MCS | at the 1e6 micro-gas-turbine reference |
| **mass calibration ×1.20** | anchored on two **centrifugal** engines (JetCat P400, AMT Nike); no axial micro-turbojet exists to check it, and the axial has 291 blades plus variable geometry |
| fielded technology level η_c 0.709 | borrowed from the centrifugal debit (A3A.1); the axial has no efficiency data of its own |
| worst-corner thrust margin | +71 % in Phase 3A-R; not re-run on the Phase 4A engine |
| engine length 599 mm | 41 % longer than the centrifugal (426 mm); the airframe was not re-laid out for it (Phase 2 fuselage assumed to accommodate it; installation not checked) |
| combustor | Phase 3 length rule (liner 157 mm), not re-checked; η_b and dP/P assumed |
| drag chute | required for a 300 m runway |

---

## 5. What Phase 6 (CAD / 3D) would start from if approved now

**Geometry that would be committed:** the section 1 design:
* compressor: 6 stages, 110 mm casing, 291 blades with the tapered stage-1/2 roots, drum rotor;
* VIGV, bleed manifold after stage 3 with band valve, variable nozzle;
* combustor OD 142.5 mm, liner 157 mm; turbine tip 57.3 mm;
* rotor: 2 mm drum, 24 / 12 mm shaft, 12 mm journals, damped mounts;
* envelope 142.5 × 599 mm.

**Proceeding to CAD before 4.1-4.4 are resolved means committing geometry that may have to change.** In particular:
* the **compressor blading** depends on the unvalidated model (4.1) and on the root and resonance fixes (4.6), which
  may change chords, counts and thickness in stages 1, 2, 5 and 6;
* the **variable-geometry hardware** has no sourced design (4.4); CAD would be inventing the actuation;
* the **descent concept** (4.2) changes the airframe (no change for an engine-off descent; spoilers or a reverser if
  not), and the fuel tank volume (1.88 vs 5.46 kg of fuel).

The parts least likely to change: the cycle point, the 142.5 mm diameter (set by the combustor), the turbine, and the
rotor-dynamic layout, which passes with margin.

---

## 6. Decisions for the reviewer

1. **Which engine goes forward:** the centrifugal baseline (Phase 6 already started) or this axial. Section 7 compares
   them.
2. **If the axial:** accept the engine-off descent concept (4.2) with its relight / go-around gap, or ask for a
   spoiler / reverser assessment.
3. **R4.1:** run the NACA TR-758 multistage benchmark of the stacking model (partial check, section 4.1), or accept the
   model to a rig test.
4. **Like-for-like comparison:** fly the centrifugal with the engine-off descent as well (its closure would then fall
   below 20.09 kg), so the two TOGWs compare on the same mission. Not run.
5. **Axial Phase 6:** **not started.** Approve, defer until 2-3 are resolved, or approve with the blading and the
   variable geometry explicitly held as provisional.

| | |
|---|---|
| Reviewer sign-off (Phase 5A → axial Phase 6) | not given |
| Date | |

---

## 7. Centrifugal (`docs/design_freeze.md`) against axial (this document)

Both at the fielded level, same brief, same airframe model, same calibrations.

| | centrifugal (baseline) | axial (option A) |
|---|---|---|
| compressor | 1 stage, 12 + 12 blades, OPR 4, 75 000 rpm | 6 stages, 291 blades, OPR 5, 80 000 rpm |
| variable geometry | none | VIGV + bleed + variable nozzle (3 actuators) |
| airflow / TSFC at dash | 1.326 kg/s / 0.164 kg/(N h) | 1.360 kg/s / 0.159 kg/(N h) |
| engine OD × length | **187** × 426 mm | **142.5** × 599 mm |
| engine dry mass (calibrated) | 6.85 kg | 6.86 kg |
| SLS maximum thrust | 631 N | 659 N |
| **dash thrust margin, nominal / pessimistic** | +55 / +29 % | **+103 / +88 %** |
| worst corner | +21.8 % (below the 25 % target) | +71 % |
| **SLS idle speed / thrust / fuel** | **~40 %** / - / ~19 % of max | 77.5 % / 114 N / 41 % of max |
| descent at idle | possible | **not possible** (idle thrust 5-6 × approach drag) |
| TOGW / margin | 20.09 / 4.91 kg (powered descent) | 22.12 / 2.88 kg (powered descent, not physically possible); 18.54 / 6.46 kg (engine-off descent) |
| acceleration (SLS, SM ≥ 5 % reserve) | 40 → 95 %: 6.6 s (cannot leave 40 % with a 10 % reserve) | 77.5 → 98.5 %: 1.7 s (2.2 s with 10 %); VG assumed instant |
| rotor dynamics | API pass, sensitive to ~11 mm of bearing span | API pass with 46 % margin on the bending mode |
| highest-stressed blade | impeller exducer at Fty at MCS by construction | stage-1/2 roots at 96 % of Fty (provisional taper) |
| blade resonance | exducer 1 × 19-vane passing at 39 % (idle) | 5 low-order 1F crossings, incl. at idle and 95 % |
| surge-margin prediction | unvalidated (surrogate failed on HECC; two tools disagree 28 vs 6.5 %) | unvalidated (own model, R4.1) |
| start | conventional (idle ~40 %) | not analysed (4.3) |
| hardware anchors for the architecture | 9 fielded micro-turbojets of the same type | none at this size |

**In short.** The axial trades a far better dash margin and a 44 mm smaller diameter for:
* an engine that cannot idle low enough to descend;
* three actuated systems with no sourced hardware;
* a longer engine;
* a compressor model with no micro-scale validation.

The centrifugal trades a thinner dash margin (worst corner below target) for an architecture with fielded precedent,
and a surge-margin question it shares with the axial in a different form.
