# Phase 4 (centrifugal baseline): turbomachinery preliminary design and Phase 2 ↔ 4 closure (2026-09-14)

**Scope.** The user approved the Phase 3R design ("go ahead with the -15° design"): single-stage centrifugal, OPR 4,
75 000 rpm, 15 deg backsweep (`ce75000_opr4_t1150_b15_cap`, `docs/phase3r_centrifugal.md`). This phase does the brief's
Phase 4:
* meanline compressor and turbine design with the appropriate tools;
* component efficiencies, stage counts, rough dimensions and mass;
* the mass fed back into the Phase 2 airframe budget, iterated until the 25 kg constraint closes.

Items the Phase 3R report left open are also covered: an independent compressor check, surge margin, blade vibration,
rotor dynamics and acceleration. Phase 5 (design freeze) has not been started.

## Result in brief

| item | result |
|---|---|
| stages | 1 centrifugal compressor stage (12 + 12 splitter blades, -15° backsweep, radial vaned diffuser + axial deswirl); 1 axial turbine stage (34 NGV / 28 rotor blades) |
| compressor efficiency (η_tt) | tool: TurboFlow 0.817, **NASA turbo-design 0.803** (independent check, PR 4.05 vs 4.01); fielded 0.70 |
| turbine efficiency (η_tt) | tool: TurboFlow 0.936 (0.933 at the fielded flow); fielded 0.75 |
| engine | **OD 187 mm** (compressor diffuser); **length 426 mm** (was 478: shorter combustor); **dry mass 6.85 kg** calibrated (6.49-7.21) |
| rotor | 2.11 kg, Ip 2.13e-3 kg m²; criticals 8.3 / 14.4 krpm (damped rigid-body modes, below idle) and 105.6 krpm (bending, 34 % above MCS): **API pass** with a 32 × 25.6 mm tube shaft, a 20 % shorter combustor and damped soft supports |
| acceleration, idle 40 % → 95 % (SLS, T4 <= 1150 K, surge margin >= 5 %) | 6.6 s (3.5 s from 45 %); B300F data sheet 37 → 100 % in 4.6 s |
| closure | **TOGW 20.1 kg, 4.9 kg under 25 kg**; dash margin +55 / +29 %; take-off roll 46 m; landing 175 m with flaps + chute (300 m assumed) |

**Two findings that change the confidence in the design** (sections 3 and 5):
1. **Surge margin is not established.** The peak-PR surge surrogate used in Phase 3R is badly optimistic on the one real
   vaned-diffuser stage with measured surge (NASA HECC):
   * measured surge margin at design: 8.4 %, still on the rising part of the characteristic;
   * turbo-design's characteristic peaks only below 61 % of design flow;
   * on our impeller the two tools disagree: design SMN 28 % (TurboFlow) against 6.5 % (turbo-design).

   For a vaned diffuser, surge is set by diffuser stall, which neither tool models. **This is now the top open risk.**
2. **The rotor's bending mode is set by the combustor length.** With the Phase 3 combustor rule, no shaft that fits
   the tunnel keeps the first bending critical out of the operating range. The fix used here is a 20 % shorter liner,
   made up by growing the combustor radially under the diffuser (no diameter cost, combustor loading kept), plus a
   thin-wall 32 mm tube shaft.

## 1. Compressor: independent check with NASA turbo-design (`td_check.py`, `plots/phase4r_td_check.png`)

turbo-design is the Phase 0 primary tool, validated on the NASA HECC stage (PR +2.0 %, η_poly -0.2 %). Its centrifugal
module was reviewed before use (subagent code review, recorded in `tools_survey.md` section 8):
* no degree/radian errors;
* Oh loss set with Aungier corrections (entrance diffusion, head-loss factor);
* splitters as Aungier's effective blade number;
* no shock loss and no diffuser-stall model;
* the vaned-diffuser loss is a Lieblein cascade correlation used beyond its fitted range, so it cannot size the diffuser.

The three OPR-4 / 75k impellers were rebuilt from their TurboFlow meanline geometry with no tuning:
* `build_flowpath`, 12 + 12 blades;
* the stress-sized exit blockage, so that the effective exit area matches TurboFlow's;
* zero incidence at the RMS radius;
* the design throat (area ratio 0.75, sized for a 10 % choke margin);
* vaneless space and a 19-vane diffuser to R4/R2 1.35.

| impeller | turbo-design PR / η_is | TurboFlow PR / η_is | turbo-design 100 % peak (W/W_d) / design SMN | TurboFlow peak / SMN |
|---|---|---|---|---|
| 0° | 3.96 / 0.786 | 4.00 / 0.810 | 1.10 / -9 % (design on the positive slope) | 1.00 / 0 % |
| **-15°** | **4.05 / 0.803** | **4.01 / 0.818** | **0.94 / 6.5 %** | **0.80 / 28 %** |
| -20° | 4.07 / 0.808 | 4.00 / 0.819 | 0.84 / 20 % | 0.75 / 39 % |

* **Design point confirmed.** The two tools agree on the pressure ratio within 1 % and on efficiency within 1.5 points.
  The -15° impeller makes PR 4 at 486 m/s (tool level).
* **Characteristic shape not confirmed.** Both tools move the peak to lower flow as backsweep grows. But turbo-design's
  100 % line is almost flat (PR within 1.3 % from 70 % to 108 % of design flow), so its peak, and the surge margin
  derived from it, are ill-defined.
* A first run with a throat estimated from blade angles (0.63 × the eye area) choked 2 % above design flow. The design
  throat is 25 % larger. This confirms that the 10 % choke margin needs the area Phase 3R chose.

## 2. Turbine
Unchanged from Phase 3R (TurboFlow design optimisation at the fielded cycle, 75 000 rpm):
* single stage, 34 NGV / 28 rotor blades, blade heights 23 / 24 mm;
* tip radius 61.1 mm, exactly on the 350 MPa blade-root limit;
* η_tt 0.933 (tool); OD 127 mm (inside the engine envelope).

Turbine life at the stress limit needs material data (A3.2, open).

## 3. Surge margin: the surrogate fails on a real vaned-diffuser stage (`hecc_surge_check.py`, `data/phase4r_hecc_surge_check.json`)

NASA's measured HECC 100 % speed line (vendored `map_vaned.csv`) runs from choke (5.24 kg/s) to the last stable point,
4.687 kg/s (95.1 % of design flow). There PR is still rising as flow falls (dPR/dW = -0.41 per kg/s).
* Measured design-point surge margin: **8.4 %**.
* turbo-design on the same stage, with the upstream fixture geometry: its characteristic keeps rising down to 3.0 kg/s
  (61 % of design flow). The peak-PR surrogate therefore implies >= 73 % margin, against the measured 8.4 %.
* HECC surged after only +0.8 deg of change in the vaned-diffuser inlet flow angle from design. turbo-design's absolute
  flow angle is about 4 deg off the vane angle there, so an absolute incidence limit cannot be transferred from this one
  stage.

**What this means.**
* For a vaned-diffuser stage, surge is triggered by diffuser (vane) stall before the stage characteristic peaks.
  Neither meanline tool models diffuser stall, so **the peak-PR surge margins in Phase 3R (28 % design, 22-27 % on the
  SLS line for -15°) are unvalidated and likely optimistic.**
* The P400 benchmark validated where the engine runs steadily (idle capability within ~5 points of speed). It did not
  validate where it surges, because the P400's surge line is not published.
* **What stands:** backsweep adds stability; both tools and the textbooks (Cumpsty, Dixon & Hall) agree on the
  direction. The magnitude of the -15° design's margin does not stand. Fielded micro-turbojets with vaned diffusers do
  run from idle to maximum in service, so an adequate margin is achievable. Whether this design has it depends on a
  diffuser designed for incidence range, which is not yet designed.

**Risk R4R.1 (top): the compressor surge margin is not established.** Mitigation options for the user (section 9).

## 4. Impeller: blade vibration screening (`cc_blade_modes.py`, `data/phase4r_blade_modes.json`)

The stress gate's Morley-plate model of the exducer blade was given a consistent mass matrix. Verification: a uniform
clamped strip is within -1.5 % of the analytic cantilever frequency. The frequencies below are static; centrifugal
stiffening raises them with speed, so the real crossings occur at somewhat higher speeds.

| mode | static frequency | crosses 19/rev (vaned diffuser) at | engine orders 1-6 |
|---|---|---|---|
| 1 (first bending) | 9.33 kHz | **39 % speed (at idle)** | no crossing in 35-105 % |
| 2 | 15.96 kHz | 67 % | none |
| 3 | 28.37 kHz | 119 % (above MCS) | none |

**Finding:** with 19 diffuser vanes, the exducer's first mode is excited at idle, and the second mode in the middle of
the running range. The vane count is a detailed-design choice that also moves diffuser incidence range and loss. The
static crossing speeds per vane count:

| diffuser vanes | mode 1 at | mode 2 at | mode 3 at |
|---|---|---|---|
| 15 | 50 % | 85 % | 151 % |
| 17 | 44 % | 75 % | 134 % |
| 19 (current) | 39 % | 67 % | 119 % |
| 21 | 36 % | 61 % | 108 % |
| 23 | 32 % | 56 % | 99 % |

Steady dwell points are idle (~40 %) and climb / dash (95-100 %). 15-17 vanes keep every static crossing away from both,
before stiffening. A proper Campbell with centrifugal stiffening, and a 3D blade model, remain open.

## 5. Rotor dynamics (`cc_rotor.py`, `cc_rotor_stiffening.py`, `cc_rotor_final.py`)

**Model** (ROSS 2.3.0, verified in `rotordynamics_verify.py`; eigen-solvers and API 684 criteria as in the Phase 4
axial work):
* the Phase 3R impeller as an axisymmetric FE body (1.25 kg incl. the 10 % allowance, Ip 1.59e-3 kg m²), overhung
  41 mm ahead of the front bearing;
* both bearings in the shaft tunnel: front 10 mm behind the impeller back face, rear under the NGV;
* the fielded turbine (0.43 kg), overhung 19 mm;
* bearing stiffness 6e5 / 1.75e6 / 1.9e7 N/m and damping 876 / 2000 N s/m, from the Phase 4 sources;
* operating range 35-105 % (26-79 krpm).

**Finding:** the first shaft-bending mode (4 % of its strain energy in the bearings, so dampers cannot reach it) sat at
38-57 krpm for 16-28 mm shafts, inside the range, with AF 5-20 on every support tried. Its frequency is set by the
**bearing span** (235 mm, of which 216 mm is the combustor):

| lever (damped soft supports, 12 mm journals) | first bending critical | API |
|---|---|---|
| Phase 3 combustor, shaft 16-28 mm, ID/OD 0.5 | 38-59 krpm | fail |
| Phase 3 combustor, 32 mm thin tube (ID/OD 0.8) | 74-76 krpm (< MCS 79k) | fail |
| lighter impeller boss (A/r2 0.1) | lower (the front bearing moves forward, the span grows) | fail |
| liner × 0.85, 32 mm thin tube, 15 mm journals | 99.7 krpm (1.27 MCS) | pass, by 1 % |
| **liner × 0.80, 32 × 25.6 mm tube** | **105.6 krpm (1.34 MCS)** | **pass** |
| liner × 0.75, 24-32 mm thin tube | 102-116 krpm | pass |
| liner × 0.70, 24 mm thin tube | 115-122 krpm | pass |

**Configuration chosen (D4R.1):** liner 0.8 × the Phase 3 rule (bearing span 192 mm), AISI 4340 tube 32 × 25.6 mm,
12 mm bearing journals (DN 0.95e6 at MCS, within the 1e6 reference), squeeze-film or O-ring damped supports (k ~1.75e6
N/m, c ~900 N s/m).

| critical | damping ratio / AF | position | API requirement |
|---|---|---|---|
| 8.3 krpm (rigid body) | 0.19 / 2.64 | 68 % below minimum speed | 5 % |
| 14.4 krpm (rigid body) | 0.39 / 1.28 | critically damped | none |
| 105.6 krpm (bending) | 0.017 / 29 | 34 % above MCS | 25.8 % |

The bending mode is 34 krpm at zero speed. Its forward branch is stiffened by the gyroscopic moments of the overhung
impeller and turbine (`plots/phase4r_rotor_final.png`), so its synchronous crossing is at 105.6 krpm. The heavy
impeller helps here. The backward branch falls with speed, but unbalance does not excite it with isotropic supports.

Rotor properties:
* mass 2.11 kg, Ip 2.13e-3 kg m²;
* static bearing loads at 1 g: 16.5 N front, 4.2 N rear;
* gyroscopic bearing load 87 N per rad/s of pitch or yaw rate.

**The combustor change (`cc_closure.py`).** The combustor (170 mm) sat 17 mm inside the diffuser, which sets the engine
OD. It is grown to the diffuser envelope (OD 184 mm) and shortened to a 150 mm liner. With liner volume as the
residence measure, the volume-corrected theta is 0.92 × the 7-engine reference mean (-0.42 σ of their log-spread 0.20),
inside the fielded loading band. Burner pressure loss is assumed unchanged (0.05).

Open:
* the liner is 2.2 × annulus height against the rule's 3; combustion efficiency and pattern factor at that length need
  combustor data or tests;
* damper cartridge mass is not separately sourced (it sits inside the bearing-housing allowance).

## 6. Acceleration (`cc_transient.py`, `data/phase4r_accel_ce75000_opr4_t1150_b15_cap.csv`)

Method as in `accel.py`: pyCycle NT4 mode on the real maps, fuel schedule limited by T4 <= 1150 K and a constant-speed
surge margin >= 5 % (10 % also run), with dN/dt from the excess shaft power and the rotor Ip. The table below used
2.07e-3 kg m²; the final rotor (2.13e-3) adds 3 %.

| speed | steady T4 / SMN | limit | excess power |
|---|---|---|---|
| 40 % (idle) | 910 K / 8 % | surge margin | 0.5 kW |
| 50 % | 830 K / 18 % | surge margin | 5.7 kW |
| 70 % | 870 K / 26 % | T4 | 22.8 kW |
| 90 % | 1030 K / 23 % | T4 | 20.4 kW |
| 95 % | 1110 K / 23 % | T4 | 9.5 kW |
| 100 % | 1150 K (SLS max is 98.2 % at T4-max) | - | 0 |

* **Idle (40 %) → 95 %: 6.6 s** (with Ip 2.13e-3); 45 % → 95 %: 3.5 s. With a 10 % transient margin the engine cannot
  accelerate from 40 %.
* Reference: the B300F data sheet quotes 37 → 100 % in 4.6 s.
* Acceleration from idle is limited by surge margin, the same unvalidated quantity as in section 3.

## 7. Engine update and Phase 2 ↔ 4 closure (`cc_closure.py`, `data/phase4r_closure.json`)

**Engine:**
* The Phase 3R engine is reproduced exactly (6.736 kg).
* The Phase 4 changes (raw): shaft +0.24 kg, casing -0.12, liners -0.06, tunnel +0.03.
* **6.85 kg calibrated** (6.49-7.21), length 426 mm, OD 186.6 mm.

**Mass budget** (Phase 2 bottom-up airframe at this engine's diameter and length; accessories 1.60 kg; 15 % growth;
fuel from the sortie flown on the Phase 3R real-map deck, since the cycle is unchanged), iterated:

| item | kg |
|---|---|
| engine (Phase 4, calibrated) | 6.85 |
| engine accessories | 1.60 |
| structure | 3.82 |
| landing gear + chute | 1.27 |
| fuel system | 0.40 |
| systems, avionics, instrumentation | 2.02 |
| growth allowance 15 % | 1.13 |
| fuel (sortie + 120 s reserve + 3 % unusable) | 2.98 |
| **TOGW** | **20.09** |
| **margin to 25 kg** | **4.91** |

**Checks at the closed mass** (S 0.30 m²):

| check | nominal wave drag | pessimistic |
|---|---|---|
| dash thrust margin (target 25 %) | +54.7 % | +28.5 % |
| brake release to M 1.02 / 5 km | 27.7 s | 27.9 s |
| minimum excess thrust, transonic acceleration | 177 N | 116 N |
| 3 g sustained turn at M 0.9 / 5 km | +283 N | +283 N |
| take-off ground roll / V_LOF | 46 m / 48.6 m/s | |

Landing at 17.7 kg (Phase 2 model, μ_brake 0.3): 175 m with flaps + chute, 194 m chute without flaps, 316 m with flaps
only. Against the 300 m runway assumption (A1.7) the drag chute stays required, as in Phase 2 (D2.5). **The 25 kg
constraint closes with 4.9 kg of margin.**

## 8. Assumptions added in Phase 4

| id | assumption | status |
|---|---|---|
| A4R.1 | combustor liner 0.8 × the Phase 3 rule, grown to the diffuser envelope; loading judged by the volume-corrected theta | -0.42 σ inside the reference spread; combustion efficiency at L/D_ref 2.2 unverified |
| A4R.2 | rotor supports: squeeze-film / O-ring damped cartridges, k ~1.75e6 N/m, c ~900 N s/m (Gunter 2023) | damper realisation, temperature and nonlinearity not modelled; mass inside the housing allowance |
| A4R.3 | bearing DN 0.95e6 at MCS acceptable for hybrid ceramic ball bearings | reference micro gas turbine 1e6 (Phase 4 R4.R2 source) |
| A4R.4 | exducer blade frequencies without centrifugal stiffening | conservative for the crossing speeds |
| A4R.5 | acceleration fuel schedule: T4 <= 1150 K, SMN >= 5 % | SMN magnitude unvalidated (R4R.1) |

## 9. Open risks and decisions for the design freeze (Phase 5 not started)

1. **R4R.1, surge margin (top risk).** The compressor's real surge line is governed by vaned-diffuser stall, which is not
   modelled. The only real-stage evidence (HECC) had 8.4 % design margin, and the peak surrogate was wrong there by a
   factor of about 9. Options:
   * (a) design the vaned diffuser for incidence range: low-solidity or wedge vanes, a larger vaneless gap; fewer vanes
     also help vibration;
   * (b) a vaneless diffuser: wider range but lower efficiency and a larger diameter; the trade needs its own analysis;
   * (c) more backsweep (-20°): +11 to +14 points of peak SMN (TurboFlow 28 → 39 %, turbo-design 6.5 → 20 %), at -4
     points of dash thrust margin (+24 %, just under the target);
   * (d) a start / handling bleed or a variable nozzle, as studied for the axial;
   * (e) accept and verify by rig test.

   The decision is the user's.
2. **Impeller vibration:** the 19-vane diffuser excites exducer mode 1 at idle. Choose the vane count together with (1).
3. **Combustor at 2.2 × annulus height:** needed for rotor dynamics; its combustion performance is unverified.
4. **Diffuser sizing sets the diameter** (Phase 3R open item). R4/R2 1.35 is kept, since neither tool can size it. The
   Nike check suggests the diameter is conservative by ~10 mm.
5. **Turbine on its 350 MPa limit** (material and life data); **damper cartridges** (design and mass); **3D impeller
   FE** and LCF.

## 10. Scripts (`scripts/phase4_turbomachinery/`)

| script | job |
|---|---|
| `td_check.py` | NASA turbo-design check of the three impellers |
| `hecc_surge_check.py` | surge surrogate against NASA HECC measured data |
| `cc_blade_modes.py` | exducer blade modes / Campbell screening |
| `cc_rotor.py` | rotor model and critical-speed map |
| `cc_rotor_stiffening.py` | levers on the bending critical |
| `cc_rotor_final.py` | chosen configuration (`plots/phase4r_rotor_final.png`) |
| `cc_transient.py` | acceleration |
| `cc_closure.py` | engine update and Phase 2 ↔ 4 mass closure |

Changes to shared code:
* `impeller_stress_gate.analyse_hub` returns mass properties (additive);
* `engine_mass.engine` takes shaft / tunnel / damper overrides (defaults unchanged).
