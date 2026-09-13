# Phase 4: low-speed operability and stall of the pure-axial engine (2026-09-14)

**Engine:** the corrected Phase 3 baseline (`docs/phase3_engine.md` section 14):
* 6-stage axial compressor, OPR 5, 80 000 rpm, hub/tip 0.40, Cx 185 m/s, fixed inlet guide vane;
* single-stage turbine;
* fixed convergent nozzle sized at the dash point (M 1.02 / 5 km, 500 N, T4 1150 K), fielded
  efficiencies.

Scripts are in `scripts/phase4_turbomachinery/`, data in `data/phase4*`, and the plot is
`plots/phase4_operability.png`.

## Result in brief

**The fixed-geometry pure axial has a real low-speed operability problem.** The Phase 3 caveat
("a fixed-geometry 5-stage compressor at PR 5 is prone to front-stage stall at part speed") is
confirmed. It is quantified here with a stage-stacking model and bracketed with an independent
published map shape.

| question | stage-stacking map (own model) | NPSS AXI5 5-stage PR 5.2 map (bracket) |
|---|---|---|
| surge margin at the design point (dash) | **14 %** at constant speed (18 % at constant flow) | 20 % (the map's own design point) |
| surge margin at SLS 100 % speed | 12 % | 15 % |
| first rotor beyond Howell's stalling deflection on the SLS line | below about 87 % speed | not available (no stage data) |
| lowest speed with a steady match at SLS (running line meets the surge surrogate) | **about 83 %** | **about 52-55 %** |
| steady T4 at the lowest matched speed | 1030 K (85 %); above 1150 K below about 73 % if the surge line is ignored | 915 K (55 %) |
| conventional micro-turbojet idle (about 30-35 % speed) | **not possible** | **not possible** |

Remedies tested on the stacking map, one at a time (SLS):

| remedy | lowest steady speed | penalty |
|---|---|---|
| none (fixed geometry) | 85 % | - |
| variable IGV, scheduled 21 deg to 49 deg of swirl | about 80 % (rotor 1 unstalled, stator 1 then stalls) | actuator and linkage |
| nozzle area x 1.3 / x 1.6 / x 2.0 | about 80 % | at 100 % SLS thrust falls 690 -> 467 / 361 / 281 N if left open, so it needs a variable nozzle |
| 20 % bleed after stage 3, open at or below 90 % | about 70 % | T4 1145 K at 90 % |
| 30 % bleed after stage 3 | about 65 % | T4 up to 1250 K at 85-90 % (over the 1150 K limit); rotor 4 stalls |

No single remedy gets below about 65 % speed on the stacking map. The bracketing map suggests a
real compressor of this class would do better, but even that map ends the steady running line
around 52-55 %.

**Consequences:**
* The engine cannot idle at conventional micro-turbojet speeds.
* A start must be carried by the starter, or by a scheduled bleed / variable-IGV system, up to
  (stacking) or near (bracket) the self-sustaining speed.
* **The fixed-geometry axial with a single valve or nozzle is not a workable engine on either
  map.** It would need a combined variable-geometry and bleed system that is not in the Phase 3
  mass, complexity or cost estimate.

This is a decision point for the user (see "What this means for the architecture").

## 1. Method

### 1.1 Compressor off-design: `axial_offdesign.py` (own model)

**Why an own model.** No approved tool gives axial-compressor maps: NASA turbo-design has no usable
axial loss model, TurboDesigner is design-only, and TurboFlow has no axial compressor. So the
Phase 3 design model (TurboDesigner triangles plus Howell cascade losses, Saravanamuttoo et al.,
*Gas Turbine Theory*, ch. 5) is extended to off-design by mean-line stage stacking, row by row.

**Geometry.** Frozen at the design. Constant mean radius; effective annulus areas calibrated so
the design axial velocity (185 m/s) is reproduced at every station at the design point.

**Flow angles.** Row exit flow angles are fixed (constant deviation). The stage-1 inlet swirl is
set by the IGV, which is implied by the 50 %-reaction design (alpha1 = 21.4 deg).

**Loss.** Relative total-pressure loss coefficient per row, calibrated at the design point to each
stage's Phase 3 efficiency, which includes tip clearance and the stage-1 shock loss.
* Off design: Y = Y* [1 + ((eps - eps_d) / (eps_s - eps*))^2].
* The Phase 3 Reynolds correction applies, and the stage-1 shock part is recomputed from the tip
  relative Mach number.
* The negative-incidence width is uncertain, so a sensitivity with it doubled was run
  (`neg_width 2`). The stall conclusions do not change (map table in the appendix).

**Stall criterion (Howell, as given in *Gas Turbine Theory* ch. 5).** Stalling deflection is where
the cascade loss is twice its minimum, and the nominal deflection is eps* = 0.8 eps_s, with
tan(in*) - tan(out*) = 1.55 / (1 + 1.5 s/c).
* Here eps* = 26.25 deg, the design deflection is 26.45 deg, and eps_s = 32.8 deg.
* A row with deflection at or above eps_s is counted as stalled (stall index >= 1).
* The Lieblein diffusion factor is reported as a cross-check.

**Choke.** No subsonic continuity solution at a station.

**Surge surrogate.** The peak of each pressure-ratio characteristic (zero slope). A multistage
compressor can run with its front stage stalled at low speed without surging, so the first-row
Howell line and the peak line are both kept.

**Verification.**
* Design point reproduced: PR 5.031 vs 5.000 (+0.6 %) and eta 0.831 vs 0.828.
* Effective/geometric area ratio 0.85-0.98, consistent with the 2-4 % blockage plus TurboDesigner's
  area convention.
* This check is what exposed the Phase 3 blockage input error: the ratio was 0.52 with the old
  input.

**No validation.** There is no micro-axial test data to validate the off-design losses or the stall
criterion. Hence the AXI5 bracket below.

### 1.2 Turbine map: `turbine_map.py` (TurboFlow performance analysis)

**Setup.** The Phase 3 TurboFlow turbine geometry with its own off-design performance solver
(Benner losses, Aungier deviation, critical-Mach choking), swept at 30-110 % speed and PR_ts from
1.15 to 1.35 x design.

**Verification.** The design point is reproduced exactly: 1.077 kg/s and eta_tt 0.9306, the same as
the design optimisation. 21-23 of 23 points converge per speed line.

**Two TurboFlow 0.1.18 defects found and worked around:**
1. With `stop_on_failure=False`, the summary printer crashes on a failed point (np.mean over None).
2. Every point after a failed one fails, because the failed solution is reused as the initial guess
   and gives "'list' object has no attribute 'keys'".

The workarounds are to disable the summary and to sweep outward from the design PR in two calls.

**Scaling.** The fielded turbine (eta_t 0.75, PR 3.03) is represented by pyCycle's scaling of the
map, with PR scaled linearly by (PR-1).

### 1.3 Engine match: pyCycle, `operability.py`

**Model.** The Phase 3 cycle model (TABULAR thermo, duct loss, burner dP/P 0.05, nozzle Cv 0.98),
now with the two maps above instead of the placeholder NPSS maps.

**Operating modes.** Design point at the dash; off-design in "N" mode (fuel balances shaft power at
the imposed speed, nozzle area fixed at the design value).

**Model additions** (all default off, so the Phase 3 results are unchanged):
* a variable nozzle-area scale `a8s.A8_scale`;
* an overboard compressor bleed port `sb`;
* the transient mode `NT4`.

**Reading the result.** Each converged operating point is located back on the stacking model to
get the stall index per row and the surge margins:
* SMN = (PR_s/Wc_s)/(PR/Wc) - 1 at constant corrected speed;
* SMW = dR/R at constant flow.

**Criterion.** About 20 % surge margin for an HP compressor and 15 % for an LP compressor, of which
"typically up to half" covers transient excursions (Rolls-Royce patent CN112081683A, which gives the
same dR/R definition). A single-spool PR 5 compressor is taken against the 20 % figure.

**Non-convergence.** Where pyCycle cannot converge with the R-line held at or above the peak line
(R-line 1), no steady match exists left of the surge surrogate, and the point is reported as "no
steady match".

## 2. Results

### 2.1 Fixed geometry (`data/phase4_running_line_ax0_opr5_t1150_cap_blk_nw1.csv`)

| speed | SLS thrust | SLS T4 | SLS PR | SLS stall index (row) | SLS SMN / SMW | dash thrust | dash T4 | dash stall index | dash SMN |
|---|---|---|---|---|---|---|---|---|---|
| 100 % | 690 N | 1163 K | 5.44 | 0.87 (S6) | 12 % / 11 % | 500 N | 1150 K | 0.81 | 14 % |
| 95 % | 570 | 1088 | 4.89 | 0.84 (R1) | 11 / 15 | 374 | 1049 | 0.88 | 14 |
| 90 % | 457 | 1042 | 4.33 | 0.93 (R1) | 8 / 11 | 249 | 950 | 0.96 | 13 |
| 87.5 % | 403 | 1030 | 4.03 | 0.99 (R1) | 5 / 8 | 191 | 902 | 1.01 | 14 |
| 85 % | 350 | 1028 | 3.73 | **1.06 (R1)** | **2.5 / 3** | 135 | 855 | 1.05 | 13 |
| <= 82.5 % | no steady match (the running line would lie left of the peak line) | | | | | 90 ... -33 | 817 ... 686 | 1.10 ... 1.30 | 13-15 |

**Readings:**
* **Dash / high altitude-Mach:** the nozzle stays choked (NPR above 1.8 down to about 85 %), so the
  running line is fixed in corrected terms and SMN stays at 13-15 %. The front rotor still passes
  its Howell stalling deflection below about 87 % corrected speed.
* **SLS:** the dash-sized nozzle is unchoked (NPR 1.65 at 100 %). The running line rises toward
  surge as speed falls and meets the peak line at about 83 %.
* **At 100 % mechanical speed at SLS**, T4 is 1163 K, so the ECU speed limit would sit at about
  99 % for T4 1150 K. That gives about 680 N of take-off thrust, enough for the 500 N-class
  requirement. Corrected speed at SLS is 1.035, because the dash inlet at 309 K is warmer than
  SLS.

### 2.2 Remedies (SLS; `data/phase4_nozzle_sweep_*.csv`, `phase4_bleed_sweep_*.csv`, `phase4/vigv_*.json`)

Summarised in the table at the top. **Variable IGV:** the schedule is found iteratively as the
smallest swirl that keeps every row below 0.95 x its stalling deflection on the running line. It
closes to 49 deg at 85 % corrected speed.

Why the results come out as they do:
* **The IGV** unloads rotor 1 but moves the stall to stator 1 and does not move the peak line
  enough.
* **A larger nozzle** lowers the running line at high speed: SMN at 100 % rises to 19-23 %. But the
  low-speed end of the line is set by the narrow speed lines of the stacking map.
* **Interstage bleed** is the most effective single measure. It unloads the rear, so the front
  stages take more flow. But 30 % bleed pushes T4 over the limit at 85-90 %.

### 2.3 Bracket with the NPSS AXI5 map (`running_line_axi5.py`)

pyCycle ships NPSS's AXI5 map of a 5-stage, PR 5.2 axial compressor. Its geometry and any
variable-stator schedule are not documented. With the same engine, turbine map and nozzle, the SLS
running line stays stall-free down to 55 %:
* SMN is 20-27 % between 70 and 95 % speed;
* T4 is 845-1072 K;
* the line reaches the AXI5 stall line at about 52 %.

In normalised terms, AXI5's surge line sits above the stacking model's peak line at mid speed. At
0.6 x design flow AXI5 reaches PR 3.6, against 2.8 for the stacking model. So the stacking model is
the pessimistic end of the bracket. The truth for a new micro-scale design is unknown until a
validated map exists.

### 2.4 Acceleration margin

Not computed as a time. A quasi-steady transient script is drafted (`accel.py`: pyCycle mode
`NT4`, excess power over the rotor inertia Ip = 1.12e-3 kg m² from the rotordynamics study) but was
**not run or verified**. There is no idle to accelerate from. And on the SLS running line the steady margin at 85-95 % is already below
the roughly 10 % transient allowance (half of 20 %), so a surge-free fuel schedule could add almost
no over-fuelling there. The fixed-geometry engine therefore has **no usable acceleration margin
below about 95 % speed at SLS**, and marginal margin at the dash (13-15 % steady).

## 3. What this means for the architecture

**What the pure axial would need.** The Phase 3 recommendation of the pure axial listed operability
as the open risk that "changes the mass and complexity case" if variable geometry or bleed were
needed. It is needed:
* at minimum a scheduled start/handling bleed plus a variable IGV;
* probably also a variable nozzle for take-off / low-speed matching.

Even then, the model does not give a conventional idle. The whole micro-turbojet class (every
engine in the Phase 3 database) avoids this by using a single centrifugal stage.

**Options for the user's decision.** I have not switched the architecture. That is the user's call.

| option | for | against / to do |
|---|---|---|
| **A. Keep the pure axial, add VIGV + start bleed + variable nozzle** | best dash margin (+104 / +89 %), smallest diameter (142 mm) | idle still at or above about 55-65 % speed; 3 actuated systems (mass, ECU, reliability) not costed; start needs a high-power starter or a start-bleed schedule; the axial efficiency is still unvalidated at micro scale (open risk R4.1) |
| **B. Axial-centrifugal, 1-2 axial stages + centrifugal, 90 000 rpm** (corrected in the Phase 3 erratum) | 6.1 kg, 564-610 mm, +75 / +50 % margin; the classic small-engine arrangement for PR 4-6, with 1-2 lightly loaded front stages ahead of a wide-range centrifugal | impeller at 409-471 m/s: exducer blade-root bending must be checked with the Phase 4 gate method; operability must be checked with the same tools (a centrifugal map from TurboFlow is available); 170 mm diameter |
| **C. Pure centrifugal** | micro-turbojet standard, benign operability | fails the impeller blade-root check as designed (537 m/s, 30 deg backsweep); would need a less-backswept or tip-loaded exducer redesign |

**My recommendation:** run the same two checks on option B before committing further Phase 4 work
to the pure axial. Those are the impeller blade root at 409-471 m/s, and an operability sweep with
the TurboFlow centrifugal map plus the 1-2 axial stages on the stacking model. Both checks are
cheap with the tools now built. Option A stays the fallback if B fails.

## 4. Open risks and caveats

* **R4.1 (as instructed):** axial-stage efficiency and the off-design loss and stall model come from
  textbook correlations checked only at conventional scale. Revisit them with published micro-axial
  compressor test data if a source becomes available. The AXI5 bracket shows the answer here is
  sensitive to the map shape.
* **Mean-line only.** Tip-region stall of the transonic first rotor is not resolved, and the
  parabolic loss continuation beyond stall is crude. The low-speed peak line is therefore
  indicative.
* **Bleed map vs mechanical-speed scheduling.** The bleed-open map is scheduled on corrected speed
  and the pyCycle valve on mechanical speed (at SLS they differ by 3.5 %). The bleed port frac_P
  0.376 / frac_work 0.50 is taken from the design point.
* **Turbine map scaling.** The turbine map is the tool-level design scaled by pyCycle to the
  fielded efficiency and PR. CoolProp air is used, not combustion products (as in Phase 3).
* **Intake.** Recovery at SLS is 1.0, and the duct loss is fixed at its dash value.
* **Rotordynamics interaction** (`docs/phase4_rotordynamics.md`): that study assumed idle at 35 %.
  With idle at or above 55-65 %, the damped rotor bending mode at about 36 krpm (45 %) is crossed
  only during start and shut-down, not dwelt near. This helps option A.

## Appendix: loss-width sensitivity of the stacking map

Doubling the negative-incidence loss width (`neg_width 2`; `data/phase4/comp_lines_*_nw2.json`)
changes the choke side at low speed:

| corrected speed | choke flow / design, nw 1 -> nw 2 |
|---|---|
| 0.5 | 0.33 -> 0.38 |
| 0.7 | 0.53 -> 0.58 |

It does not change the conclusions:
* at and above 0.85 corrected speed the peak line and the Howell line are identical to within 1 %;
* at and below 0.8 the first rotor is at Howell stall already at choke in both cases;
* the design-point surge margin is 14.1 % vs 14.2 %.
