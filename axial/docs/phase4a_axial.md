# Phase 3A-R / 4A (axial, option A): refresh, turbomachinery checks, operability and closure (2026-09-14)

**Scope.** The user asked to take the early 6-stage axial concept "where we left off" and finish it "as you did with the
centrifugal one". That concept is the pure axial baseline of Phases 3 and 4 (OPR 5, 6 stages, 80 000 rpm; design_log
D4.2), last worked in Phase 4 on operability (D4.4) and rotor dynamics (D4.R2), before the user switched the baseline
to the centrifugal (D3R.0). **User decision: pause at the axial freeze for review before any axial CAD** (brief rule 4).

This report covers the same steps the centrifugal went through:
* a Phase 3R-style refresh of the Phase 3 axial numbers (**Phase 3A-R**);
* the Phase 4 items: blade and disc stress, blade vibration, operability with variable geometry, rotor dynamics,
  acceleration, and the Phase 2 ↔ 4 closure (**Phase 4A**).

The freeze snapshot is `axial/docs/design_freeze_axial.md`. **The centrifugal design and its files are not changed.** Axial
tags end in `_3r` (e.g. `ax80000_opr5_t1150_n6_cap_3r`); data are in `axial/data/phase3ax/` and `axial/data/phase4ax/`.

> **Read every compressor number below with open risk R4.1 in mind.** Axial-stage efficiency, off-design loss, stall
> and the surge line all come from the project's own Howell cascade / stage-stacking model. It is verified against its
> own equations and against the Phase 3 design point, but **it has not been validated on any micro-scale axial** (one
> published clearance sensitivity agrees; section 3). The surge line is the peak of each stacking speed line, a
> surrogate that failed badly on a vaned-diffuser centrifugal (`hecc_surge_check.py`) and has no axial validation
> either.

## Result in brief

| item | result |
|---|---|
| stages | 6 axial compressor stages (rotors 14/17/21/26/30/35, stators 14/18/22/26/32/36; 291 blades); 1 axial turbine stage (~33 NGV / ~27 rotor blades) |
| spool speed | 80 000 rpm (unchanged); MCS 84 000 rpm |
| compressor efficiency | tool (Howell on the TurboDesigner blading) 0.832; **fielded 0.709** (re-referenced, A3A.1; was 0.730) |
| turbine efficiency (η_tt) | tool 0.917 (TurboFlow, re-designed at the fielded cycle, tip on the 350 MPa limit); fielded 0.75 |
| cycle at dash (fielded) | W **1.360 kg/s**, TSFC **0.159 kg/(N h)**, T4 1150 K, Pt3 511 kPa |
| engine | **OD 142.5 mm** (combustor-set); **length 599 mm**; **dry mass 6.86 kg** calibrated (6.50-7.22), incl. 0.64 kg raw of variable geometry |
| variable geometry (option A) | VIGV (15° closure), 10 % overboard bleed after stage 3 (open below 95 % speed), variable nozzle to 2.0 × A8 by 80 % speed |
| **idle (SLS)** | **77.5 % speed**, 114 N, 10.0 g/s (41 % of the 100 % fuel flow); stator-1 stall below |
| rotor | 1.60 kg, Ip 8.0e-4 kg m²; criticals 2.8 / 12.4 / 19.6 / 39.9 krpm (damped, below idle) and 122.3 krpm (46 % above MCS): **API pass** |
| acceleration, idle 77.5 % → 98.5 % (SLS, T4 ≤ 1150 K) | **1.7 s** with a 5 % surge-margin reserve, 2.2 s with 10 % (light rotor, short span; the VG assumed to follow its schedule instantly) |
| closure, powered idle descent (as the centrifugal) | **TOGW 22.12 kg**, margin 2.88 kg; dash margin +103 / +88 %; time to dash 29.1 s; ground roll 54 m; landing 177 m (flaps + chute) |
| closure, engine-off descent | TOGW 18.54 kg, margin 6.46 kg; same dash margins |

**What changed the picture relative to Phase 4:**
1. **The axial cannot idle below 77.5 % speed** even with all three variable-geometry systems (section 6). Its idle
   thrust (114 N static) is 5-6 × the approach drag (section 7), so **a normal idle descent and approach are not
   possible**. The engine has to be shut down at the top of descent and the aircraft landed dead-stick, or the airframe
   needs a thrust spoiler or large airbrakes (not assessed).
2. **The stage-1 and stage-2 blade roots are at 96 % of yield at MCS**, and only with a provisional 10 % thickness
   taper (section 4). Five low-order blade resonances lie in or near the operating range, one (stage 6, 1F × 3E) at
   95 % speed.
3. The dash performance is unchanged and remains the axial's strength: **+103 / +88 % dash thrust margin** (the
   centrifugal: +55 / +29 %), from the 142.5 mm diameter (the centrifugal: 187 mm).

---

## 1. Why a refresh was needed (F3A.1, A3A.1)

The Phase 3 / 4 axial numbers were stale in three ways:
1. **The fielded efficiency.** A3.4 debited the axial tool efficiency by 0.70 / 0.794 so it would sit at the same
   technology level as the centrifugal. The 0.794 was the Phase 3 centrifugal tool efficiency, computed with
   TurboFlow's defective slip model (F3R.1). The corrected Phase 3R centrifugal tool efficiency is 0.8175, so the
   debit becomes K_F = 0.70 / 0.8175 = 0.856 (was 0.882), and the fielded axial efficiency **0.709** (was 0.730).
   This is still an assumption (A3.4): the axial has no fielded efficiency data of its own.
2. **Compressor scaling.** Phase 3 scaled the tool-level geometry by √W to the fielded flow. At fixed speed that cannot
   match both the flow (area ~ r²) and the work (~ U²). Phase 3R found the same flaw for the impeller (F3R.3).
3. **Turbine.** The √W-scaled turbine ran past its 350 MPa blade-root limit (F3R.3 applies to every Phase 3 case).

The mass and length calibrations had also been re-anchored in Phase 3R (×1.20 / ×1.21).

## 2. Phase 3A-R trade and refreshed baseline (`ax_trade.py`; D3A.1, F3A.2, D3A.2)

**Method.** For each case:
1. **Compressor designed AT the fielded cycle.** TurboDesigner is run at the fielded flow, inlet state and PR 5, with the
   fielded efficiency setting the work. The Howell loss model is then evaluated once on that blading and reports its
   tool-level efficiency. Phase 3 limits apply: diffusion factor ≤ 0.5, de Haller ≥ 0.72, rotor-1 tip relative Mach
   ≤ 1.35, last blade ≥ 10 mm. Grid: 70-90 krpm × 5-8 stages × hub/tip 0.40-0.55 × Cx 170-200 m/s; 98 of 240 designs
   are feasible.
2. **Turbine re-designed by TurboFlow** at the fielded cycle, with the 350 MPa root limit and the envelope cap.
3. Engine and airframe as Phase 3R: θ-scaled combustor, `engine_mass`, the 3R calibrations, Phase 2 airframe drag.
4. Worst corner: η_c × 0.66/0.70, combustor +1σ, pessimistic wave drag.

| rpm / stages | tool η of blading | rotor-1 M_rel | turbine tip (on the limit) | L | dry mass cal. | margin nom / pess | worst | TOGW |
|---|---|---|---|---|---|---|---|---|
| 70k / 8 | 0.832 | 1.13 | 65.5 mm | 714 mm | 6.41 kg | +104 / +88 % | +71 % | 18.03 kg |
| 75k / 7 | 0.832 | 1.20 | 61.1 mm | 651 mm | 5.64 kg | +104 / +88 % | +71 % | 17.27 kg |
| **80k / 6** | 0.832 | 1.27 | 57.3 mm | **599 mm** | **5.02 kg** | **+104 / +89 %** | **+71 %** | **16.65 kg** |
| 85k / 6 | 0.827 | 1.32 | 53.9 mm | 593 mm | 4.83 kg | +104 / +89 % | +71 % | 16.46 kg |

(Masses and TOGW here are Phase 3A-R values, before the Phase 4A changes in section 10.)

Every case is **combustor-set at OD 142.5 mm**, so drag and margins are equal. The choice is then length and mass:
80k / 6 is 51 mm shorter and 0.62 kg lighter than 75k / 7. 85k saves only 0.19 kg (inside the ±5 % mass calibration
band) but takes rotor 1 to M_rel 1.32 of the 1.35 limit and raises bearing DN by 6 %. **Baseline: 80 000 rpm, 6 stages,
hub/tip 0.40, Cx 200 m/s**, the same speed and stage count as Phase 3 / 4.

**Refreshed baseline at the dash point** (fielded; `axial/data/phase3ax/axt_ax80000_opr5_t1150_n6_cap_3r.json`):

| quantity | value |
|---|---|
| net thrust / T4 | 500 N / 1150 K |
| airflow / fuel flow / TSFC | 1.360 kg/s / 22.0 g/s / 0.159 kg/(N h) |
| compressor inlet / exit | 309 K, 102.1 kPa / 559 K, 511 kPa (PR 5.0) |
| turbine inlet / exit | 1150 K, 485 kPa / 937 K, 151 kPa (PR 3.20) |
| nozzle | convergent, A8 70.2 cm², NPR 2.80, Vj 556 m/s |
| compressor | casing 110.3 mm; rotor-1 tip radius 52.4 mm, hub 20.8 mm; inlet Mach 0.59; rotor-1 tip M_rel 1.27; worst DF 0.46, de Haller 0.72; last blade 11.8 mm; length 196 mm |
| turbine | hub 34.4 / tip 57.3 mm, chord 11.5 mm, ~33 NGV / ~27 rotor blades; tool η_tt 0.917 |

Against Phase 3: fielded airflow 1.314 → 1.360 kg/s (lower efficiency, more air per newton), mass 5.74 → 5.02 kg (the
turbine re-design), length 611 → 599 mm, dash margin unchanged.

## 3. An attempt to validate the axial model (F3A.3)

Published small-axial test data were searched for a check of R4.1:
* **NASA-CR-134827** (AiResearch 1976, scaled single-stage transonic axial, 70-110 % speed). Tip clearance 1.0 → 2.2 %
  of blade height (both with casing treatment) cost 2.2 efficiency points, ≈ 1.8 points per 1 % of clearance. The
  model uses 2.0 points per 1 %: **consistent**. The same test shows stall margin falling 12.8 → 8.7 %; **the stacking
  model has no clearance effect on stall**.
* **NACA TR-758** (8-stage axial, 1943) has speed lines at 5 000-14 000 rpm and stage-by-stage pressures. A multistage
  part-speed benchmark of the stacking model is possible, but the geometry would have to be rebuilt and the scanned
  characteristics digitised, and the machine is large, subsonic and lightly loaded. **Not run**; offered at the freeze.
* NASA-TM-106999 (small 2-stage rig, 1995): inlet calibration only, no maps.

**R4.1 stays open.** Only the clearance sensitivity is supported by data.

## 4. Blades and discs (`ax_rotor_stress.py`, `axial/data/phase4ax/rotor_stress_<tag>.json`; F4A.1)

Ti-6Al-4V, minimum basis Fty 620 / Ftu 681 MPa; MCS 105 % (84 000 rpm).

**Verification.** The rotating-beam FE reproduces the static cantilever eigenvalues (3.5160 / 22.0345) exactly and
Wright et al. (1982) at speed parameters 1 and 2 (3.6816 / 4.1373) to 0.001 %.

**Blade roots** (centrifugal + gas bending on a biconvex section, × Kt 1.4):
* The mass model's constant-section stage-1 blade reaches **677 MPa at MCS: it fails.** The tip speed is 461 m/s at
  MCS, and a 32 mm tall blade with a constant section carries all of its own outer mass through the root.
* **A 10 % thickness taper** (root 1.65 / tip 1.35 mm, same mass) moves material inboard and gives **598 MPa (96 % of
  Fty)**. Stage 2 is at 597 MPa (96 %); stages 3-6 at 523-550 MPa. **The taper is provisional geometry**, and 4 %
  margin to minimum yield leaves nothing for fatigue or the start-stop cycles.

**Discs.** The mass model's 450 MPa constant-stress discs give a burst ratio of 1.08 at MCS (Robinson, k 0.85), below
the ≥ 1.20 used for the impeller. Re-sized to 365 MPa at design speed (402 MPa at MCS): burst ratio 1.20 for
**+0.009 kg**, because the 4 mm minimum rim governs these small discs.

**Blade vibration** (`axial/plots/phase4a_blade_campbell.png`; 1F with centrifugal stiffening, taper included). Low
engine-order crossings in the likely operating range:

| stage | crossing | speed |
|---|---|---|
| 1 | 1F × 2E | 61 % |
| 2 | 1F × 2E | 79 % |
| 4 | 1F × 3E | 60 % |
| 5 | 1F × 3E | 76 % |
| **6** | **1F × 3E** | **95 %**, near maximum speed |

Stages 2 and 5 cross just around idle (77.5 %) and stage 6 near full speed, where the engine dwells. Low engine orders
(2E, 3E) are typically driven by circumferential inlet distortion and struts; no distortion estimate exists for the
nose-pitot intake. Vane-passing crossings exist only with 2F, at 40-43 % (below idle). **No retuning was done, and there is no
forced-response or damping estimate.** The plot uses a Southwell interpolation between the FE static and 100 %
frequencies; the crossings in the table are the FE values.

![blade Campbell](../axial/plots/phase4a_blade_campbell.png)

## 5. Three model problems found and fixed (F4A.2)

Running the Phase 4 operability chain on the refreshed design exposed three problems. Phase 3 / 4 results are unchanged
by the fixes (regression: PR 5.031, η 0.831 on the Phase 3 design).

1. **Wrong velocity triangles.** `axial_offdesign.Compressor` rebuilt the TurboDesigner triangles at the loss-model
   efficiency (0.832). The 3A-R blading was sized at 0.709. Fix: rebuild at `eta_sizing` when present.
2. **Tool-level losses on a blading sized for fielded work.** The stacking design point over-delivered PR, putting
   the design in the wrong place on its own map. Scaling the *whole* row loss up to the fielded efficiency (stage η
   −0.103) doubled the incidence parabola as well, and every flow choked below 80 % speed: a model artefact. **Adopted
   (`axial_offdesign.fielded`):** the design point is calibrated to the fielded 0.709 and PR 5.09 at the design flow;
   off design, only the tool-level (Howell) part follows the incidence parabola, and the fielded debit (clearance,
   Reynolds number, surface finish type losses) is a **constant extra loss** (ΔY 0.054-0.058 per row). Howell stall is
   unchanged (deflection-based). With this split the design surge margin to the peak line is ~14 %, as in Phase 4.
3. **pyCycle off-design start.** `cycle_model.set_design` seeds every off-design point with W 2.0 lbm/s, FAR 0.018 and
   turbine PR 2.0. At η_c 0.730 (Phase 4) Newton converges from there; at 0.709 (W 3.0 lbm/s, turbine PR 2.64) it
   diverged to NaN at every point. The Phase 4 maps failed the same way at 0.709 and converged at 0.730, so the maps
   were not the cause. **Fix:** `cycle_model.seed_od_from_design` copies every implicit state from the design point and
   re-solves; the off-design point is then marched from the design flight condition. Verified: it reproduces the
   design (500 N, 1150 K); SLS 100 % gives 686 N at T4 1169 K. No Phase 3 / 4 script uses it.

## 6. Operability and variable geometry (`ax_operability.py`, `ax_operability_summary.py`; D4A.1)

**Why a multistage axial is hard to throttle.** At the design point every stage runs at its design incidence. As speed
falls, the pressure ratio falls much faster than the speed, so the air in the rear stages is less dense than the
design assumed. With the same annulus area, the rear stages then see *more* axial velocity than their blade speed
suits (they unload and head toward choke), while the front stages see *less* (their incidence rises and they head
toward stall). On the SLS running line, rotor 1 passes its Howell stalling deflection below 85-90 % speed on this
design, as Phase 4 found. The three cures act on different parts of this mismatch:
* **VIGV** adds pre-swirl, which lowers rotor-1 incidence (but loads stator 1);
* **bleed after stage 3** lets the front stages pass more flow than the rear stages can take;
* **opening the nozzle** lowers the back pressure the compressor works against, which moves the running line away
  from surge at the cost of thrust.

**Acceptance criteria (Phase 4):** a steady point is acceptable if it is converged, T4 ≤ 1150 K, no row is beyond its
Howell stalling deflection, and SM to the peak line ≥ 10 % (the transient half of ~20 %). **Idle** = the lowest speed
from which every point up to the T4-limited maximum-throttle speed is acceptable.

**Scheduling corrections made during the search** (the first batches were wasted; recorded in D4A.1):
* the bleed and nozzle open at 95 % speed: the Phase 4 setting (90 %) acted below the first fixed-geometry failure
  (92.5 %, SM 9.2 %);
* the VIGV is a scheduled closure on corrected speed (design swirl at ≥ 95 %, closing linearly by Δ at 60 %; at SLS
  the corrected speed is 1.035 × the mechanical speed, so the closure starts at ~92 % mechanical): the Phase 4
  stall-index-driven schedule never closed the IGV, because here the binding limit is the surge-surrogate margin.

**Results at SLS** (maximum throttle 97.5-98.7 % in every configuration, T4-limited):

| configuration | idle | idle thrust | idle fuel | limit below idle |
|---|---|---|---|---|
| fixed geometry | 95 % | 573 N | 20.3 g/s | SM 9.2 % |
| 10 % bleed | 87.5 % | 396 N | 16.7 g/s | SM 9.4 % |
| nozzle ×1.6 | 92.5 % | 500 N | 18.2 g/s | SM 8.4 % |
| VIGV 15-30° + 10 % bleed | 85 % | 338-348 N | 14.9-15.3 g/s | SM, stator 1 |
| VIGV 15-30° + 10 % bleed + nozzle ×1.6 (at 40 %) | 80 % | 222-231 N | 11.8-12.2 g/s | SM 7.7-8.9 % |
| **VIGV 15° + 10 % bleed + nozzle ×2.0, fully open at 80 %** | **77.5 %** | **114 N** | **10.0 g/s** | **stator-1 stall at 75 %** |
| 15-20 % bleed (any) | none below 97.5 % | | | T4 1159-1207 K at 95 % |

* Relaxing the margin to SM ≥ 5 % does not help: the best idle is still 77.5 %, with stator-1 stall binding. The VIGV
  unloads rotor 1 and loads stator 1, as Phase 4 found.
* Nozzle ×2.5 gives 77.5 % / 91 N.
* More bleed fails the other way: the turbine has to make up the lost work at lower flow, and T4 goes over the limit
  near full speed.
* Below 70 % speed at SLS the model finds no converged steady point at all with this geometry.

**Adopted:** VIGV 15° closure (stage-1 swirl 22.4° → 28.7° at idle); 10 % overboard bleed after stage 3, open ≤ 95 %
speed (bleed port at 38 % of the compressor pressure rise, 50 % of its work); variable nozzle opening to 2.0 × A8 by
80 % speed.

**Final lines** (`axial/plots/phase4a_operability.png`, `axial/data/phase4ax/operability_<tag>_final.csv`):
* **SLS idle 77.5 %:** SM 11.9 %, T4 878 K, 114 N, 10.0 g/s, i.e. **41 % of the 100 % SLS fuel flow** (the centrifugal
  idles at ~19 %, fielded engines at 14-18 %).
* SLS maximum: 659 N at 98.7 % speed, T4-limited, SM 10.5 %.
* **Dash line** (VIGV scheduled, bleed closed, nozzle at design): acceptable from 100 % down to 87.5 % speed (184 N);
  rotor 1 stalls below. The dash hold needs ~245 N (throttle 49 %), which is at 90 % speed with SM 12 % and no bleed.
  **The engine cannot be throttled below ~184 N at M 1.02 without opening the bleed**, which was not analysed at dash.

![operability](../axial/plots/phase4a_operability.png)

**Against Phase 4.** Phase 4 estimated that a pure axial with combined variable geometry would idle "at or above about
55-65 %". The 55 % end came from the NPSS AXI5 bracketing map, and 65 % from 30 % bleed on the stacking map with T4
over the limit. On the stacking map with all acceptance criteria applied, the combined geometry gives 77.5 %.

## 7. Idle thrust makes a powered idle approach impossible (F4A.3)

* Approach drag (Phase 2 airframe model, 14-16 kg, M 0.12-0.20): **15-21 N** (L/D 7.5-9).
* Idle thrust: 114 N static (≈ 100 N net in flight after ram drag), **5-6 × the approach drag**; 231 N with the nozzle at
  1.16.
* So the aircraft would accelerate, not descend, at idle. A conventional descent and approach are not possible. The
  options are to **shut the engine down at the top of descent** (glide from 5 km at L/D 7-9, dead-stick landing with
  flaps and the 0.6 m chute) or to add a thrust spoiler, reverser or large airbrake (not assessed).

This is a direct consequence of section 6: an engine idling at 77.5 % speed still moves most of its design airflow.

## 8. Rotor dynamics (`ax_rotor.py`, verified ROSS model; D4A.2)

* The mass-sized Phase 3 rotor passes at only 2 of 6 support settings. Its bending mode (57-61 krpm, 71-77 % speed) now
  lies just below idle. Not robust.
* **Stiffened rotor, adopted:** layout A, 2 mm Ti drum, 24 / 12 mm AISI 4340 shaft, **12 mm journals** (DN 1.01e6 at
  MCS; Phase 4's 16 mm journals were at 1.34e6), damped supports k 1.75e6 N/m, c 876 N s/m. It passes at all 24 support
  settings of the sweep.
  * Criticals 2.8 / 12.4 (AF 2.0) / 19.6 (1.3) / 39.9 (1.2) krpm: all below idle (62.0 krpm) and critically damped;
    122.3 krpm, **46 % above MCS**.
  * Rotor 1.60 kg (mass-sized 1.10 kg), Ip 8.0e-4 kg m².
* The assessment used idle 80 %. The final idle (77.5 %, 62.0 krpm) does not change it: the highest critical below the
  range is 39.9 krpm, 36 % below idle.

## 9. Acceleration (`ax_transient.py`, `axial/data/phase4ax/accel_<tag>.csv`)

Same quasi-steady method as the centrifugal (`cc_transient.py`). At each speed the bleed and the nozzle take their
scheduled values, and the VIGV its scheduled angle. T4 is raised above its steady value with speed and T4 imposed
(pyCycle `NT4` mode, shaft power left unbalanced). The usable excess power is the largest one that keeps T4 ≤ 1150 K,
no row beyond its Howell stalling deflection, and a margin to the stacking peak line of ≥ 5 % (as for the centrifugal)
or ≥ 10 %. Then dN/dt = P_excess / (I_p ω) is integrated from idle to 98.5 % speed (SLS maximum throttle is 98.7 %,
where the excess is zero). I_p = 8.07e-4 kg m² (the chosen rotor, section 8).

**Consistency check.** The two runs use different pyCycle modes: section 6 imposes speed and balances the shaft (N),
and this one imposes speed and T4 (NT4). Imposing the section 6 steady T4 at each speed gives a net shaft power of
0.0 kW (to three decimals) at every speed from 77.5 to 97.5 %, and the same bleed / nozzle / VIGV states. A first run
that stepped T4 down from 1150 K gave the same excess powers at 80-98.5 % (e.g. 29.28 kW at 90 %, 0.76 kW at 98.5 %),
but found no converged point at 77.5 % (tools_survey section 9). The table is from the second run.

| speed | steady T4 | usable excess power, SM ≥ 5 % (limit) | SM ≥ 10 % (limit) |
|---|---|---|---|
| 98.5 % | 1146 K | 0.8 kW (T4) | 0.8 kW (T4) |
| 97.5 % | 1126 K | 4.5 kW (T4) | 4.5 kW (T4) |
| 95 % (bleed opens) | 1125 K | 5.9 kW (T4) | 5.9 kW (T4) |
| 92.5 % | 1038 K | 21.0 kW (T4) | 21.0 kW (T4) |
| 90 % | 988 K | 29.3 kW (T4) | 24.9 kW (surge margin) |
| 85 % | 906 K | 34.6 kW (surge margin) | 21.9 kW (surge margin) |
| 80 % | 877 K | 23.8 kW (surge margin) | 12.7 kW (surge margin) |
| **77.5 % (idle)** | 878 K | 15.8 kW (surge margin) | **2.2 kW** (surge margin) |

| result | SM ≥ 5 % reserve | SM ≥ 10 % reserve |
|---|---|---|
| **idle 77.5 % → 98.5 %** | **1.7 s** | **2.2 s** |
| of which 77.5 → 95 % | 0.6 s | 1.2 s |

**What sets it.** The rotor is light (Ip 8.1e-4 kg m², 38 % of the centrifugal's 2.13e-3), and the speed span is short:
spinning up from 77.5 to 98.5 % takes only ½ I_p (ω₂² − ω₁²) = 10.5 kJ. Two regions take most of the time:
* **the top 3 % of speed**, where the steady T4 is already within 4-25 K of the limit, so the temperature leaves
  almost no excess power. 95 → 98.5 % takes 1.1 s of the total, whatever the margin reserve;
* **the idle point with a 10 % reserve**, where the steady margin is 11.9 %, so only 2.2 kW can be used before the
  surrogate margin falls to 10 %. The same situation made the centrifugal unable to accelerate from 40 % with a 10 %
  reserve. Here the engine still accelerates, slowly, for its first 2.5 % of speed.

For comparison, the centrifugal takes 6.6 s from 40 to 95 % with a 5 % reserve, and the B300F data sheet gives 37 →
100 % in 4.6 s. The axial is quick only because it idles at 77.5 %: it never has to cross the low-speed range.

**Not included** (the same limits as the centrifugal estimate):
* the variable geometry is assumed to follow its speed schedule instantly; actuator rates are unknown (section 10);
* the bleed closing at 95 % is a step in the schedule. Its transient (a sudden rise in the flow through the rear
  stages) is not modelled;
* fuel-control dynamics, heat soak and combustor lag;
* the surge line is the unvalidated peak-line surrogate (R4.1), so both reserves are measured against an unvalidated
  line;
* the start (below idle) is not covered at all.

## 10. Engine update and Phase 2 ↔ 4 closure (`ax_mission.py`, `ax_closure.py`; D4A.3)

**Engine deck:** the stacking map with the VIGV schedule and the fielded TurboFlow turbine map in pyCycle, maximum
throttle = min(100 % speed, T4 1150 K). SLS maximum 659 N at 98.7 % (SM 10.5 %); dash 500 N at 100 % (SM 13.9 %).

**Engine mass:** 5.02 → **6.86 kg** calibrated (6.50-7.22), L 599 mm, OD 142.5 mm (combustor-set; liner 157 mm,
reference velocity 29.8 m/s). Raw mass changes:
* shaft 24 / 12 mm: 0.95 kg raw (the largest single item);
* drum 2 mm: 0.26 kg;
* discs +0.009 kg;
* **variable geometry 0.64 kg raw**: VIGV 0.165 (vanes, spindles, levers, unison ring + servo), bleed 0.122 (manifold,
  band valve + servo), nozzle 0.354 (flaps, sync ring, hinges + heat-shielded servo). **These are geometric estimates
  plus 3 × 75 g hobby-class servos, not sourced from a fielded design.** Whether a 75 g servo can hold a nozzle
  actuator next to a 937 K jet, or move the VIGV unison ring against its aerodynamic and friction loads, is not known.

Largest raw items (kg): shaft 0.95, fasteners / seals / balancing 0.52, outer casing 0.46, compressor casing 0.46,
combustor liners 0.42, shaft tunnel and bearing housings 0.37, variable nozzle 0.28 + 0.075.

**Closure (S 0.30 m², Phase 2 airframe, sortie on the engine's deck; `axial/data/phase4ax/closure_<tag>.json`):**

| mass item (powered idle descent, as the centrifugal was flown) | kg |
|---|---|
| engine (calibrated) | 6.86 |
| engine accessories (A3.7) | 1.60 |
| structure | 3.43 |
| landing gear + chute | 1.28 |
| fuel system | 0.40 |
| systems, avionics, instrumentation | 2.03 |
| growth 15 % | 1.07 |
| fuel (sortie 4.15 + reserve 1.15, + 3 % unusable) | **5.46** |
| **TOGW** | **22.12** |
| **margin to 25 kg** | **2.88** |

With the engine shut down at the top of descent (below): fuel **1.88 kg, TOGW 18.54 kg, margin 6.46 kg**.

| performance check | nominal wave drag | pessimistic wave drag |
|---|---|---|
| dash thrust margin at M 1.02 / 5 km (target 25 %) | **+103 %** | **+88 %** |
| time to M 1.02 at 5 km | 29.1 s | 29.2 s |
| 3 g sustained turn at M 0.9 / 5 km, excess thrust | +292 N | +292 N |

* Take-off ground roll 54 m (V_LOF 51.0 m/s); landing 177 m with flaps and the chute (300 m assumed, A1.7).
* **About 4.5 kg of the 5.46 kg fuel is idle-related**: the 235 s descent from 5 km, the 60 s pattern and the 120 s
  reserve, all at 41 % of the maximum fuel flow. That powered descent is also physically inconsistent with section 7
  (the aircraft would not descend at idle). It is shown because it is how the centrifugal was flown.
* **Engine-off descent variant:** engine shut down at the top of descent, glide and dead-stick landing with the chute;
  the 120 s reserve at idle fuel flow is kept. Fuel 1.88 kg, TOGW 18.54 kg, margin 6.46 kg; dash margins unchanged.
  **Not a like-for-like comparison** with the centrifugal (20.09 kg, flown with a powered descent at its ~19 % idle).
* Worst corner: +71 % in Phase 3A-R (η_c 0.66, combustor +1σ, pessimistic drag). Not re-run on the Phase 4A engine; the
  diameter and cycle did not change, the mass rose 1.84 kg.

## 11. Assumptions added in Phase 4A

| ID | assumption | basis |
|---|---|---|
| A3A.1 | fielded axial η_c = tool × 0.70 / 0.8175 = 0.709 | same technology debit as the centrifugal; no axial field data |
| (D4A.1) | fielded loss split: Howell part follows incidence, fielded debit constant per row | the whole-loss scaling produced an unphysical choke (F4A.2) |
| (D4A.1) | operability criteria as Phase 4 (SM ≥ 10 % to the peak line, no Howell stall, T4 ≤ 1150 K) | Phase 4; the surge surrogate is unvalidated |
| (D4A.3) | variable-geometry masses: geometric estimates + 3 × 75 g servos | no fielded micro-turbojet VG hardware found |
| (F4A.1) | blade root Kt 1.4, 10 % thickness taper | Phase 4 impeller practice; taper not optimised |
| (D4A.3) | engine-off variant keeps the 120 s idle reserve | brief reserve rule kept unchanged |

## 12. Open risks

They are listed, with their status, in `axial/docs/design_freeze_axial.md` section 4. In short: R4.1 (the model itself),
idle at 77.5 % and the descent concept it forces, unsourced variable-geometry hardware, the start, blade roots at 96 %
of Fty, blade resonances, the turbine on its stress limit, damper design, mass calibration, and no hardware.

## 13. Scripts

| script | venv | purpose |
|---|---|---|
| `scripts/phase3_cycle/ax_trade.py grid / run [rpm] / compile` | .venv (+ np1) | Phase 3A-R trade (`P3_DATA=phase3ax`, `P3_OPR=5`) |
| `scripts/phase4_turbomachinery/ax_rotor_stress.py <tag>` | .venv | blade roots, discs, blade modes (with the FE verification) |
| `scripts/phase4_turbomachinery/ax_operability.py <tag> search / one / final` | .venv | variable-geometry search and final lines |
| `scripts/phase4_turbomachinery/ax_operability_summary.py <tag>` | .venv | idle per configuration (`AXOP_SM_MIN`) |
| `scripts/phase4_turbomachinery/ax_rotor.py <tag>` | .venv | rotor-dynamics sweep (ROSS) |
| `scripts/phase4_turbomachinery/ax_transient.py <tag>` | .venv | acceleration |
| `scripts/phase4_turbomachinery/ax_mission.py <tag>` | .venv | engine deck and idle (`AXM_REUSE_DECK=1`) |
| `scripts/phase4_turbomachinery/ax_closure.py <tag>` | .venv | engine update and closure, incl. the engine-off variant |
| `scripts/phase4_turbomachinery/ax_plots.py <tag>` | .venv | the two Phase 4A plots |
