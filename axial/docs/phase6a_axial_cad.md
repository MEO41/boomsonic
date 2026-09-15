# Phase 6A (axial): exploratory packaging and mass CAD (2026-09-15)

> **What this is, and what it is not.**
> Exploratory CAD of the **axial option** (`ax80000_opr5_t1150_n6_cap_3r`, `axial/docs/design_freeze_axial.md`), run on the
> user's instruction to resolve as much of **open risk 4.4 (unsourced variable-geometry hardware)** as geometry and
> mass can, and to answer whether the shaft, bearings, bleed ducting and VIGV actuation ring physically fit inside the
> 142.45 mm engine OD.
> * **It is not a build release.** No manufacturing drawings, no tolerancing, no material release.
> * **It is not an architecture decision.** The **centrifugal remains the baseline** and its Phase 6 status is
>   unchanged and still held; freeze decision 1 (which engine goes forward) is still open.
> * **It resolves none of the axial freeze's open risks** except as stated in section 7. R4.1 (the unvalidated
>   stage-stacking model) is untouched, and every aerodynamic number quoted here inherits it.
> * Blade aero surfaces are out of scope: blades are volume-correct envelopes, not aerofoils.
> * **Nothing was resized, moved or re-sized to fit.** Where hardware does not fit, it is drawn clashing and reported.

Toolchain: **CadQuery 2.8 / OCCT 7.9 in `.venv-cad`** (user-approved), the same stack and helpers (`cadlib.py`) as the
centrifugal Phase 6. Every boolean is checked by volume.

---

## 1. What was built, and from what

Per-stage geometry was taken **stage by stage** from `axial/data/phase3ax/axt_<tag>.json` (`levels.fielded.comp.stages`);
nothing is scaled or evenly spaced. The axial stack-up follows the compressor's own rule
(`scripts/phase3_cycle/axial_design.py:41`: `row_gap_to_chord = stage_gap_to_chord = 0.25`, each row occupying
1.25 × chord), and the disc / bearing / turbine stations are the ones `rotor_model.geometry()` used for the
rotordynamic pass, so the CAD and the rotor model share one layout.

| | stage 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| rotor chord (mm) | 21.38 | 16.81 | 13.62 | 11.30 | 9.55 | 8.20 |
| rotor r_hub / r_tip (mm) | 20.30 / 52.38 | 23.73 / 48.95 | 26.12 / 46.56 | 27.87 / 44.82 | 29.18 / 43.50 | 30.19 / 42.49 |
| disc station x (mm) | 28.37 | 77.08 | 115.83 | 147.52 | 174.00 | 196.52 |
| **stage pitch (mm)** | — | **51.6** | **40.7** | **33.1** | **27.6** | **23.4** |

The pitch more than halves front to back: assuming even spacing would have misplaced the rear stages by ~26 mm.

67 solids were built, all valid (`axial/data/phase6a/engine_cad_mass.csv`, `vg_cad_mass.csv`). Parameter sheet:
`axial/data/phase6a/axial_params.json`, every entry tagged frozen / derived / provisional with its source.

---

## 2. The variable geometry as real mechanisms, with real actuators

### 2.1 Actuation loads (first-order, `make_params_axial.py`)

| system | load | basis |
|---|---|---|
| **VIGV** | 8.6 N lift per vane, hinge moment 24.6 N mm per vane, **unison-ring force 57 N**, stroke 1.57 mm | cascade lift `CL = 2 (s/c) cos a_m tan a2` at the design 22.4° swirl, q 19.4 kPa at the compressor face; centre of pressure 0.15 c aft of a 0.30 c spindle; bushing friction µ 0.2 |
| **bleed** | choked port area 3.34 cm², ΔP 203 kPa, seal force 68 N, **band torque 1.02 N m** | 10 % of 1.360 kg/s at the stage-3 total state (257 kPa, 433 K), Cd 0.8, band friction µ 0.3 at r 50.0 mm |
| **variable nozzle** | 56 N per flap, **total hinge moment 27.0 N m over 14.1° of flap travel = 6.7 J of work** | mean flap inner static 82 kPa (turbine-exit static to choked throat) against 54 kPa ambient at 5 km; the linkage-independent invariants |

The nozzle figure is the one that matters: force and stroke trade with the lever ratio, **the hinge moment and the work
do not**. The modelled linkage (pushrod at 0.8 of the flap length, 30° to the flap) turns 27.0 N m into a **729 N**
sync-ring load over a 33.9 mm stroke.

### 2.2 Actuators selected from datasheets (`axial/data/phase6a/actuators.json`)

The freeze's placeholder was 3 × 75 g hobby servos. Replaced with:

| system | part | mass | rated torque | demand | verdict |
|---|---|---|---|---|---|
| VIGV | **Volz DA 22-12-2615** | 105 g | 0.80 N m | 0.285 N m on a 5 mm arm (18.3° travel) | **torque OK, 36 % utilised**; temperature OK (~16 °C at the compressor face) |
| bleed | **Volz DA 22-12-2615** | 105 g | 0.80 N m | 0.51 N m through a 2:1 crank (40° travel) | torque OK, 64 % utilised; **temperature NOT COMPLIANT** — 433 K (160 °C) manifold against a **+70 °C** rating |
| variable nozzle | **Volz DA 22-12-4112** | 132 g | 1.20 N m (peak 3.00) | **27.0 N m to hold** | **NOT COMPLIANT** (below) |

Volz DA 22: case 41.5 × 45.5 × 22.0 mm (2615) / 41.5 × 65.9 × 22.0 mm (4112), −30…+70 °C, backlash ≤ 0.5°, IP 67
([datasheet Rev D](https://www.volz-servos.com/fileadmin/user_upload/Downloads/Datasheets/DA-22_Datasheet_Rev_D.pdf)).

**Why the nozzle actuator fails.** Holding 27.0 N m on the 1.20 N m rated torque needs a **22.5:1 reduction**, which
makes the servo travel 22.5 × 14.07° = **317°** — only the optional 330° extended-travel version reaches it, and a
22.5:1 reduction is a screwjack or gear stage that **is not in the freeze's 0.279 kg flap/ring/hinge estimate** (it is
drawn here as an 83 g block). On peak torque (3.00 N m) a 9:1 bellcrank holds it with *zero* margin, which is not a
design. Independently, the actuator sits beside a **937 K** jet pipe against a **+70 °C** rating.
The alternative considered, an **Actuonix P16-50-256** (95 g, self-locking so it holds without power,
[datasheet Rev B](https://s3.amazonaws.com/actuonix/Actuonix+P16+Datasheet.pdf)), is worse on both counts: 300 N lift
and 500 N maximum static against the 729 N of the modelled linkage, and a −10…+50 °C rating.

---

## 3. Packaging: what does not fit (`ax_clash.py`, `axial/data/phase6a/clash_report.json`)

**The space available.** The compressor casing OD is 110.26 mm and the engine OD is 142.45 mm (combustor-set), so the
variable geometry has a **16.10 mm radial annulus** to live in over the compressor. There is no outer casing there —
`engine_mass` puts sheet metal only over the hot section — so the full 16.10 mm is free. It is still not enough: the
**smallest dimension of a DA 22 case is 22.0 mm**.

### 3.1 Parts outside the 142.45 mm engine OD

Confirmed by boolean (part minus the OD cylinder):

| part | max radius | over the OD | volume outside |
|---|---|---|---|
| **nozzle actuator** | 127.10 mm | **+55.87 mm** | 81 531 mm³ |
| nozzle reduction stage | 104.91 mm | +33.68 mm | 30 000 mm³ |
| nozzle pushrods | 93.36 mm | +22.14 mm | 1 402 mm³ |
| **VIGV actuator** | 82.48 mm | **+11.25 mm** | 21 850 mm³ |
| nozzle sync ring | 78.83 mm | +7.61 mm | 7 825 mm³ |
| VIGV cranks | 78.38 mm | +7.15 mm | 601 mm³ |
| **bleed actuator** | 76.56 mm | **+5.33 mm** | 4 591 mm³ |
| VIGV spindles | 72.38 mm | +1.15 mm | 114 mm³ |

The sync ring and pushrods are outside because `ax_closure` sizes the sync ring at r8_max + 10 mm = 76.83 mm, which is
5.6 mm outside the engine line before any actuator is added.

**What does fit:** the bleed manifold, band valve, ports and the full-area collector duct (its outer end reaches
exactly the 142.45 mm line); the VIGV unison ring (r 66.38 mm, 9.25 mm clear of the casing); and the nozzle flaps at
both stops (71.16 mm at fully open, 0.07 mm inside the OD).

### 3.2 Axial overhang

| | |
|---|---|
| VIGV vane row | starts **6.38 mm ahead** of the compressor front face (chord 17.11 mm + the 0.25-chord gap do not fit in the 15 mm front allowance) |
| VIGV actuator / bracket | 24.75 mm ahead of the front face |
| nozzle flaps | 28.1 mm **aft** of the raw engine length |
| sync ring / pushrods | 16.6 / 14.1 mm aft |
| nozzle actuator and heat shield | 36.1 mm aft |

So the engine as packaged is at least **495.1 + 6.4 + 36.1 = 537.6 mm raw**, i.e. **+42.5 mm (+8.6 %)** on the frozen
raw length, before the ×1.209 length calibration. The frozen 598.7 mm calibrated length has no allowance for either end.

### 3.3 Interferences (assembly joints excluded)

| pair | common volume | what it means |
|---|---|---|
| **rotor drum × stage-1…3 stators** | 3 027 + 1 737 + 526 + 427 + 97 mm³ | **section 4** |
| ngv_shroud_ring × turbine_shroud | 8 441 mm³ | two `engine_mass` rings occupy the same space: a **double count** of ~67 g of IN-713LC |
| VIGV actuator × unison ring / spindles / cranks | 727 + 209 + 66 + 41 mm³ | the actuator body occupies the crank circle: it cannot be mounted there |
| nozzle flaps (open) × heat shield | 93 mm³ | the flaps hit the shield at the fully open stop |
| nozzle_outer_cone × hinge ring | 221 mm³ | the fixed cone was not trimmed where the flaps replace it (modelling, not hardware) |

### 3.4 Clearances that are fine

| | |
|---|---|
| shaft OD to tunnel ID | 1.00 mm |
| tunnel OD to combustor inner liner | 7.79 mm |
| **front bearing (28 mm OD) inside the 20.30 mm inlet hub** | **6.30 mm** clear (housing 3.30 mm) |
| VIGV unison ring to casing | 9.25 mm |
| nozzle flaps to tail cone (both stops) | 22.7 / 22.9 mm |
| nozzle flaps (open) to hot casing | 8.36 mm |

**So the answer to the packaging question is split:** the *rotating and internal* hardware — shaft, journals,
bearings, tunnel, bleed manifold and its full-area duct — **fits comfortably**. The *actuation* hardware does not:
all three actuators, the VIGV cranks and spindles, and the nozzle sync ring and pushrods lie outside the 142.45 mm
line.

---

## 4. The rotor drum, as modelled, cannot be built

The rotordynamic pass (D4A.2, `axial/docs/design_freeze_axial.md` section 3) uses a **2 mm Ti drum at a constant mean radius
of 26.23 mm**, taken from `ax_closure`'s `r_bar = mean(rotor r_hub)`. But the compressor hub line rises from 20.30 mm
to 30.19 mm through the six stages, so a constant-radius drum stands **above** the hub line in the front half:

| row | hub radius | drum outer radius 27.23 mm stands |
|---|---|---|
| stage 1 rotor | 20.30 mm | **6.93 mm into the flow path** |
| stage 1 stator | 21.44 mm | 5.79 mm into the flow path |
| stage 2 rotor | 23.73 mm | 3.50 mm into the flow path |
| stage 2 stator | 24.50 mm | 2.73 mm into the flow path |
| stage 3 rotor | 26.12 mm | 1.11 mm into the flow path |
| stage 3 stator | 26.67 mm | 0.56 mm into the flow path |

It intersects the stage-1 to stage-3 stator vanes and their inner shroud bands, and swallows part of the stage-1 and
stage-2 rotor blade roots. A buildable drum must follow the hub line (stepped or conical), which changes its bending
stiffness and therefore the rotor's bending critical.

**This does not say the rotordynamic result is wrong**, and it does not re-open it here: it says the API 684 pass at
122.3 krpm (46 % above MCS) rests on a drum geometry that cannot be built as modelled, and the check should be re-run
on a hub-following drum before the result is relied on. Added as an open item.

---

## 5. Flow path: the nozzle is not the engine's throat (`ax_flowpath_check.py`)

A packaging model is an area model, so every annulus was compared with the flow it must pass
(`W_choke = A p0 sqrt(γ/(R T0)) (2/(γ+1))^((γ+1)/(2(γ−1)))`).

**Verification first:** applied to the nozzle throat at the cycle's own A8 and Pt5, the relation reproduces pyCycle's
sizing to **−0.6 %** (the nozzle is choked at the design point by construction). The method is therefore sound.

| station | area | required | choked capacity | margin |
|---|---|---|---|---|
| compressor rows 1–12 | 73.2 → 27.0 cm² | 1.360 kg/s | 1.60–2.12 kg/s | +17.5 % … +56.2 % |
| **turbine exit annulus** | **66.02 cm²** | **1.381 kg/s** | **1.292 kg/s** | **−6.5 %** |
| nozzle throat A8 (×1.0) | 70.16 cm² | 1.381 kg/s | 1.373 kg/s | −0.6 % (choked by design) |
| nozzle throat A8 (×2.0) | 140.32 cm² | 1.381 kg/s | 2.745 kg/s | +98.8 % |

The compressor is comfortable everywhere. But **A8 / A_turbine-exit = 1.063**: the minimum area of the drawn hot end
is the **turbine exit annulus, not the nozzle throat**, and at the fielded Pt5 of 151.4 kPa that annulus can pass only
1.292 kg/s against the 1.381 kg/s required.

**Traced cause.** `arch_trade.turb_pout` converts the cycle's Pt5 into the static pressure handed to TurboFlow by
**assuming an exit Mach of 0.45**. TurboFlow hit that static pressure (132.6 kPa) but with an exit velocity of
**408 m/s at −19.5° swirl, i.e. M ≈ 0.71**, so its own exit total pressure is **184.0 kPa**, not the cycle's 151.4 kPa.
The annulus is sized for the tool-level machine (η_tt 0.917); the cycle runs the fielded one (η_t 0.75), whose lower
exit pressure needs about 53 % more area — unreachable with the tip radius already capped by the 350 MPa blade-root
limit.

This is the same tool-vs-fielded mismatch the project has already found twice (F3R.3 for √W scaling, F4A.2 for the
loss split), appearing this time as an area. **Consequence for the variable nozzle specifically:** at high speed the
controlling area is upstream of the flaps, so the nozzle has less authority over the running line than
`ax_operability` assumed. How much less is not assessed here. **Not fixed, not re-run: reported.**

---

## 6. Mass (`ax_mass_compare.py`, `axial/data/phase6a/mass_compare.csv`)

Compared against the **raw** bottom-up model, not the calibrated 6.863 kg: the ×1.2025 calibration exists for exactly
what the CAD does not draw (flanges, bolts, fillets, seals, manifold, igniters, wiring).

**Core engine: the model holds up.** Blades −3.0 %, discs −3.1 %, stators −3.4 %, liners −0.4 %, hot casing −0.4 %,
turbine disc and NGV rings exact. Two items disagree, in opposite directions:

| item | model raw | CAD | Δ | why |
|---|---|---|---|---|
| shaft | 0.950 kg | 1.056 kg | **+106 g** | `engine_mass` uses `L_shaft = 0.72 × L_total` = 356 mm; the layout needs 434 mm (front face to turbine disc) |
| shaft tunnel + bearing housings | 0.368 kg | 0.167 kg | **−201 g** | the model adds a flat +0.12 kg for housings/preload; the CAD housings are thin placeholders — here the **model is the more realistic of the two** |
| bearings | 0.050 kg | 0.063 kg | +13 g | the CAD draws solid rings; a real bearing is not solid — the CAD over-models |

Core CAD total 4.154 kg against 4.289 kg of model items, i.e. **−3.1 %**.

### 6.1 Variable geometry: the number Phase 6A was run for

| system | freeze allowance | CAD | Δ | ratio |
|---|---|---|---|---|
| VIGV | 165 g | 232 g | +66 g | 1.40 |
| bleed | 122 g | 200 g | +79 g | 1.65 |
| variable nozzle | 354 g | 695 g | **+342 g** | 1.97 |
| **total** | **640 g** | **1127 g** | **+487 g** | **1.76** |

Where the +487 g comes from:
* **+248 g of hardware the freeze's estimate did not contain at all**: the nozzle heat shield (165 g) and the 22.5:1
  reduction stage the actuator needs (83 g);
* **+117 g of real actuators** (105 + 105 + 132 g against 3 × 75 g);
* **+52 g of brackets** (three 3 mm mounting brackets, 26 g each);
* **+18 g** of bleed collector duct;
* the rest is the geometric items coming out heavier when drawn as solids.

The heat shield is drawn as a full 360° ring; a local shield would be lighter, so the nozzle figure is the softest of
the three. The two actuator masses are datasheet values and are firm.

### 6.2 What this would do, if carried through

**Not carried through — no re-closure was run.** For scale only, at the frozen calibration and with no airframe
re-iteration:

| | frozen | with the CAD variable geometry |
|---|---|---|
| raw dry mass | 5.708 kg | 6.194 kg (+487 g) |
| calibrated dry mass | 6.863 kg | **7.449 kg (+586 g)** |
| TOGW, powered-descent case | 22.12 kg (margin 2.88) | 22.71 kg (**margin 2.29 kg**) |
| TOGW, engine-off case | 18.54 kg (margin 6.46) | 19.13 kg (margin 5.87 kg) |

Both stay under 25 kg. The powered-descent case is in any event not physically possible for this engine (freeze 4.2).

---

## 7. What Phase 6A changed, and what it did not

**Resolved, partly:** open risk 4.4 is no longer "no sourced hardware". The VIGV and bleed actuators now have a
named, in-production part with adequate torque margin, and the variable-geometry mass is a CAD number, 1.76 × the
allowance. **Still open within 4.4:** the bleed and nozzle actuators are outside their temperature ratings, the
nozzle has no compliant actuator at all, no actuator rates were checked against the transient assumption
(freeze 4.7), and no ECU, failure modes or bleed discharge path beyond the engine OD were addressed.

**Untouched:** R4.1 and everything downstream of it (4.1), idle at 77.5 % and the descent concept (4.2), start (4.3),
dash throttling (4.5), blade roots and resonances (4.6), and the absence of hardware validation (4.8).

**New open items from Phase 6A:**

| id | item |
|---|---|
| **R6A.1** | The actuation hardware does not fit inside the 142.45 mm OD — worst case the nozzle actuator at +55.9 mm. Either a local fairing (which changes the airframe cross-section and the wave drag the whole dash margin rests on) or remote mounting with long pushrods; neither assessed. |
| **R6A.2** | The engine is at least 42.5 mm longer than the frozen raw length once the VIGV row and the nozzle mechanism are packaged. |
| **R6A.3** | No off-the-shelf actuator found for the variable nozzle: 27.0 N m of hold, 6.7 J of work, beside a 937 K jet. |
| **R6A.4** | The rotordynamic drum geometry (constant radius) is not buildable; the API 684 pass should be re-run on a hub-following drum. |
| **R6A.5** | The drawn hot end has its minimum area at the turbine exit annulus, not at the nozzle throat, and that annulus is 6.5 % short of capacity at the fielded Pt5. Traced to the exit-Mach 0.45 assumption in `arch_trade.turb_pout`. Affects the variable nozzle's authority at high speed. |
| **R6A.6** | Minor `engine_mass` items: the 0.72 × L shaft rule (−106 g), the NGV shroud / turbine shroud double count (~67 g). |

**Phase 6A does not change the engine choice.** The centrifugal baseline and its Phase 6 work are untouched, and
freeze decisions 1–5 remain open.

---

## 8. Files

| | |
|---|---|
| parameters | `axial/data/phase6a/axial_params.json` (frozen / derived / provisional per entry) |
| actuators | `axial/data/phase6a/actuators.json` (datasheet values, cited) |
| CAD | `axial/cad/parts/*.step` (67 parts), `axial/cad/axial_core_assembly.step`, `axial/cad/axial_vg_assembly.step` |
| mass | `axial/data/phase6a/engine_cad_mass.csv`, `vg_cad_mass.csv`, `mass_compare.csv`, `vg_mass_breakdown.csv` |
| packaging | `axial/data/phase6a/clash_report.json` |
| flow path | `axial/data/phase6a/flowpath_check.json` |

| script | venv | purpose |
|---|---|---|
| `axial/scripts/phase6a_axial_cad/make_params_axial.py` | `.venv` | parameter sheet + actuation loads |
| `axial/scripts/phase6a_axial_cad/ax_flowpath_check.py` | `.venv` | flow-path area / choking capacity |
| `axial/scripts/phase6a_axial_cad/ax_engine_cad.py` | `.venv-cad` | core engine solids |
| `axial/scripts/phase6a_axial_cad/ax_vg_cad.py` | `.venv-cad` | the three variable-geometry mechanisms |
| `axial/scripts/phase6a_axial_cad/ax_clash.py` | `.venv-cad` | envelope, interference, clearances |
| `axial/scripts/phase6a_axial_cad/ax_mass_compare.py` | `.venv-cad` | CAD vs the raw mass model |
