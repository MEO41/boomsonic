# Phase 4: the two checks on option B, the axial-centrifugal (2026-09-14)

> **Note (Phase 3R, 2026-09-14).** The TurboFlow impeller designs and maps used here, including the P400 benchmark,
> were made with TurboFlow's defective Wiesner slip (`docs/phase3r_centrifugal.md` section 1.1). The P400 benchmark was
> re-run with the fix: the chain still reproduces the P400's idle capability to about 5 points of speed. The option-B
> verdict is moot: the user chose the pure centrifugal.

Option B is the corrected axial-centrifugal (AC) from the Phase 3 erratum: 1 or 2 axial stages plus one centrifugal
stage on one shaft at 90 000 rpm, OPR 4, T4 1150 K, fielded efficiencies. Both variants were checked:
* `ax90000_opr4_t1150_ax2_pa2_cap_blk`: 2 axial stages (PR 2.0) + impeller (PR 2.0);
* `ax90000_opr4_t1150_ax1_pa1.5_cap_blk`: 1 axial stage (PR 1.5) + impeller (PR 2.67).

Both checks use exactly the methods applied to options A and C:
1. the impeller stress gate: axisymmetric FE disc, burst criterion, Morley-plate exducer blade root;
2. the operability chain: stage stacking, TurboFlow maps, pyCycle running lines.

The operability chain was also **benchmarked on a real engine that is known to idle**.

## Result in brief

**Option B fails both checks as designed.**

| check | 2 axial + cc | 1 axial + cc | pure axial (A), for reference | pure centrifugal (C), for reference |
|---|---|---|---|---|
| impeller exducer root at a 3.5 mm root, 30 deg backsweep, Kt 1.4 (limit Fty 620 MPa) | **1105 MPa, fails** | **936 MPa, fails** | - | 656 MPa, fails |
| root thickness needed for 620 MPa (no margin) | 5.8 mm (49 % root blockage) | 4.9 mm (36 %) | - | 3.7 mm (23 %) |
| impeller disc (boreless) with the thermal gradient / burst ratio | 214 MPa (+190 %) / 2.37 | 276 MPa (+125 %) / 2.09 | - | 326 MPa (+90 %) / 1.92 |
| design-point surge margin (constant speed) | **11 %** | **11 %** | 14 % | not run |
| SLS: lowest speed with a steady match | **about 90 %** | **about 90 %** | about 85 % | not run |
| dash running line, 70-100 % | 10-21 % margin (with the impeller throat opened; see 2.3) | 7-15 % | 13-15 % | not run |

**Why the impeller fails.** The AC impellers are small (r2 44.5 / 51.5 mm) but have tall exit blades (b2/r2 0.43 /
0.30, against 0.19 for the pure centrifugal), because they are low-pressure-ratio stages sized at the same exit
flow coefficient. Exducer root bending scales with the blade height squared, so the lower tip speed (419 / 486 m/s,
against 537 m/s) does not help. About 10 deg of backsweep would pass (377 / 320 MPa at a 3.5 mm root). That is an
aerodynamic redesign, not evaluated here.

**Why the operability fails.** It is the axial front stage(s), not the impeller. On the 100 % line the axial pair's
PR peaks about 5 % below the design flow and collapses about 3 % above it, while the centrifugal PR is almost flat
(1.95-2.01). The combined characteristic therefore peaks close to the design point, and the SLS running line reaches
that peak at about 90 % speed. This does not change when the axial loss band is doubled or the impeller throat is
opened.

**The method is not the cause.** Applied unchanged to the Phase 3 model of the JetCat P400-PRO-LN (a real
centrifugal engine; published idle 30 000 rpm = 31 %, 14 N):
* the method finds a steady running line down to **35 % speed** (27 N, exhaust gas temperature 740 C, inside the
  published 480-750 C range);
* it finds **38-53 % surge margin** all the way down;
* the steady match is lost just below 34 %, against the published 31 %.

So the TurboFlow-map + pyCycle + peak-line chain reproduces a real engine's idle capability to within about
3-4 % of speed. What drives the narrow margins of options A and B is **the axial-stage off-design model, which is the
one element with no validation (open risk R4.1)**. The low-speed conclusion for anything with axial stages is
therefore model-dependent, and the AXI5 bracket for option A already suggested the stacking model is on the
pessimistic side.

## 1. Check 1: impeller stress (`impeller_check_ac.py`, `axial/data/phase4_optionB_impeller.json`)

The solvers, material and criteria are those of the gate (`docs/phase4_impeller_stress_gate.md`):
* verified axisymmetric FE;
* Ti-6Al-4V minimum basis at about 250 C: Fty 620, Ftu 681 MPa;
* burst ratio >= 1.2 (14 CFR 33.27);
* Kt 1.4;
* 12 + 12 splitter blades, mean thickness 1.2 mm, linear taper to 0.8 mm.

**Geometry.** The Phase 3 TurboFlow impeller of each variant, scaled to the fielded engine by s = 1.107 / 1.108
exactly as the trade scales it, at 90 000 rpm. The tip speed is 419 / 486 m/s. The trade's own fielded-work
estimate is 409 / 471 m/s, so the check is 2-3 % conservative on tip speed.

**Thermal case.** Eye 399 / 359 K (fielded) to exit 522 K.

| | 2 ax + cc | 1 ax + cc |
|---|---|---|
| r2 / b2 / b2/r2 | 44.5 / 19.3 mm / 0.434 | 51.5 / 15.5 mm / 0.300 |
| hub with 12 mm bore, best boss (A = 0.3 r2, p 2): von Mises / + thermal / burst ratio | 352 / 383-393 MPa / 2.02 | 451 / 491-506 MPa / 1.82 |
| boreless hub: von Mises / + thermal / burst ratio | 199 / 208-214 MPa / 2.37 | 258 / 269-276 MPa / 2.09 |
| exducer root 2.5 / 3.5 / 5.0 / 7.0 mm (Kt 1.4) | 1713 / 1105 / 711 / 477 MPa | 1447 / 936 / 603 / 405 MPa |
| root blockage at 3.5 / 5 mm (24 blades) | 30 / 43 % | 26 / 37 % |
| backsweep 10 / 20 / 30 deg at a 3.5 mm root | 377 / 748 / 1105 MPa | 320 / 634 / 936 MPa |
| inducer blade root, tension | 156 MPa | 187 MPa |

**Verdict.** The disc and burst pass with large margin, even with a bore. **The exducer blade root fails** at every
aerodynamically plausible thickness, worse than the pure centrifugal. A near-radial exducer (about 10 deg) passes.

## 2. Check 2: operability (`ac_offdesign.py`, `ac_operability.py`, `centrifugal_map.py`)

### 2.1 Method

**Combined compressor.** The axial stage(s) use the Phase 4 stage-stacking model on the Phase 3 TurboDesigner design
(Howell stall criterion, as for option A). The centrifugal stage uses the TurboFlow off-design map of the Phase 3
impeller and diffuser (same configuration as its design run), in corrected terms at the eye.
* The axial exit state is the eye state. Deswirl in the last stator and no transition-duct loss, as in Phase 3b.
* Surge surrogate: the peak of the overall PR characteristic, as for option A.

**Maps.**
* TurboFlow centrifugal maps: 10 speeds x 21 flows; 199 / 200 of 210 points converge.
* TurboFlow turbine map of each AC turbine.
* pyCycle, with the design point at the dash; running lines at SLS and at the dash.

**Verification.**
* The TurboFlow map reproduces both design runs exactly (PR 2.0045 / 2.675, eta 0.7837 / 0.7915).
* The combined model reproduces the design point: PR 4.036 vs 4.0, eta 0.803 vs 0.801.
* Both turbine maps reproduce their design points.

### 2.2 Results (`axial/data/phase4_running_line_ax90000_*.csv`)

| speed | 2 ax + cc, SLS: thrust / T4 / SMN | 1 ax + cc, SLS: thrust / T4 / SMN | 2 ax + cc, dash (throat 0.80): thrust / SMN |
|---|---|---|---|
| 100 % | 679 N / 1186 K / 10 % | 676 N / 1184 K / - (at map edge) | 500 N / 11 % |
| 95 % | 576 / 1127 / 6 % | 569 / 1123 / 6 % | 383 / 10 % |
| 90 % | 471 / 1078 / 1.7 % | 460 / 1074 / 0.2 % | 274 / 10 % |
| <= 87.5 % | no steady match | no steady match | 219 ... -32 / 11-21 % |

* **At 100 % SLS speed** T4 is about 1185 K, above the 1150 K limit, so the ECU limit sits at about 97-98 % speed for
  about 650 N.
* **The front axial rotor** stays below its Howell stalling deflection on the steady line (stall index 0.8-0.95).
  The limit is the combined characteristic peak, not first-row stall.

### 2.3 Sensitivities

| change | effect |
|---|---|
| axial negative-incidence loss width x2 | no change (SMN at design 11.2 %, SLS limit about 90 %) |
| impeller throat area ratio 0.65 -> 0.80 | Phase 3 opened the throat only until the design point was just unchoked, which left zero choke margin. TurboFlow's PR and efficiency are unchanged by the throat area (identical values at 1.0-1.2 x design flow); only the choke flag moves, from about 1.05 to about 1.25 x design flow. The dash line now stays inside the map (SMN 10-21 %). SLS is unchanged. |

### 2.4 Attribution (100 % speed, 2 ax + cc)

| W / W_design | overall PR | axial PR | centrifugal PR | rotor 1 / rotor 2 incidence |
|---|---|---|---|---|
| 0.90 | 4.184 | 2.120 | 1.974 | +5.9 / +6.4 deg |
| 0.95 | **4.239 (peak)** | 2.131 | 1.990 | +3.1 / +4.1 |
| 1.00 (design) | 4.036 | 2.013 | 2.005 | 0.0 / +0.2 |
| 1.03 | 3.269 | 1.666 | 1.962 | -2.0 / -4.4 |

The axial pair sets both the peak and the steep high-flow side. The centrifugal stage has a wide, flat
characteristic, as in the P400 benchmark, where the peak lies about 20 % below the design flow.

## 3. Method benchmark: JetCat P400-PRO-LN (`cc_benchmark.py`, `data/phase4_benchmark_P400.csv`)

**Reference data** (`data/microturbojet_database.csv`, jetcat.de): 425 N at 98 000 rpm; idle 30 000 rpm (31 %),
14 N; EGT 480-750 C; PR 3.8; 0.67 kg/s.

**Model.** The Phase 3 validation model: TurboFlow impeller and turbine designed to the published point, fielded
efficiencies, T4 1384 K solved for 425 N. Its impeller throat was sized with the same "just unchoked" rule. The
chain is identical to options A and B.

| speed (rpm) | thrust | T4 | EGT | SMN |
|---|---|---|---|---|
| 100 % (98 000) | 425 N | 1384 K | 962 C | at map edge |
| 80 % (78 400) | 191 | 1041 | 668 | 41 % |
| 60 % (58 800) | 86 | 910 | 580 | 50 % |
| 40 % (39 200) | 31 | 912 | 614 | 40 % |
| 35 % (34 300) | 27 | 1031 | 740 | 38 % |
| <= 32.5 % | no steady match (T4 rising steeply: not self-sustaining) | | | |

**Reading.**
* The method keeps this engine stall-free with large margin across its whole range. It loses the steady match at
  about 33-34 %, against the published idle of 31 %, and predicts about 27 N at 35 % against 14 N at 31 %.
* It is slightly pessimistic at the very bottom, which is consistent with a cold, low-Reynolds regime the
  loss models do not capture. It is **not** pessimistic by the 50-60 points of speed that separate options A and B
  from a normal idle.
* The predicted max-power EGT (962 C) is above the published 750 C limit. That is the known Phase 3 finding that the
  fielded-efficiency model needs T4 about 1380 K to reach the published thrust (A3.1 / section 2 of
  `docs/phase3_engine.md`). It does not affect the low-speed conclusion.

## 4. What this means

**Option B:**
* **Check 1:** it does not remove the impeller problem it was meant to remove. The disc stress is solved, but the
  exducer blade-root bending is worse than in the pure centrifugal.
* **Check 2:** its operability, in the same model, is no better than the pure axial.

**Architectures with axial stages.** Options A and B are limited by the same element: the fixed-geometry axial
stage(s), as represented by the stage-stacking model. That model is unvalidated (R4.1), and the benchmark shows the
rest of the chain is sound.

**Option C.** The pure centrifugal is the one architecture the benchmark supports for low-speed operability. It is
the micro-turbojet norm, and its only failed item so far is the exducer blade root. That would need an exducer
redesign, about 10-20 deg of backsweep or a tip-concentrated backsweep, with the aero, cycle and margin re-run.

**Suggested next step.** Redesign the pure centrifugal's exducer for stress, re-run its TurboFlow design, dash cycle
and thrust margin, and then run this same operability chain on it. Every tool needed is now in place.

## 5. Caveats

* **Axial stages.** Mean-line stacking with Howell stall and a peak-line surge surrogate, unvalidated at micro scale
  (R4.1). Options A and B stand or fall on it at low speed.
* **Transition and deswirl.** The axial-to-impeller transition duct and the last-stator deswirl are loss-free, as
  in Phase 3b.
* **Impeller geometry.** The TurboFlow pre-sizing uses a fixed exit flow coefficient (0.28), which makes the
  low-PR AC impellers wide. A dedicated AC impeller design, narrower with less backsweep, could change both checks
  for B.
* **1 ax + cc throat sensitivity.** Not run (the run was stopped); the 2 ax + cc result shows the throat only
  affects the choke side.
* **P400 benchmark.** It validates the chain on one engine only. That engine's own TurboFlow model was calibrated
  only to the published design point, not to part-load data.
