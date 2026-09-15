# Analysis coverage review (2026-09-15)

Companion to `docs/suite_architecture.md` and `docs/suite_build_plan.md`. It records an external review of the
project (by another agent) and checks each of its points against the project's own data. It says what analysis
exists, what is missing, and where the review's numbers do not match this engine. **It changes no engineering result
and no freeze decision.**

The missing items feed the suite's evaluator backlog (architecture doc, Appendix C) and the engineering checks E1-E3
below.

**Status key:** **done** = a tool run exists; **partial** = part of it exists; **missing** = nothing in the repo.

---

## 1. Headline points

| review point | status and verdict | evidence | goes to |
|---|---|---|---|
| T4-limited at SLS at 98.2 % speed; run an ISA+15 / +25 lapse first | **missing, and overdue.** Phase 1 set the envelope at ISA−15 to ISA+20 (E4), and A1.1 says "hot day checked in Phase 3". No hot-day run exists. The take-off is not the case at risk (631 N SLS on 20.1 kg is T/W 3.2; ground roll 46 m on a 300 m runway). **The case at risk is the dash on a hot day:** the pessimistic-drag margin is +28.5 %, only 3.5 points above the 25 % target, and the worst corner is already +21.8 %. Physics: with T4 capped, a hotter inlet lowers T4/T2, so each kilogram of air does less work. Corrected speed and airflow fall, and air density falls too | `docs/phase1_requirements.md` E4, A1.1; freeze 1.1, 2 | E1; atmosphere cases in the study |
| NPR ~3.4; a fixed convergent nozzle costs ~5 % at M 1 | **the numbers don't fit this engine, and the nozzle was already chosen with a tool run.** Fielded NPR at the design point is 2.76 (3.7 at tool level). D3.2 (pyCycle): a C-D nozzle gains 2 % (tool) / 0.2 % (fielded). Closed form (γ 1.33, T0 972 K, Cv 1; underexpanded choked vs ideal expansion): net-thrust loss 0.9 % at NPR 2.76, 2.2 % at 3.4, 5.4 % at 5.0. So "5 %" belongs to NPR ~5. The pressure term is ~20 % of gross thrust at NPR 2.76. pyCycle (0.2 %) and the closed form (0.9 %) differ; cause not isolated. **Agreed** that A8 is the main lever on where the running line sits | `design_log.md` D3.2; `data/phase3_cycle_trade.csv`; freeze 1.1 | A8 as a matching variable |
| PR 4 needs ~440 m/s tip, T3 ~190-195 °C, 7075-T6 is marginal; settle the material now | **already settled; the numbers don't fit.** The impeller is Ti-6Al-4V. U2 is 525 m/s at fielded η_c 0.70 (486 m/s at tool level). T3 at the dash is 520 K (247 °C); Al 2618 was ruled out on T3. Disc +86 % yield margin with the thermal gradient; burst ratio 1.90 | freeze 1.2; `engine_mass.py` header | material is a study field |
| 75 000 rpm with a 20 mm bore is DN 1.5e6; this drives lubrication and shaft thermal design | **the arithmetic is right, but the design uses 12 mm journals** (DN 0.95e6 at MCS, hybrid ball bearings, at the edge of the 1e6 reference). **Agreed on the gap behind it: lubrication, bearing heat generation and bearing temperature have not been analysed at all.** The rear bearing sits under the NGV | freeze 1.4, 4.6; no entry in docs or log | E3; L4 evaluator |
| installed thrust (inlet recovery, spillage, boattail, bleed, power extraction) belongs in the drag polar | **partial.** Inlet recovery is inside the cycle (normal shock + duct, 3.05 % of Pt). The boattail is in the airframe drag (cubic, D2.6). No spillage at the dash (capture sized for it). **Two gaps.** (1) The jetpipe friction found in Phase 6 (ΔPt/Pt 0.64 %, roughly −1.7 % thrust) was never fed back into the cycle; applied to the pessimistic margin, +28.5 % becomes about +26.3 %. (2) The Phase 2 3 % installation allowance, which included power extraction, was replaced by the duct loss in Phase 3, so power extraction is now zero. That holds only if every system runs from the battery (the accessory mass includes one), which is unverified. No bleed exists | `design_log.md` D6.4; `docs/phase2_airframe.md` A2.3 | E1; installation block in the study |

## 2. Layer by layer

| layer / item | status and verdict | evidence | suite level |
|---|---|---|---|
| **1** deck with real maps; running lines with surge margin | **done**, but the surge margin comes from the unvalidated surrogate (R4R.1) | `cc_mission.py` | L3 |
| **1** windmill and relight | **missing** | - | L3 |
| **1** transient: inertia, heat soak, slam acceleration, flameout margin on deceleration | **partial.** Quasi-steady acceleration with I_p under T4 and surge limits exists; heat soak, volume dynamics and deceleration / flameout do not | `cc_transient.py` | L3 |
| **1** Monte Carlo over efficiencies, losses, leakage, clearance | **missing.** One worst corner and a one-at-a-time sensitivity exist | `cc_sensitivity.py` | UQ use case |
| **1** PR × T4 carpet against the mission; "SFC-optimum PR 6-8" | **partial. The direction is right, the size is small.** Fielded pyCycle at T4 1150 K: TSFC 0.1642 at OPR 4 vs 0.1609 at OPR 6 (−2 %), but specific thrust falls 377 → 340 N s/kg (−10 %: more airflow for 500 N, so a bigger engine). OPR 4 was chosen for dash margin and diameter, where the combustor and diffuser ODs meet (F3R.5), not for SFC: sortie fuel is only 2.36 kg. Still missing: T4 values other than 1150 K in the Phase 3R chain, and the carpet evaluated on mission fuel and TOGW | `data/phase3_cycle_trade.csv`; F3R.5 | L1-L2 DOE |
| **2** inducer shroud relative Mach < ~1.3 | **done** (1.29; limit 1.33 from nine fielded engines) | `inducer_anchor.py` | validity rule V-TF-MREL |
| **2** clearance sensitivity "2-3 points per 1 % of clearance / passage height"; cold-build clearance from a thermal transient | **not measured here. Check the magnitude before adopting it:** a TurboFlow clearance sweep settles it (clearance is an input, 0.25 mm now). Cold-build clearance: missing | - | L2 sweep; L4 thermal-transient evaluator |
| **2** at least one URANS impeller-diffuser case | **missing** | - | L5 |
| **2** NGV throat area as the second matching knob | **partial.** TurboFlow designs the NGV with the cycle, but it is not treated as a matching variable | `turbine_design.py` | matching variable at L3 |
| **2** combustor pattern factor, altitude relight: rig problems | **agreed** | freeze 4.3, 4.5 | risk register |
| **3** burst above ~130 % of maximum speed | **done:** 1.90 × N_MCS (project criterion 1.20, 14 CFR 33.27) | freeze 1.2 | L1 constraint |
| **3** LCF life, creep at turbine rim temperature | **partial.** Disc creep negligible for Ti at 247 °C. Turbine allowable is 100 h rupture strength / 1.5 (A3.2), not a life calculation. LCF not done. The life requirement is small: A1.6, ≥ 10 hot cycles / 1 h | `docs/phase4_impeller_stress_gate.md`; A1.6 | L4 / L5 |
| **3** Campbell diagrams for impeller, diffuser vanes, NGVs, turbine blades; blade counts off low-order crossings | **partial: exducer only, static.** That already found the 19-vane crossing at idle (open risk 4.4). Diffuser vanes, NGVs and turbine blades: missing | `cc_blade_modes.py` | E2; L4; counts as design variables |
| **3** rotordynamics with real bearing stiffness and damping, ~20 % separation, unbalance response, balancing spec tighter than G2.5 | **partial.** Criticals and damped amplification factors with API separation are done (bending critical 34 % above MCS). Unbalance response and a balancing grade: missing | freeze 3 | L4 |
| **3** containment or a documented release case | **missing** | - | L5 |
| **4** controls: acceleration schedule, T4 / speed limiting, overspeed, start and relight logic, HIL | **missing.** Beyond the brief's conceptual scope, but needed before any hardware | - | later plugin layer |
| **5** component rigs, instrumented thrust stand, recalibrate the deck | **agreed** (freeze 4.5). The suite's error-band update is where test data would enter | freeze 4.5 | band estimation |
| tools: GasTurb / GSP, Vista CCD, CFturbo, Concepts NREC, CFX, FINE/Turbo, Abaqus / Ansys, XLRotor, DyRoBeS | **not adopted.** Student project on open tools. Adopted as candidates: validation cases for CFD (NASA CC3, Eckardt, Krain impellers) and OpenMDAO as the MDO wrapper | - | high-fidelity backlog |

## 3. Priorities that follow

The review's own "if resources are limited" list was: hot-day deck, impeller material and burst, Campbell diagram.
For this engine the material and burst are done, so the list becomes three engineering checks on the **current**
chain. Their answers do not wait for the suite, and their results later become golden values for it. Each is new
engineering work, so each needs the user's go-ahead and gets its own `design_log.md` entries.

- [ ] **E1: dash margin at hot and cold day, with installed thrust.** Run the Phase 3R deck (`cc_mission.py`
      machinery; pyCycle's flight-condition temperature offset) at ISA+20 / ISA−15 at the dash point and at SLS.
      Put the jetpipe loss (D6.4) into the cycle. Settle whether power extraction is really zero. Re-run the worst
      corner on the Phase 4 engine (freeze 4.6 says it was never re-run). Output: the pessimistic dash margin at each
      case, against the 25 % target. **It can move the baseline below its target.**
- [ ] **E2: Campbell diagrams for diffuser vanes, NGVs and turbine blades**, with centrifugal stiffening, and the
      exducer re-checked. Choose vane and blade counts off low-order crossings in the 35-105 % range. Belongs with the
      diffuser redesign (freeze decisions 1-2).
- [ ] **E3: bearing lubrication and thermal design, first pass.** Heat generation at DN 0.95e6, lubricant choice
      and flow, and rear-bearing temperature under the NGV.

Open question: the hot day. The Phase 1 envelope says ISA+20; the review suggests ISA+25.
