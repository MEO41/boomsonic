# Phase 3R: the engine redesigned around a centrifugal compressor (2026-09-14)

**Why this phase exists.** After trying axial, axial-centrifugal and centrifugal options, the user decided
(2026-09-14) to design the engine around a **centrifugal compressor**, as the architecture that suits this scale. Phase 3
was re-opened on that basis and redone to the brief's Phase 3 scope:
* an on-design cycle at the reference thrust point;
* a quantitative trade of 2-3 options (here: pressure ratio, spool speed and impeller backsweep of the centrifugal
  engine, the brief's "OPR sweep" type of option), each with SFC, airflow, mass and size;
* off-design points across the Phase 1 mission;
* one recommendation tied to the numbers.

Phase 4 (turbomachinery preliminary design) has not been started. Every Phase 3R output is in `data/phase3r/`,
`data/phase3r_*.csv|json` and `plots/phase3r_*.png`; the superseded Phase 3 files are untouched, for traceability.

## Result in brief

> **Note (Phase 4, `docs/phase4r_centrifugal.md`).** The surge margins below (28 % design, 22-27 % on the SLS line)
> use the peak-PR surrogate, which Phase 4 found badly optimistic on NASA HECC, the one vaned-diffuser stage with a
> measured surge line (real margin 8.4 %). NASA turbo-design gives the -15° impeller 6.5 %. The surge margin is
> therefore an open risk, not a demonstrated pass. The design point (PR 4, η) was confirmed by turbo-design within
> 1 % / 1.5 points.

**Recommended engine (D3R.1): single spool; single-stage centrifugal compressor at OPR 4.0; 75 000 rpm; Ti-6Al-4V
impeller with 12 + 12 splitter blades and 15 deg exit backsweep; radial vaned diffuser with axial deswirl; annular
combustor; single-stage axial turbine; convergent nozzle. T4 1150 K, Fn 500 N at M 1.02 / 5 km.**

| | fielded level (realistic) | tool level |
|---|---|---|
| airflow / dash TSFC | 1.326 kg/s / 0.164 kg/(N h) | 1.068 kg/s / 0.138 |
| impeller tip speed | 525 m/s | 486 m/s |
| engine OD (set by) | **187 mm** (compressor diffuser; combustor 170, turbine 127) | 173 mm |
| length / dry mass (calibrated) | **478 mm / 6.74 kg** (6.38-7.09) | 6.21 kg |
| dash thrust margin, nominal / pessimistic drag | **+55 % / +29 %** (target 25 %) | +71 % / +46 % |
| worst corner (η_c 0.66, combustor +1 σ, pessimistic drag) | +22 % | - |
| surge margin: design point / SLS running line 55-100 % | **28 % / 22-27 %** (criterion ~20 %) | |
| lowest steady speed / idle (fuel) | 35 % / 40 % speed, 37 N, 19 % of max fuel flow | |
| impeller stress at MCS (105 %) | blade root = Fty by sizing (2.2 mm root); disc +86 % yield margin; burst ratio 1.90 | |
| TOGW with the sortie fuel from the real-map deck | **20.0 kg** (3.05 kg fuel), 5.0 kg under 25 kg | |

* **It passes every constraint the Phase 3 centrifugal failed or never checked:** correct slip model, inducer Mach
  inside the fielded range, stress-sized impeller, turbine inside its stress limit, surge margin quantified on real maps.
* **It is 12 mm larger in diameter than the Phase 3 centrifugal claimed (175 mm), and its margin is 15 points lower
  (+29 % vs +44 %).** The Phase 3 numbers were not achievable, for the four reasons in section 1.
* The margin rests on a diffuser-sized diameter that is probably conservative. Calibrating the compressor OD to the AMT
  Nike, the one validation engine whose diameter is compressor-set, gives 177 mm and +42 %.

**Physics in one paragraph.** A centrifugal stage's pressure rise comes from its tip speed U2. The shaft speed is capped
by the inducer relative Mach number: with this much air, faster than ~77 000 rpm puts the eye beyond any fielded
micro-turbojet. So the impeller must be large (134 mm), and its vaned diffuser, not the combustor, sets the engine
diameter. Backsweep trades against that. Every degree of backsweep lowers the work per unit U2², so it costs tip speed
and diameter (about 0.65 mm and 0.9 points of thrust margin per degree). It also makes the pressure characteristic fall
as flow increases, and that negative slope is what keeps the stage stable (about 2 points of surge margin per degree).
A radial-bladed impeller would give the smallest engine with zero surge margin; -15 deg sits in the middle of the
window where both criteria hold (section 6).

## 1. Four problems found in the Phase 3 centrifugal chain before redesigning

### 1.1 TurboFlow's Wiesner slip model has a unit error (tool defect, F3R.1)

`turboflow/centrifugal_compressor/slip_model.py`:

```python
return u_out*np.sqrt(np.cos(theta_out))/(z**0.7)
```

`theta_out` is the blade exit angle **in degrees** (the rest of the model uses `math.tand(theta_out)`, and the upstream
example gives -24.5). `np.cos` takes radians. The Wiesner slip factor is σ = 1 - √(cos β2b) / Z^0.7.

Evidence (`scripts/phase3_cycle/verify_turboflow_slip.py`, `data/phase3r_turboflow_slip_check.json`): the slip factor
TurboFlow actually solves for, recovered from its exit velocity triangle, on the Phase 3 impeller (Z 12, 504 m/s):

| backsweep | σ solved, stock | σ, Wiesner correct | σ, as coded | PR, stock | PR, fixed |
|---|---|---|---|---|---|
| -30 deg (Phase 3 design) | 0.9310 | 0.8366 | 0.9310 | **4.012** | **3.394** |
| -24.5 deg (upstream example) | 0.8423 | 0.8325 | 0.8423 | 3.686 | 3.623 |
| -20 deg | 0.8878 | 0.8298 | 0.8878 | 4.163 | 3.792 |
| -10 deg | no solution (cos < 0 -> NaN) | 0.8257 | NaN | - | 4.141 |

* The error depends erratically on the angle, because cos(30 rad) and cos(24.5 rad) are unrelated numbers. At the
  upstream example's -24.5 deg it happens to be small (6 % on the slip term), which is why the Phase 0 smoke test
  looked fine.
* **Effect:** at -30 deg TurboFlow under-predicted slip, so it credited the impeller with 18 % more pressure ratio at
  a given tip speed. The Phase 3 impeller (U2 504 m/s for PR 4.01) actually gives PR 3.39. Every centrifugal result
  before this phase (the Phase 3 centrifugal, the Phase 3b and Phase 4 axial-centrifugal impellers, the impeller stress
  gate, the P400 / Nike validation and the P400 benchmark) used the defective slip.
* **Fix:** `scripts/phase3_cycle/turboflow_fixes.py` replaces the function at run time with the degree-correct form. It
  is imported by `centrifugal_design.py` and `centrifugal_map.py`. With the fix the solved σ equals Wiesner exactly
  (table).

### 1.2 The Phase 3 inducer ran beyond every fielded engine (F3R.2)

The Oh loss set has no shock loss, so TurboFlow's efficiency at high inducer relative Mach is not trustworthy, and
Phase 3 set no limit on it. Moreover, the fielded engine carries 22 % more air than the tool-level design at the same
speed. The same optimum-inducer rule used in the design script (`inducer_anchor.py`, `data/phase3r_inducer_anchor.csv`)
gives the inducer shroud relative Mach number:

| engine | rpm | airflow | M1s,rel |
|---|---|---|---|
| database, 9 engines with rpm and airflow | 61 500-117 000 | 0.45-1.80 kg/s | **1.10-1.33** (highest: PBS TJ40-G1 1.328; P400 1.24; P1000 1.27) |
| this engine, fielded airflow, 75 000 rpm | 75 000 | 1.33 kg/s | 1.29 |
| this engine, 77 500 rpm | | | 1.33 |
| this engine, 85 000 rpm (the Phase 3 speed) | | | **1.43** |

**Limit adopted (A3R.1): M1s,rel <= 1.33 at the fielded airflow, the top of the fielded range.** It caps the spool
speed at about 77 500 rpm. The design speed is **75 000 rpm** (1.29, inside the band); 77 500 rpm is carried as a
sensitivity.

### 1.3 The fielded geometry scaling was wrong for the impeller and unsafe for the turbine (F3R.3)

Phase 3 made the fielded engine by scaling every radius of the tool-level design by √(W_fielded / W_tool) at fixed
speed (A3.6).
* **Impeller.** Its exit radius is set by the work, U2 = ωr2, not by the flow. The same pressure ratio at η 0.70
  instead of ~0.81 needs U2 × √(0.81 / 0.70), i.e. +8 %, whereas √W scaling gave +11 %. Phase 3R scales the impeller exit,
  vaneless and vaned diffuser radii and the axial lengths by the tip-speed ratio. The exit and diffuser widths follow
  continuity at the same exit flow coefficient, and the eye follows √W. This is the same geometry the stress check
  uses. **Effect: -6 to -8 mm of engine diameter wherever the diffuser sets it.**
* **Turbine.** The tool-level turbine tip sits exactly on its 350 MPa blade-root stress limit. Scaling it by √W (×1.11)
  raised the root stress, which goes as ω²(r_t² - r_h²), by ×1.24, to about 435 MPa. The Phase 3 centrifugal turbine had
  the same problem (tip 53.9 → 59.6 mm at 85 000 rpm). Phase 3R **re-designs the turbine with TurboFlow at the fielded
  cycle** (same speed, same stress limit and envelope cap). **Effect: the turbine meets its limit; engine mass falls
  about 0.7 kg** (the stress-sized disc mass rises steeply with rim radius).

### 1.4 The Phase 3 impeller had no stress constraint (known from the Phase 4 gate)

The gate found the -30 deg exducer blade root fails at 537 m/s. In Phase 3R the stress is **inside the design loop**
(section 3).

## 2. Re-anchored calibrations (with the slip fix)

**Mass model** (`validate_mass_model.py`, `P3_DATA=phase3r`, Phase 3R blade conventions, `data/phase3_mass_model_validation_3r.csv`):

| engine | predicted / published mass | predicted / published length | predicted / published OD |
|---|---|---|---|
| JetCat P400-PRO-LN | 3.52 / 4.01 kg (-12 %) | 322 / 390 mm | 145 / 148 mm (combustor-set) |
| AMT Nike | 7.23 / 9.15 kg (-21 %) | 434 / 524 mm | **212 / 201 mm (compressor-set, +5.7 %)** |

* Calibration: **mass ×1.20 (range 1.14-1.27)**, length ×1.21. Phase 3 used ×1.24 / ×1.22.
* New with the slip fix: the Nike's diffuser-set diameter is over-predicted by 5.7 %. The compressor envelope rule
  (vaned diffuser R4/R2 1.35 + axial deswirl, 3 mm casing) is therefore **conservative** on the one engine where the
  compressor sets the diameter. It is kept uncalibrated; the effect is shown as a sensitivity (section 5).

**Operability chain benchmark** (`cc_benchmark.py`, P400 maps regenerated with the fix, `data/phase4_benchmark_P400_3r.csv`):
* the chain runs the P400 steady down to **37.5 % speed** (28 N, EGT 667 C) and loses the match at about 35 %, against
  the published idle of 31 %. It is about 5 points of speed pessimistic (3-4 points before the fix);
* design-point surge margin 61 % (the characteristic peaks about 30 % below design flow), and 61-88 % along the SLS
  line.

The chain is still validated for centrifugal engines, now with a correct impeller model.

## 3. Design method (Phase 3R conventions)

Unchanged from Phase 3: pyCycle dash cycle (Fn 500 N at M 1.02 / 5 km, T4 1150 K, intake losses inside the cycle,
burner dP/P 0.05, η_b 0.95, convergent nozzle); TurboFlow centrifugal stage (Oh losses, algebraic vaneless model,
'custom' vaned diffuser, R4/R2 1.35, 0.25 mm clearance, inducer hub/tip 0.35 with the minimum-W1s shroud radius, exit
flow coefficient 0.28); TurboFlow single-stage axial turbine on the same shaft (350 MPa blade-root limit, tip capped at
the engine envelope); theta-scaled combustor (±1 σ); bottom-up mass model; Phase 2 airframe drag; tool and fielded
(η_c 0.70, η_t 0.75) technology levels.

Changed in Phase 3R:

| item | Phase 3 | Phase 3R |
|---|---|---|
| slip | TurboFlow stock (defective) | patched, Wiesner correct |
| blades | Z 12 in TurboFlow; 12 + 12 splitters in the stress and mass models | 12 + 12 splitters (half length) everywhere; TurboFlow sees Aungier's Z_eff = 18 |
| exit width | 5 % blockage assumed inside the TurboFlow width | TurboFlow gets the effective width; the physical width adds the blockage of the stress-sized blades |
| inducer throat | opened until the design point is "just unchoked" | opened until 110 % of design flow is unchoked (10 % choke margin) |
| spool speed | 85 000 rpm, inducer M_rel unconstrained | limited by the fielded inducer M_rel (A3R.1): 75 000 rpm |
| impeller stress | solid-disc screening formula, checked afterwards | **sized inside the loop** (below) |
| fielded compressor geometry | √W scaling | work-based (1.3) |
| fielded turbine | √W-scaled (over its stress limit) | re-designed at the fielded cycle |
| mass / length calibration | ×1.24 / ×1.22 | ×1.20 / ×1.21, applied before the drag and TOGW |

**Impeller stress in the loop** (`impeller_stress.py`; the verified solvers of the Phase 4 gate). Criteria use the gate's
Ti-6Al-4V minimum basis at about 250 C (Fty 620, Ftu 681 MPa). Stresses are taken at the maximum continuous speed MCS
= 105 % (the definition used in the Phase 4 rotordynamics, from API 617 practice):
* **exducer blade root:** Morley-plate FE with Kt 1.4. The root thickness is **sized**: the smallest t_root >= 1.6 mm
  (the Phase 3 aero thickness, 1.2 mm mean with a 0.8 mm tip) whose peak root stress at MCS is <= Fty;
* **exit blockage** B2 = Z_exit t_mean / (2π r2 cos β2b), which sets the physical exit width. The trailing-edge dump
  loss of that blockage is estimated separately (Borda-Carnot on the meridional velocity) because TurboFlow sees no
  blade thickness;
* **disc:** boreless hub with the best back-face boss (A/r2 0.1-0.3), axisymmetric FE with the thermal gradient
  (eye to exit, linear and quadratic), peak von Mises at MCS <= Fty;
* **burst:** Robinson criterion with k 0.85, N_burst / N_MCS >= 1.20 (14 CFR 33.27);
* **inducer blade root** in tension <= Fty.

Regression: the module reproduces the gate's 656 MPa for the Phase 3 exducer (3.5 mm root, 537 m/s, -30 deg).

## 4. Screening: pressure ratio × spool speed × backsweep (`cc_screen.py`, `data/phase3r_cc_screen.csv`)

36 TurboFlow designs: OPR 3.5 / 4.0 / 4.5 × 75 / 85 / 95 krpm × backsweep 0 / -10 / -20 / -30 deg, each stress-sized at
the fielded level.

* **Every design can be made stress-feasible once its root is sized.** The price is root thickness and blockage, and it
  grows steeply with backsweep and speed. At OPR 4, 75k: root 1.6 / 1.7 / 2.7 / 3.3 mm and blockage 7 / 7 / 10 / 13 %
  at 0 / -10 / -20 / -30 deg. At 95k, -30 deg: 5.3 mm and 23 %.
* **TurboFlow credits backsweep with little efficiency:** η_tt 0.809 → 0.819 from 0 to -30 deg at OPR 4, 75k. The
  pressure ratio at a given tip speed falls with backsweep (lower work coefficient ψ = σ - φ2 tan β2b), so U2 rises:
  fielded 498 → 561 m/s.
* **Speed:** efficiency falls with rpm (0.81 at 75k, 0.79 at 85k, 0.76 at 95k at OPR 4), because the inducer relative
  Mach rises. The diffuser shrinks with rpm.
* The trailing-edge blockage dump loss is 0.03-0.14 efficiency points: negligible.

## 5. Full-chain trade (`cc_trade.py`, `data/phase3r_cc_trade.csv`, `plots/phase3r_cc_trade.png`)

Fielded level. Calibrated mass ×1.20 and length ×1.21. TOGW here uses the Phase 2 sortie fuel scaled by the dash fuel
flow, as in Phase 3; section 8 replaces it with the real-map sortie fuel for the recommended engine. SMN is the
design-point surge margin, for the cases that have maps.

| OPR, speed, backsweep | U2 | root / exit blockage | OD (set by) | length | dry mass | drag nom / pess | margin nom / pess | worst corner | TOGW | SMN |
|---|---|---|---|---|---|---|---|---|---|---|
| 3.5, 75k, 0° | 469 m/s | 1.6 mm / 8 % | 189 (combustor) | 499 | 6.55 kg | 330 / 399 N | +52 / +25 % | +7 % | 18.8 | |
| 3.5, 75k, -20° | 504 | 3.1 / 12 % | 189 (combustor) | 505 | 6.89 | 330 / 399 | +52 / +25 | +7 | 19.1 | |
| 3.75, 75k, 0° | 485 | 1.6 / 7 % | 179 (combustor) | 486 | 6.48 | 305 / 361 | +64 / +38 | +20 | 18.6 | |
| 4.0, 75k, 0° | 498 | 1.6 / 7 % | 177 (diffuser) | 474 | 6.44 | 301 / 355 | +66 / +41 | +32 | 18.5 | **0 %** |
| 4.0, 75k, -10° | 516 | 1.7 / 7 % | 183 (diffuser) | 477 | 6.62 | 315 / 377 | +59 / +33 | +26 | 18.7 | 19 % |
| **4.0, 75k, -15°** | **525** | **2.2 / 9 %** | **187 (diffuser)** | **478** | **6.74** | **323 / 389** | **+55 / +29** | **+22** | **18.9** | **28 %** |
| 4.0, 75k, -20° | 535 | 2.7 / 10 % | 190 (diffuser) | 480 | 6.87 | 332 / 402 | +51 / +24 | +18 | 19.0 | 39 % |
| 4.0, 75k, -30° | 560 | 3.3 / 13 % | 199 (diffuser) | 485 | 7.17 | 355 / 439 | +41 / +14 | +7 | 19.4 | |
| 4.25, 75k, 0° | 511 | 1.6 / 7 % | 182 (diffuser) | 465 | 6.50 | 311 / 371 | +61 / +35 | +28 | 18.6 | |
| 4.5, 75k, 0° | 524 | 1.6 / 7 % | 186 (diffuser) | 456 | 6.51 | 321 / 387 | +56 / +29 | not converged | 18.6 | |
| 4.5, 75k, -20° | 563 | 2.4 / 9 % | 200 (diffuser) | 463 | 6.97 | 358 / 443 | +40 / +13 | not converged | 19.2 | |
| 4.0, 77.5k, 0° (at the inducer limit) | 499 | 1.6 / 8 % | 172 (diffuser) | 467 | 6.14 | 290 / 338 | +72 / +48 | +32 | 18.1 | |
| 4.0, 85k, -20° (reference; violates A3R.1) | 538 | 3.4 / 14 % | 170 (combustor) | 477 | 6.36 | 286 / 332 | +75 / +51 | +32 | 18.3 | |

Reading the table:
* **Pressure ratio.** At 75k the optimum is OPR 4.0, where the combustor (shrinking with OPR) and the diffuser (growing
  with the tip speed OPR needs) are about equal: 3.75 is combustor-limited (179 mm), 4.25 diffuser-limited (182 mm).
* **Backsweep** costs about 6-7 mm of diameter and 8-9 points of pessimistic margin per 10 deg at OPR 4.
* **Speed.** 77.5k would buy 5 mm and 7 points, at the very top of the fielded inducer range. 85k looks best on paper
  but breaks the inducer limit, and its fielded turbine cannot pass the flow within the 350 MPa blade limit (TurboFlow
  returns a design 2.3 % short of the worst-corner flow with the tip 1.4 % over its limit).
* **Stress:** every case is feasible once the root is sized. The disc (boreless) has 67-102 % yield margin and burst
  ratios of 1.8-2.1 at MCS.
* **The trailing-edge blockage** dump loss is ≤ 0.14 efficiency points in every case.
* **The pyCycle design did not converge at η_c 0.66 for OPR 4.5.** An energy balance shows that cycle closes (turbine
  PR about 3.3, positive thrust), so it is a solver failure, not an infeasible cycle.

**Sensitivities of the recommended engine** (`cc_sensitivity.py`, `data/phase3r_sensitivity_ce75000_opr4_t1150_b15_cap.csv`):

| case | OD | margin nom / pess | TOGW (trade fuel) |
|---|---|---|---|
| baseline (η_c 0.70) | 187 mm | +55 / +29 % | 18.9 kg |
| compressor OD calibrated to the Nike (×0.946) | 177 mm | +67 / +42 % | 18.8 kg |
| η_c 0.66 (impeller re-sized: U2 541 m/s, root 2.4 mm, stress ok) | 192 mm | +48 / +22 % | 19.2 kg |
| η_c 0.74 (U2 511 m/s) | 182 mm | +61 / +35 % | 18.6 kg |

## 6. Backsweep and stability: why -15 deg (`plots/phase3r_backsweep.png`)

TurboFlow off-design maps of the 0 / -10 / -15 / -20 deg impellers (OPR 4, 75k; 233-237 of 252 points converged each),
TurboFlow turbine maps, and pyCycle running lines. Method as in Phase 4 and benchmarked on the P400. Surge surrogate:
the peak of each speed line.

| backsweep | 100 % line peak at W/W_design | design SMN | SLS running line SMN, 55-100 % | lowest steady SLS speed | pessimistic thrust margin | OD |
|---|---|---|---|---|---|---|
| 0° (radial) | 1.00 | **0 %** | 0-1 % (rides the peak) | about 70 % (only a few points converge) | +41 % | 177 mm |
| -10° | 0.85 | 19 % | 12-17 % | 45 % | +33 % | 183 mm |
| **-15°** | **0.80** | **28 %** | **22-27 %** | **35 %** | **+29 %** | **187 mm** |
| -20° | 0.75 | 39 % | 31-36 % | 35 % | +24 % | 190 mm |

**Mechanism.** Euler work is ψU2² with ψ = σ - φ2 tan β2b.
* **Radial blades** (β2b = 0): the work does not depend on the flow coefficient φ2. The pressure characteristic is set
  by the losses alone, flat and peaked at the minimum-loss point, which is the design point. The stage has no negative
  slope to stabilise it: SMN is 0.
* **Backswept blades:** the work falls as flow rises, which tilts the characteristic down to the right. The peak moves
  to lower flow, and the design point gains a stable margin, about 2 points per degree here.
* **The price** is the lower ψ. The same pressure ratio needs more U2, so the impeller, its diffuser and the engine
  diameter grow, and the thrust margin falls by about 0.9 points per degree.

**Criteria:**
* surge margin >= ~20 % on the high-power running line (the Phase 4 criterion, Rolls-Royce CN112081683A: about 20 %
  for an HP compressor, up to half consumed in transients);
* dash thrust margin >= 25 % with pessimistic drag.

The first needs >= about 10.5 deg of backsweep and the second <= about 19 deg. **-15 deg sits in the middle of that
window.** It keeps about 8 points of surge margin above the criterion for transients, and 4 points of thrust margin
above the target. -10 deg meets neither the design-point criterion (19 %) nor the SLS line (12-17 %).

## 7. The recommended engine (`data/phase3r/cct_ce75000_opr4_t1150_b15_cap.json`)

**Cycle at the dash, fielded:**
* W 1.326 kg/s; Wf 0.0228 kg/s; TSFC 0.164 kg/(N h);
* T3 520 K, P3 408 kPa; T4 1150 K; turbine exit 972 K (699 C); NPR 2.76; A8 70.8 cm²;
* intake loss inside the cycle (normal shock + duct, as D3.1).

**Cantera cross-check** (`data/phase3r_cantera_check.txt`): T_ad 1146.0 K vs pyCycle T4 1150.0 K (-0.35 %); γ 1.3136
vs 1.3134; cp +0.6 %; overall φ 0.244. The real-gas properties hold, as in Phase 3.

**Compressor:**

| item | tool design | fielded |
|---|---|---|
| TurboFlow η_tt / PR | 0.817 / 4.01 | (η_c 0.70 assumed) / 4.0 |
| tip speed U2 / at MCS | 486 m/s | 525 / 552 m/s |
| impeller exit radius / diameter | 61.9 / 124 mm | 66.9 / 134 mm |
| eye tip / hub radius | 44.6 / 15.6 mm | 49.7 / 17.4 mm |
| inducer shroud relative Mach | 1.19 | 1.29 (fielded range 1.10-1.33) |
| exit width, effective / physical | 9.5 mm / - | 10.7 / 11.8 mm (blade blockage 9 %) |
| blades | 12 + 12 splitters, β2b -15°, Z_eff 18 | exducer root 2.2 mm (tapering to 0.8 mm) |
| inducer throat | area ratio 0.75, unchoked at 110 % design flow | |
| diffuser | vaned, R4/R2 1.35, 19 vanes, axial deswirl; exit Mach 0.21 | OD 187 mm incl. 3 mm casing |

**Impeller stress at MCS (105 %), fielded, Ti-6Al-4V minimum basis:**
* exducer blade root 618 MPa = Fty by sizing (Kt 1.4);
* inducer root 196 MPa;
* boreless disc 313 MPa mechanical, 335 MPa with the thermal gradient: yield margin +86 %;
* burst ratio N_burst / N_MCS 1.90 (>= 1.20 required);
* FE impeller mass 1.13 kg (with the back-face boss; the calibrated engine-mass model uses its own impeller estimate
  for consistency with the calibration).

At the worst corner (η_c 0.66, U2 541 m/s) the root re-sizes to 2.4 mm and every check still passes.

**Turbine** (TurboFlow, re-designed at the fielded cycle): single stage, 34 NGV / 28 rotor blades, blade heights 23 /
24 mm. The tip radius is 61.1 mm, exactly the 350 MPa blade-root limit at 75 000 rpm, so the turbine is stress-limited,
not envelope-limited. Turbine OD 127 mm; TurboFlow η_tt 0.936 (tool) / 0.933 at the fielded flow (0.75 assumed).

**Combustor:** theta-scaled, OD 170 mm (182.6 mm at +1 σ), liner 188 mm long, reference velocity 23.6 m/s.

**Engine:**
* OD 187 mm, set by the compressor diffuser (the combustor +1 σ at 183 mm is still inside it);
* length 478 mm calibrated;
* dry mass 5.60 kg bottom-up → **6.74 kg calibrated** (range 6.38-7.09). The largest items: impeller 0.92, outer
  casing 0.85, combustor liners 0.60, shroud / inlet 0.44, diffuser 0.39, shaft 0.34, turbine disc 0.28 kg (raw).

**Airframe at the dash** (Phase 2 model): fuselage 217 mm; drag area 81.9 / 98.6 cm²; drag 323 / 389 N; throttle 0.65 /
0.78.

## 8. Off-design across the mission, with the real maps (`cc_mission.py`, `plots/phase3r_mission.png`)

This replaces the Phase 3 placeholder-map deck (A3.8).
* Compressor: TurboFlow map of the -15° stage.
* Turbine: TurboFlow map of the designed turbine.
* pyCycle scales both maps to the fielded dash design point.
* Max throttle = 100 % speed, or less where T4 would exceed 1150 K (found by a secant search on speed). pyCycle's own
  T4 mode does not converge with these maps.

**Sea-level static running line:**

| speed | thrust | T4 | EGT | fuel flow | SMN |
|---|---|---|---|---|---|
| 100 % | 681 N | 1182 K (over the limit) | 731 C | 91.8 kg/h | 22 % |
| **98.2 % (max, T4-limited)** | **631 N** | 1150 K | | 85.6 kg/h | 24 % |
| 90 % | 445 N | 1039 K | 618 C | 64.1 kg/h | 22 % |
| 70 % | 186 N | 877 K | 511 C | 35.0 kg/h | 25 % |
| 55 % | 87 N | 824 K | 493 C | 23.0 kg/h | 22 % |
| **40 % (idle for fuel: minimum-fuel steady point)** | **37 N** | 902 K | 599 C | **17.5 kg/h (19 % of max)** | 8 % |
| **35 % (lowest steady within T4 1150 K)** | 33 N | 1036 K | 741 C | 19.5 kg/h | 9 % |

Against fielded engines of this class: idle speed 26-39 % of max rpm and idle fuel 14-18 % of max (JetCat P220 / P300 /
P400 data). The model sits at the pessimistic edge of both, consistent with the benchmark's ~5-point pessimism at the
bottom. The Phase 2 idle-fuel assumption A1.4 (10 %) was optimistic against the data.

**Dash running line (M 1.02 / 5 km):** SMN 28 % at 100 %, 28-60 % from 95 % to 75 %. Thrust 500 / 376 / 269 N at
100 / 95 / 90 %.

**Max-thrust deck** (`data/phase3r_mission_ce75000_opr4_t1150_b15_cap_deck.csv`, 70 points, all converged): T4-limited
at low Mach at every altitude, speed-limited near M 0.8-1.0 at low altitude. Thrust is 631 N SLS, 424 N at M 0.7 /
5 km and 500 N at M 1.02 / 5 km. SMN at max throttle is 22-29 % wherever the operating point lies inside the map. At low
Mach above 2.5 km the corrected speed exceeds the map's highest line (105 %), so no SMN is computed there.

**Sortie** (Phase 2 integrator re-flown on this deck; S 0.30 m²; calibrated engine OD and length; intake loss inside
the cycle; idle fuel = the 40 % point; TOGW iterated on the sortie's own fuel):

| | nominal wave drag | pessimistic |
|---|---|---|
| TOGW | 20.03 kg | 20.03 kg |
| ground roll / V_LOF | 46 m / 48.5 m/s | same |
| brake release to M 1.02 at 5 km | 27.6 s | 27.9 s |
| minimum excess thrust, transonic acceleration at 5 km / during the hold | 183 / 177 N | **115 / 111 N** |
| dash throttle (drag / max thrust) | 0.65 | 0.78 (margin +29 %) |
| 3 g sustained turn at M 0.9 / 5 km, excess thrust | +283 N | +283 N |
| fuel: used + reserve (120 s idle) | 2.47 + 0.58 = **3.05 kg** | 2.50 + 0.58 = 3.08 kg |
| landing mass | 17.6 kg | 17.5 kg |

* Fuel is dominated by the idle descent from 5 km (1.14 kg in 235 s) and the pattern plus reserve (1.16 kg). The
  descent uses the SLS idle fuel flow, which is conservative: corrected fuel flow scales with ambient pressure.
* The accelerating part of the sortie takes 0.8 kg.
* The Phase 3 trade's 1.90 kg (Phase 2 fuel scaled by dash fuel flow) under-estimated the sortie by 1.15 kg. The
  25 kg limit still holds with 5.0 kg to spare.
* The climb segment is inherited unchanged from Phase 2. With thrust/weight above 1 its energy-height climb is not
  limited by the flight-path angle, so the 11 s climb is optimistic. It uses 0.25 kg of fuel, so the effect on fuel is
  small.

## 9. What changed against the Phase 3 centrifugal, and why

| | Phase 3 centrifugal (OPR 4, 85k, -30°) | Phase 3R (OPR 4, 75k, -15°) | cause |
|---|---|---|---|
| PR delivered at the design tip speed | claimed 4.0 at 504 m/s (actually 3.39) | 4.0 at 486 m/s (tool) | slip defect (1.1), less backsweep |
| inducer relative Mach, fielded | 1.43 (beyond every fielded engine) | 1.29 | speed limit A3R.1 |
| impeller exducer root at MCS | fails (gate) | = Fty by sizing, 2.2 mm root | stress in the loop |
| fielded turbine tip vs 350 MPa limit | 11 % over | on the limit | turbine re-designed at the fielded cycle |
| surge margin | never computed | 28 % design, 22-27 % SLS line | real maps |
| engine OD | 175 mm | 187 mm | lower speed → larger impeller and diffuser |
| dry mass (calibrated) | 6.57 kg | 6.74 kg | |
| margin nom / pess | +69 / +44 % | +55 / +29 % | |
| TOGW | 18.6 kg (scaled fuel) | 20.0 kg (sortie fuel from the real-map deck) | |

## 10. Assumptions added in Phase 3R

| id | assumption | basis / status |
|---|---|---|
| A3R.1 | inducer shroud relative Mach <= 1.33 at the fielded airflow | top of the 9-engine fielded range (1.10-1.33); TurboFlow has no shock loss |
| A3R.2 | impeller stresses at MCS 105 %: disc and blade root (Kt 1.4) <= Fty min; burst >= 1.20 × N_MCS; root >= 1.6 mm | gate criteria plus the Phase 4 MCS definition; zero margin beyond MCS at the blade root by design |
| A3R.3 | surge margin >= ~20 % on the high-power running line, peak-PR surrogate | Phase 4 criterion; the chain is ~5 points of speed pessimistic at idle (benchmark) |
| A3R.4 | splitters as Aungier's effective blade number in TurboFlow | Aungier (2000) slip with splitters |
| A3R.5 | 10 % impeller-throat choke margin | Phase 4 finding; PR and η unaffected |
| A3R.6 | fielded compressor geometry work-based; fielded turbine re-designed | replaces A3.6 |
| A3R.7 | idle for fuel accounting = minimum-fuel steady SLS point; descent at SLS idle fuel flow | fielded idle fuel 14-18 %; model 19 % |
| A3R.8 | compressor-set OD not calibrated (the Nike check suggests -5.7 %) | shown as a sensitivity |

## 11. Open items for Phase 4 (not started)

1. **The diffuser sets the diameter**, and TurboFlow's vaned-diffuser loss is insensitive to R4/R2. A proper diffuser
   design (vane count, radius ratio, radial-to-axial turn and deswirl) is the largest single lever on drag: the
   Nike-calibrated diameter is worth +13 points of margin.
2. **Impeller 3D:** the exducer root sits at Fty at MCS by construction. Still to do: 3D FE with rake/lean, blade
   vibration (Campbell), and low-cycle fatigue for start-stop cycles.
3. **Rotor dynamics** of this rotor (75 000 rpm, overhung impeller and turbine); the Phase 4 work was on the axial rotor.
4. **Transients:** start and acceleration. The chain is ~5 points pessimistic at idle; the SLS SMN of 8-9 % at 35-45 % is
   the region to check.
5. **Turbine:** it sits on its conceptual 350 MPa blade limit, so IN-713LC life data are needed (A3.2).
6. **Compressor map above 105 % corrected speed** (cold, high-altitude, low-Mach corner of the deck).

## 12. Scripts (all in `scripts/phase3_cycle/` unless noted)

| script | job |
|---|---|
| `turboflow_fixes.py`, `verify_turboflow_slip.py` | slip fix and its evidence |
| `centrifugal_design.py` | TurboFlow stage design; Phase 3R options: `Z_split`, `split_frac`, `effective_width`, `choke_margin` |
| `impeller_stress.py` | stress-sized impeller, wrapping the Phase 4 gate solvers |
| `inducer_anchor.py` | fielded inducer relative Mach range |
| `cc_screen.py` | 36-design screen |
| `cc_trade.py` | full-chain trade: `run OPR:rpm:beta`, `reeval`, `compile` |
| `cc_sensitivity.py` | diameter and efficiency sensitivities |
| `cc_mission.py` | running lines, deck, sortie; add `lines` for running lines only |
| `plot_phase3r.py` | figures |
| `validate_mass_model.py` | mass calibration (`P3_DATA=phase3r`, `P3_CC_OPTS`, `P3_OUT_SUFFIX=_3r`) |
| `scripts/phase4_turbomachinery/cc_benchmark.py` | P400 benchmark (`P3_DATA=phase3r`, `MAP_DIR=data/phase3r/maps`) |
| `run_centrifugal_map.sh`, `run_turbine_map.sh` | maps (`CC_SRC`, `TT_SRC`, `MAP_DIR`, `CC_GROUPS`, `TMAP_NS`, `TMAP_PAR`) |
