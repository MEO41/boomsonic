# Design freeze (Phase 5): status snapshot for review (2026-09-14)

**What this document is.** It is the brief's Phase 5 deliverable: a snapshot of the current design, compiled from Phase
3R (`docs/phase3r_centrifugal.md`) and Phase 4R (`docs/phase4r_centrifugal.md`) for the user's review. **It does not
claim the design is closed.** Several items that decide whether this geometry survives are still open, and section 4
states them with their current status. Per the brief, Phase 6 (CAD / 3D) does not start without the user's explicit
sign-off.

Every number here comes from a tool run or a cited relation (sources in the two phase reports and `design_log.md`).
Nothing has been measured on hardware. Numbers are given at the **fielded** technology level (η_c 0.70, η_t 0.75,
η_b 0.95, the level that reproduces commercial micro-turbojet TSFC) unless marked "tool".

---

## 1. Final architecture

Single-spool turbojet with a single-stage centrifugal compressor, annular combustor, single-stage axial turbine and
convergent nozzle, in a nose-pitot-fed fuselage.

### 1.1 Cycle (design point: Fn 500 N at M 1.02 / 5000 m ISA, T4 1150 K)

| quantity | fielded | tool level |
|---|---|---|
| net thrust / T4 | 500 N / 1150 K | 500 N / 1150 K |
| overall pressure ratio | 4.0 | 4.0 |
| airflow | 1.326 kg/s | 1.068 kg/s |
| fuel flow / TSFC | 0.0228 kg/s / 0.164 kg/(N h) | - / 0.138 kg/(N h) |
| compressor inlet (after intake) | 309 K, 102.1 kPa (normal shock 0.99999, subsonic duct loss 3.05 % of Pt) | |
| compressor exit | 520 K, 408 kPa | 490 K |
| turbine inlet / exit | 1150 K, 388 kPa / 972 K (699 C) | |
| turbine pressure ratio (tt) | 2.60 | |
| nozzle | convergent, A8 70.8 cm², NPR 2.76 | |
| fuel-air ratio / overall φ | 0.0163 / 0.244 | |

* Real-gas check: Cantera (n-dodecane surrogate) against pyCycle at the combustor exit gives T4 -4.0 K (-0.35 %),
  γ +0.0002, cp +0.6 %.
* Sea-level static: 631 N at 98.2 % speed, limited by T4. 100 % speed would need T4 1182 K.

### 1.2 Compressor: single-stage centrifugal (`ce75000_opr4_t1150_b15_cap`)

| item | value |
|---|---|
| spool speed | 75 000 rpm; MCS (105 %) 78 750 rpm |
| why 75 000 rpm | inducer shroud relative Mach 1.29 at the fielded airflow, inside the range of 9 fielded micro-turbojets (1.10-1.33) |
| impeller | Ti-6Al-4V, **12 main + 12 splitter blades**, **exit backsweep -15°**, boreless hub with back-face boss |
| impeller exit radius / tip speed | 66.9 mm (D2 134 mm) / 525 m/s (552 m/s at MCS); tool level 61.9 mm / 486 m/s |
| eye tip / hub radius | 49.7 / 17.4 mm |
| exit width, effective / physical | 10.7 / 11.8 mm (blade blockage 9 %; corrected in Phase 6 from a transcription "12.0", data 11.796 mm) |
| exducer blade root | 2.24 mm, tapering to 0.8 mm; sized so its peak stress at MCS equals the minimum yield (Kt 1.4) |
| inducer throat | area ratio 0.75 of the eye (10 % choke margin at design speed) |
| diffuser | vaneless gap to 1.06 r2, then a **19-vane** radial vaned diffuser to R4/R2 1.35, then an axial deswirl; exit Mach 0.21 |
| efficiency (η_tt) | tool: TurboFlow 0.817, NASA turbo-design 0.803 (PR 4.05 vs 4.01, same geometry); fielded 0.70 |

**Impeller stress at MCS** (Ti-6Al-4V, minimum basis Fty 620 / Ftu 681 MPa at ~250 C):
* exducer root 618 MPa, equal to Fty by construction;
* inducer root 196 MPa;
* disc 335 MPa with the thermal gradient (+86 % yield margin);
* burst ratio 1.90 (>= 1.20 required).

### 1.3 Turbine: single-stage axial

| item | value |
|---|---|
| material / blades | IN-713LC; **34 NGV / 28 rotor blades**; blade heights 23 / 24 mm |
| tip radius | 61.1 mm, **exactly on the 350 MPa blade-root stress limit** at 75 000 rpm (conceptual allowable, A3.2) |
| turbine OD | 127 mm (inside the engine envelope) |
| efficiency (η_tt) | tool 0.936 (TurboFlow; 0.933 re-designed at the fielded flow); fielded 0.75 |

### 1.4 Combustor, rotor, envelope

| item | value |
|---|---|
| combustor | annular; casing OD 183.6 mm (grown to the diffuser envelope in Phase 4); inner radius 22.6 mm; **liner 150 mm** (0.8 × the Phase 3 rule of 3 × annulus height); reference velocity 23.6 m/s; η_b 0.95 and dP/P 0.05 assumed |
| rotor | overhung impeller and overhung turbine on two hybrid ball bearings in the shaft tunnel; **AISI 4340 tube shaft 32 × 25.6 mm**, 12 mm journals; **bearing span 192 mm**; damped soft supports (k ~1.75e6 N/m, c ~900 N s/m); rotor 2.11 kg, Ip 2.13e-3 kg m² |
| **engine envelope** | **OD 187 mm** (186.6, set by the compressor diffuser; combustor 183.6, turbine 127) × **length 426 mm** |
| **engine dry mass** | **6.85 kg** calibrated (bottom-up 5.70 kg × 1.20 from the JetCat P400 / AMT Nike validation; range 6.49-7.21 kg) |

Largest raw mass items (kg, before calibration):
* impeller 0.92;
* outer casing 0.73;
* shaft 0.58;
* combustor liners 0.54;
* shroud / inlet 0.44;
* diffuser and deswirl 0.39;
* shaft tunnel and bearing housings 0.35;
* turbine disc 0.28.

Accessories (ECU, pump, etc.) are carried separately: 1.60 kg (A3.7).

---

## 2. Airframe closure (S 0.30 m², Phase 2 airframe; `cc_closure.py`, `data/phase4r_closure.json`)

Fuel comes from the sortie flown on the engine's real-map deck: TurboFlow compressor and turbine maps in pyCycle,
T4-limited max throttle. TOGW is iterated on that fuel.

| mass item | kg |
|---|---|
| engine (calibrated) | 6.85 |
| engine accessories | 1.60 |
| structure | 3.82 |
| landing gear + drag chute | 1.27 |
| fuel system | 0.40 |
| systems, avionics, prize instrumentation | 2.02 |
| growth allowance (15 %) | 1.13 |
| fuel: sortie 2.36 + 120 s idle reserve 0.54, + 3 % unusable | 2.98 |
| **TOGW** | **20.09** |
| **margin to 25 kg** | **4.91** |

| performance check | nominal wave drag | pessimistic wave drag |
|---|---|---|
| **dash thrust margin at M 1.02 / 5 km** (target 25 %) | **+54.7 %** | **+28.5 %** |
| minimum excess thrust, transonic acceleration at 5 km | 177 N | 116 N |
| brake release to M 1.02 at 5 km | 27.7 s | 27.9 s |
| 3 g sustained turn at M 0.9 / 5 km, excess thrust | +283 N | +283 N |

* **Worst corner** (η_c 0.66, combustor +1 σ, pessimistic drag): **+21.8 %, below the 25 % target.** It was evaluated
  in Phase 3R, before the Phase 4 engine changes (the diameter and cycle did not change; the mass rose 0.11 kg), and has
  not been re-run on the Phase 4 engine.
* **Take-off:** ground roll **46 m**, V_LOF 48.6 m/s.
* **Landing** at 17.7 kg (Phase 2 model, μ_brake 0.3): **175 m with flaps and the 0.6 m drag chute**; 194 m chute
  without flaps; **316 m with flaps only**. Against the 300 m runway assumption (A1.7) the chute is required.
* Diameter sensitivity: the one validation engine whose diameter the compressor sets (AMT Nike) is over-predicted by
  5.7 %. Calibrating to it gives 177 mm and +67 / +42 % margin. It is not applied.

---

## 3. Rotor dynamics (`docs/phase4r_centrifugal.md` section 5, `plots/phase4r_rotor_final.png`)

**Result: API 684 / 617 separation criteria met** (ROSS, verified; damped criticals with squeeze-film / O-ring supports;
operating range 35-105 %, i.e. 26-79 krpm):

| critical | amplification factor | position | requirement |
|---|---|---|---|
| 8.3 krpm (rigid-body mode) | 2.64 | 68 % below the minimum operating speed | 5 % |
| 14.4 krpm (rigid-body mode) | 1.28 | below idle, critically damped | none |
| **105.6 krpm (first shaft bending)** | 29 | **34 % above MCS** | 25.8 % |

The bending mode is 34 krpm at rest. The gyroscopic moments of the overhung impeller and turbine stiffen its forward
branch, which puts the synchronous crossing at 105.6 krpm.

**What it took.** As first laid out (Phase 3 combustor rule, 235 mm bearing span), the first bending critical sat at
38-59 krpm for 16-28 mm shafts, inside the running range. The bearings carry only 4 % of that mode's strain energy, so
dampers cannot help. Its frequency is set by the bearing span, which is mostly the combustor. The fix:
1. **Combustor shortened 20 %** (liner 188 → 150 mm; span 235 → 192 mm) **and grown outward** into the free room under
   the diffuser (OD 170 → 184 mm, no engine-diameter cost). Liner volume is 94 % of the Phase 3R combustor, and the
   volume-corrected loading parameter is 0.92 × the 7-engine reference mean (-0.42 σ of their spread; Phase 3R was 1.00).
   That is near parity, not exact.
2. **Thin-wall shaft tube 32 × 25.6 mm** (ID/OD 0.8, more stiffness per unit mass), with 12 mm journals (bearing DN
   0.95e6 at MCS).
3. **Damped soft bearing mounts** (k ~1.75e6 N/m, c ~900 N s/m) for the two rigid-body modes.

Bearing loads: 16.5 N front / 4.2 N rear at 1 g; gyroscopic 87 N per rad/s of pitch or yaw rate.

**The pass holds only for this span and shaft.** In the stiffening sweep, lengthening the span by about 11 mm (liner ×0.85
instead of ×0.80) dropped the bending critical from 105 to 96 krpm with the same 32 mm tube and 12 mm journals, below
the 99 krpm requirement.

---

## 4. Open risks (current status; none of these is resolved)

### 4.1 Compressor surge margin: no validated prediction method exists for this stage type. OPEN, top risk.
* **What is known.** Design-point pressure ratio and efficiency are confirmed by two independent tools (TurboFlow and
  NASA turbo-design agree within 1 % on PR and 1.5 points on efficiency). The surge line is not known.
* **The two tools disagree on the same impeller.** Design-point surge margin by the peak-of-characteristic surrogate:
  **28 % (TurboFlow)** against **6.5 % (turbo-design)**. turbo-design's 100 % speed line is nearly flat (PR within 1.3 %
  from 70 % to 108 % of design flow), so its peak is ill-defined.
* **The surrogate itself failed its only validation against real data** (`hecc_surge_check.py`). On NASA's HECC stage
  (measured to surge):
  * measured design-point surge margin **8.4 %**, with the pressure ratio still rising at the last stable point
    (95 % of design flow);
  * turbo-design's characteristic keeps rising down to 61 % of design flow, so the surrogate implies >= 73 %: wrong by
    roughly an order of magnitude.
* **Why.** In a vaned-diffuser stage, surge is triggered by diffuser (vane) stall. **Neither tool models diffuser
  stall.** Every surge-margin number in Phase 3R and Phase 4R (the 28 % design margin, 22-27 % on the ground running
  line, and the acceleration limits) comes from this unvalidated surrogate.
* **What the -15° backsweep choice rests on.** Both tools and the textbooks agree on the direction (more backsweep, more
  stability). The magnitude is not validated. The backsweep was chosen mid-window on the TurboFlow numbers.
* **Status of mitigation:** **a diffuser redesign for wider stall range was recommended** (fewer or low-solidity vanes,
  larger vaneless gap) **but has not been run.** Alternatives listed but not evaluated:
  * a vaneless diffuser;
  * -20° backsweep (+11 to +14 points of surrogate margin, dash margin +24 %);
  * a variable nozzle;
  * rig test.

  No approved tool currently predicts vaned-diffuser stall; this needs a sourced diffuser-stall method or test data.

### 4.2 Surge margin in the idle range: a separate, sharper transient risk. OPEN.
* **Ground running line** (TurboFlow surrogate, `phase3r_mission_..._running_lines.csv`): surge margin 8.4-8.7 % at
  35-40 % speed and 13 % at 45 %, against 22-27 % above 55 %. These are the same surrogate as 4.1, so the real values
  may be lower.
* **Effect on acceleration** (`cc_transient.py`; T4 <= 1150 K):
  * **with a 5 % transient reserve**, 40 → 95 % takes 6.6 s, and almost half of it is spent between 40 and 45 %, where
    the surge margin, not the temperature, holds the excess power to about 0.5 kW;
  * **with a 10 % reserve the engine cannot accelerate from 40 % at all.**
* This is independent of the diffuser outcome: the idle-range margin is thin even by the optimistic surrogate.
* **Status: a start / handling-bleed provision was proposed but has not been sized or integrated** (no port location,
  valve, schedule, or effect on the cycle and the mass). A higher idle (45 %) also shortens the acceleration to 3.5 s;
  it is not adopted.

### 4.3 Combustor shortened 20 % for rotor dynamics: combustion performance unverified. OPEN.
* The liner is 150 mm, 2.2 × annulus height, against the 3.0 rule used through Phase 3R.
* The sizing basis (Lefebvre theta scaled on 7 fielded engines) has no length term. Treating liner volume as the
  residence measure puts it at -0.42 σ of the reference spread.
* Combustion efficiency, pattern factor, pressure loss (0.05 kept) and lean stability at this length have **not been
  checked by any tool or data**.
* If the combustor has to get longer again, the rotor pass in section 3 is lost (see 5).

### 4.4 Diffuser vane count excites the exducer at idle: vibration / fatigue. OPEN.
* Screening modal model (Morley plate, verified -1.5 %; static frequencies): exducer mode 1 at 9.33 kHz **crosses the
  19-vane passing frequency at 39 % speed, i.e. at idle**, where the engine dwells. Mode 2 (16.0 kHz) crosses at 67 %.
* Centrifugal stiffening, which raises the crossings somewhat, is not modelled. No forced-response or damping estimate
  exists.
* **This is a live high-cycle-fatigue concern until the vane count is redesigned.** 15-17 vanes would move the static
  crossings off idle and full power. That choice belongs with the diffuser redesign in 4.1, which has not been run.

### 4.5 Nothing has been validated by a rig or bench test. OPEN.
Every number in this document is tool-predicted:
* cycle and component efficiencies (fielded level set by vendor TSFC data);
* maps and operability;
* stresses;
* rotor dynamics;
* mass (calibrated on two engines);
* mission.

The only hardware anchors are published data sheets (TSFC, mass, length, idle) and NASA's HECC measurements, which
were used as checks, not as tests of this design.

### 4.6 Other open items (carried; each is documented in the phase reports)
| item | status |
|---|---|
| **impeller exducer root at Fty at MCS by construction** | zero margin above the 105 % speed basis; 3D FE (rake / lean), low-cycle fatigue for start-stop cycles not done |
| **turbine on its 350 MPa blade-root limit** | conceptual allowable (A3.2); IN-713LC life data needed |
| **damped bearing supports** | cartridge design, temperature, nonlinearity not modelled; mass not separately sourced (inside the housing allowance) |
| bearing DN 0.95e6 at MCS | at the edge of the 1e6 micro-gas-turbine reference |
| **diffuser sets the engine diameter** | R4/R2 1.35 not optimised (no approved tool can size it); the Nike check suggests about 10 mm conservatism |
| worst-corner thrust margin +21.8 % | below 25 %; not re-run on the Phase 4 engine |
| fielded technology level (η_c 0.70, η_t 0.75, η_b 0.95) | from vendor TSFC; the design has no efficiency data of its own |
| mass calibration ×1.20 (1.14-1.27) | two reference engines |
| compressor map above 105 % corrected speed | missing (cold, low-Mach corner of the deck above 2.5 km: no surge margin computed there) |
| idle fuel 19 % of max | fielded engines 14-18 %; the model's low-speed end is ~5 points of speed pessimistic (P400 benchmark) |
| drag chute | required for a 300 m runway |
| Phase 2 climb segment | not flight-path limited at T/W > 1 (optimistic time, small fuel effect) |
| TurboFlow slip patch | every compressor result depends on `turboflow_fixes.py` (upstream defect) |

---

## 5. What Phase 6 (CAD / 3D) would start from if approved now

**Geometry that would be committed:** the section 1 design:
* impeller: 134 mm, 12 + 12 blades, -15°, 2.24 mm exducer root;
* diffuser: 19-vane radial vaned, R4/R2 1.35, plus axial deswirl;
* combustor: OD 184 mm, 150 mm liner;
* turbine: single stage, tip 61.1 mm;
* rotor: 32 × 25.6 mm tube shaft, 12 mm journals, 192 mm bearing span, damped soft mounts;
* envelope: 187 × 426 mm.

**Proceeding to CAD before the diffuser redesign and the surge-margin question (4.1, 4.2, 4.4) are resolved means
committing geometry that may have to change.** In particular:
* **The diffuser is the most likely part to change**: vane count and type, radius ratio, vaneless gap, possibly a
  vaneless diffuser. It sets the engine diameter (drag, and the dash margin at about 3 N per mm), the front-bearing
  housing (which sits in the diffuser hub), and the axial length ahead of the combustor.
* **The API rotor-dynamics pass assumed the current bearing span and shaft.** Anything that moves the front bearing
  aft, or lengthens the combustor (for example if 4.3 fails), eats into the bending-critical margin. About 11 mm more
  span was enough to fail the criterion in the sweep. A vaneless diffuser or -20° backsweep would also change the
  impeller's mass and inertia, which feed the rigid-body modes and the gyroscopic stiffening.
* **A start-bleed provision (4.2)** would add a port, a valve and ducting in the compressor or diffuser region that CAD
  would otherwise not reserve space for.
* **The combustor length (4.3)** is set by rotor dynamics, not by combustion data. A combustor result could force the
  combustor, the span and the shaft to change together.

The parts least likely to change are the cycle point, OPR 4 / 75 000 rpm, the turbine, and the airframe closure, which
has 4.9 kg of mass margin to absorb changes.

---

## 6. Decisions for the reviewer

1. **Surge margin (4.1 / 4.2):**
   * run the diffuser redesign for stall range, which needs a sourced diffuser-stall method;
   * or evaluate another mitigation: a vaneless diffuser, -20° backsweep, start bleed, or a variable nozzle;
   * or accept the risk to a rig test.
2. **Diffuser vane count (4.4):** together with (1).
3. **Combustor length (4.3):** accept 150 mm pending data, or require a combustor check first.
4. **Phase 6:** **not started.** Approve, defer until 1-3 are resolved, or approve with the diffuser and rotor
   (bearing span / shaft) explicitly held as provisional.

| | |
|---|---|
| Reviewer sign-off (Phase 5 → Phase 6) | not given |
| Date | |
