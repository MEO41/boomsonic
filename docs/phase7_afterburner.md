# Phase 7 — Afterburner (2026-09-15)

**What this is.** The user asked for an afterburner on the frozen centrifugal engine, and chose its
purpose and the nozzle treatment: **extend the envelope past Mach 1**, and **decide the variable
nozzle on numbers across three concepts**. This is the conceptual study of that afterburner.

**What it is not.** It is not a design freeze, it does not resolve any of the open decisions in
`docs/design_freeze.md` section 6, and it does not touch the Phase 6 CAD. The frozen engine's open
risks (surge margin 4.1, idle transient 4.2, combustor length 4.3, exducer/vane resonance 4.4, no
hardware validation 4.5) are all still open and none of them is made better by this work. Three of
them are made **worse**, and that is stated in section 10.

Every number here comes from a tool run or a cited relation. Scripts are in
`scripts/phase7_afterburner/`, data in `data/phase7/`, figures `plots/phase7_*.png`.

---

## 1. Headline

| question | answer |
|---|---|
| Does the tool support it, and is the baseline undisturbed? | Yes. `cycle_model.py` gains an `afterburner` option, **off by default**. With it off the model reproduces the frozen fielded dash point to every digit, and the real-map dry deck to 0.000 % at all ten Mach numbers. |
| What does it buy at the dash? | **+79 % net thrust**: 500 → 896 N at M 1.02 / 5 km, at Tt7 1900 K. TSFC 0.164 → 0.267 kg/(N h). |
| How far past Mach 1 does it get? | **It is not thrust-limited anywhere up to M 2.0.** The limit moves to the engine's own hot end: the **turbine exit annulus chokes at M 1.33**. The airframe's dynamic pressure doubles at M 1.41. |
| What does the nozzle have to do? | Open **54 % in area** (throat 94.9 → 119.3 mm). Without that, the afterburner buys +10 % instead of +79 % **and halves the surge margin**. |
| Which nozzle? | **Translating plug.** Its actuation load is 123 N against the iris's 1198 N — 9.7 × less — and it is the only concept for which a sourced, in-production actuator meets the load. |
| Does it still close under 25 kg? | **Yes, but only just, and only if the afterburner is used briefly.** 24.78 kg (+0.22 kg margin) for the conservative build used for the supersonic acceleration and the 7 s hold. **26.02 kg — over the limit — if it runs through the whole 27.7 s acceleration.** |
| What does it cost? | **+4.08 kg** and **+458 mm** of engine length: the engine more than doubles (426 → 810 mm raw CAD). |
| Does it draw? | Yes — `cad/engine_with_afterburner_assembly.step`, built on the Phase 6 engine with 25 of its parts carried over unchanged and 17 new ones, **42/42 solids valid**. The afterburner fits inside the engine envelope with a 10.2 mm annulus to spare; **its nozzle actuator does not fit anywhere** (section 9.1). CAD mass is +0.298 kg over the model, which puts TOGW **0.100 kg over the 25 kg ceiling**. |

---

## 2. Verification before anything else (`verify_ab_cycle.py`)

Per the brief's rule 3. All checks pass.

**0. The Rayleigh relations** added in `ab_common.py` against published Rayleigh-flow tables
(γ 1.4): Tt/Tt\* and Pt/Pt\* at M 0.2 / 0.3 / 0.5, worst error **2.1e-5 relative**.

**1. Regression — the afterburner option changes nothing when it is off.** `cycle_model` with
`afterburner=False` at the frozen fielded dash point:

| | now | frozen | error |
|---|---|---|---|
| Fn | 499.99999 N | 499.99997 N | 4.3e-8 |
| W | 1.3257543 kg/s | 1.3257543 kg/s | 1.7e-16 |
| TSFC | 0.1641596 | 0.1641596 | 4.3e-8 |
| Tt5 / Pt5 | 971.5062 K / 149.3242 kPa | same | < 3e-9 |
| A8 | 70.76905 cm² | 70.76905 cm² | 2.3e-9 |

**2. Null afterburner.** With `afterburner=True`, zero AB fuel and zero AB loss, every quantity
matches the `afterburner=False` run to ≤ 1e-9, and Tt7 = Tt5, Pt7 = Pt5 exactly. The extra station
is transparent, so any later difference is the afterburner and not the plumbing.

**3. The afterburner's own physics.**
* **Fuel bookkeeping.** pyCycle's tabular `ThermoAdd` references the mix ratio to the incoming
  **dry air**, so for a second burner in series the ratio is still per unit dry air and the
  composition accumulates. Checked, not trusted: `Wf_ab = W_air × FAR_ab` to 3.5e-16 and
  `FAR_total = FAR_main + FAR_ab` to 1.5e-16. Had this been read wrong, every TSFC here would be
  wrong.
* **Energy.** The tabular fuel carries **zero injection enthalpy** in the table's datum (the heat of
  reaction lives entirely in the FAR-dependence of *h*), which makes an internal energy balance
  vacuous — so the heat release is checked against **Cantera** instead, the same cross-check
  `phase3_cycle/cantera_check.py` runs on the main burner, extended to a second burn in the
  vitiated stream: **Cantera 1925.7 K vs pyCycle 1900.0 K, +1.35 %.** (The main burner agreed to
  −0.35 % at 1150 K; the gap widens at 1900 K where dissociation and surrogate differences matter
  more.)
* **Area.** A8 against the closed-form choked-throat relation: **+0.15 %**.
* **Thrust.** Fg against momentum + pressure, with Cv debiting the momentum term only (pyCycle
  `nozzle.py:117`): **1.2e-6**.

---

## 3. The design point (`ab_design_point.py`, `plots/phase7_ab_design_point.png`)

Core held exactly at its frozen fielded operating point, nozzle throat free, η_AB 0.90, afterburner
loss = computed flameholder loss + **computed Rayleigh loss**.

| Tt7 K | FAR total | φ overall | Fn N | vs dry | TSFC | A8 cm² | A8/A8_dry |
|---|---|---|---|---|---|---|---|
| 971.5 (dry) | 0.0163 | 0.24 | 500 | 1.00 | 0.1642 | 70.8 | 1.00 |
| 1400 | 0.0289 | 0.43 | 691 | 1.38 | 0.2156 | 89.8 | 1.27 |
| 1700 | 0.0388 | 0.57 | 816 | 1.63 | 0.2467 | 101.3 | 1.43 |
| **1900** | **0.0460** | **0.68** | **896** | **1.79** | **0.2671** | **109.0** | **1.54** |
| 2000 | 0.0498 | 0.73 | 936 | 1.87 | 0.2776 | 112.9 | 1.60 |

**Why the thrust beats the fuel.** The afterburner raises gross thrust about 40 % (jet velocity goes
as √Tt7) but *net* thrust 79 %, because the ram drag — 434 N of the 934 N gross at the dash — is
already subtracted and does not grow. That is the whole reason afterburning is worth more the
faster you go, and it is why section 5's thrust curve climbs with Mach.

**Why 1900 K (A7.1).** Three things converge near there: fielded afterburner practice, a total
FAR of 0.046 that is 8 % inside the tabular thermo's ceiling (see F7.1), and φ 0.68 — comfortably
lean of stoichiometric, so there is still oxygen to spare.

**The thrust answer does not depend on the η_AB assumption.** η_AB sets how much fuel it takes to
reach Tt7, not the thrust at Tt7. Across η_AB 0.75–0.95 the thrust is 896 N unchanged and TSFC moves
0.302 → 0.258. So the *thrust* numbers are firm and the *fuel* numbers carry that band.

---

## 4. The afterburner duct: thermal choking sets a hard ceiling

Adding heat in a constant-area duct drives the flow towards Mach 1 (Rayleigh flow). Past a certain
inlet Mach the required temperature ratio simply cannot be reached — the duct **thermally chokes**.
That is a hard limit, and it is computed, not assumed:

| AB duct Mach | duct diameter | Tt7 the duct can reach | required 1900 K | Rayleigh loss |
|---|---|---|---|---|
| 0.15 | 188.6 mm | 9792 K | ✓ | 1.5 % |
| 0.20 | 164.2 mm | 5743 K | ✓ | 2.7 % |
| 0.30 | 136.1 mm | 2862 K | ✓ | 6.4 % |
| 0.35 | 127.2 mm | 2256 K | ✓ | 9.3 % |
| **0.40** | **120.2 mm** | **1867 K** | **✗ choked** | — |

So the afterburner duct Mach must stay below about **0.39**. Across the whole flight envelope the
duct Mach of the chosen design stays at 0.20–0.25 (section 5), so this limit is never approached in
flight — but it is what stops the duct being made small to save length.

---

## 5. How far past Mach 1 (`ab_envelope.py`, `plots/phase7_ab_envelope.png`)

Run on the **real Phase 3R TurboFlow maps**, fixed geometry, at max throttle (the lower of 100 %
mechanical speed and T4 1150 K — the same ECU logic `cc_mission.deck` uses).

**The nozzle schedule.** The wet point is solved at the dry point's own mechanical speed, and the
throat is opened until T4 returns to its dry value. Same speed and same T4 behind a choked NGV is
the same compressor operating point. The check that this worked is the compressor R-line: **worst
shift dry → wet is 9.9e-4**, i.e. the compressor does not move. That is what a variable nozzle is
*for*, and it is why the surge margin column below is unchanged by lighting the afterburner.

Level flight at 5 km, 20.09 kg:

| Mach | dry N | **wet N** | A8/A8_dry | drag A | drag B | SM dry → wet | turbine-exit margin |
|---|---|---|---|---|---|---|---|
| 1.00 | 490 | 873 | 1.539 | 274 | 364 | 0.278 → 0.278 | +5.9 % |
| 1.02 | 500 | **896** | 1.539 | 326 | 378 | 0.282 → 0.282 | +5.8 % |
| 1.10 | 518 | 950 | 1.542 | 473 | 434 | 0.278 → 0.278 | +5.4 % |
| 1.20 | 553 | 1051 | 1.545 | 509 | 509 | 0.280 → 0.280 | +4.3 % |
| 1.30 | 594 | 1160 | 1.544 | 542 | 588 | 0.272 → 0.272 | **+1.2 %** |
| 1.40 | 622 | 1289 | 1.565 | 616 | 671 | 0.312 → 0.312 | **−3.5 % choked** |
| 1.50 | 674 | 1439 | 1.571 | 695 | 759 | 0.340 → 0.340 | −8.8 % |
| 1.60 | 718 | 1610 | 1.579 | 777 | 850 | 0.376 → 0.376 | −14.4 % |

Drag A is the Phase 2 model extrapolated; drag B is a slender-body wave-drag floor (see below).
Surge margins are the freeze's **unvalidated** surrogate (open risk 4.1) and are shown only to say
that the nozzle schedule leaves them alone — never as absolute margins.

### 5.1 What actually limits the speed

| limit | Mach |
|---|---|
| thrust = drag, **dry**, drag method A | 1.42 |
| thrust = drag, **dry**, drag method B | 1.31 |
| thrust = drag, **with afterburner** | never inside M ≤ 2.0 |
| **turbine exit annulus runs out of capacity** | **1.33** |
| dynamic pressure reaches 2 × the frozen dash value | 1.41 |
| stagnation temperature reaches 120 °C (epoxy screening) | 1.64 |
| afterburner duct approaches thermal choking | never |

**The afterburner removes thrust as the constraint and hands the problem to the engine's own hot
end.** The turbine exit annulus is 75.12 cm² of real TurboFlow geometry; it passes the flow with
5.8 % margin at the dash, and that margin is eaten by rising Mach, reaching zero at **M 1.33**.

So the honest answer to "how far past Mach 1" is: **about M 1.3, and the afterburner is not what
gets you there** — the dry engine already reaches M 1.31–1.42 against drag. What the afterburner
actually buys is not top speed but **margin**: +174 % thrust margin at the dash instead of +53 %,
and a supersonic acceleration that takes 0.22 s instead of 0.66 s.

### 5.2 Why the top speed is given as a band, and why the numbers above M 1.05 are soft

The Phase 2 airframe model states its own validity as *"subsonic to M 1.05"*. Everything above that
is extrapolation, so two methods bracket it:

* **A** — the model as built. Its wave-drag Mach dependence is AeroSandbox's `approximate_CD_wave`,
  which asymptotes to 0.8 × its M 1.2 value and whose own docstring says it "is likely not valid for
  high-supersonic flows".
* **B** — a supersonic floor: volume wave drag held at the slender-body value (Mach-independent to
  first order for a slender body, Ashley & Landahl), plus supersonic C_Lα = 4/√(M²−1).

They differ by 11 % on the dry top speed (M 1.42 vs 1.31). **Neither includes inlet spillage /
additive drag**, which is absent from the Phase 2 build-up altogether and which grows quickly
supersonically. The capture stream tube grows from 55.1 cm² at the dash to 67.0 cm² at M 1.6 —
i.e. the nose pitot is increasingly undersized — and the pitot recovery falls from 1.000 to 0.895
over the same range. All of this makes the M > 1.2 numbers optimistic by an unquantified amount.

**The M 1.33 cap is altitude-independent.** The turbine-exit capacity margin is set by the
compressor match, not by altitude, and the altitude sweep confirms it: +5.6 to +5.8 % at M 1.02 and
−3.4 to −3.6 % at M 1.40 at 3, 5, 7, 9 and 11 km alike (`data/phase7/ab_envelope_alt.csv`). So it is
an envelope-wide cap, not a 5 km one. Thrust at altitude, afterburner lit: 1026 N at M 1.02 / 3 km,
634 N at 9 km, 525 N at 11 km.

---

## 6. The nozzle (`ab_nozzle_trade.py`)

Duty: throat **70.77 → 111.74 cm²** (D 94.9 → 119.3 mm), ratio **1.579** over the whole envelope, at
Pt7 142.4 kPa, Tt7 1900 K, W7 1.387 kg/s against 54.0 kPa ambient. Loads are not assumed: the
internal static-pressure distribution is solved quasi-1D along each moving surface and integrated.

### 6.1 The reference first — what a fixed nozzle costs

Real engine, real maps, dash point:

| A8 scale | dry Fn | dry SM | wet Fn | wet SM |
|---|---|---|---|---|
| 1.00 (sized dry) | 500 N | 0.282 | **548 N** | **0.121** |
| 1.15 | 375 N | 0.385 | 653 N | 0.188 |
| 1.30 | 257 N | 0.467 | 755 N | 0.199 |
| 1.45 | 152 N | 0.531 | 841 N | 0.236 |
| 1.54 (sized wet) | engine will not run | — | 896 N | 0.282 |

**The variable nozzle is not optional.** A fixed dry-sized nozzle turns +79 % into **+9.6 %** and
**halves the surge margin** (0.282 → 0.121) straight into the region open risk 4.1 already says
cannot be predicted. A fixed wet-sized nozzle destroys the dry engine. Every intermediate fixed
area is bad at both ends.

### 6.2 The three concepts

| | **A/B — iris** | **C — translating plug** |
|---|---|---|
| geometry | 12 hinged petals, 90 mm, on the 82.1 mm duct | conical plug in a fixed cowl 82.1 → 62 mm |
| travel | 22.63° → 14.45°, **8.18°** | **51.0 mm** stroke |
| worst load | **112.7 N·m** total hinge moment → **1198 N** at the sync ring | **123 N** axial |
| mass | **0.557 kg** | 0.850 kg |
| actuator | **none compliant.** Best sourced part (Volz DA 22-12-4112, 1.20 N·m) needs a **4.8 × reduction** on a 5 mm crank; the linear P16 needs 3.9 ×. | **Actuonix P16-50-256 at 41 % of rated load**, self-locking |

**Concept C wins, on the load.** 123 N against 1198 N is not a close call, and it is the difference
between "a catalogue part does this" and "a reduction stage has to be designed, which is exactly
what Phase 6A found was missing on the axial engine" (D6A.2). The iris is 0.29 kg lighter, but that
saving disappears into the reduction stage and the heavier actuator it forces.

**Concept B (two-position iris)** carries the same 112.7 N·m as concept A — the mechanism and its
loads are identical and only the control is simpler — so it inherits concept A's actuator problem
without solving it. It is not recommended.

**Both concepts need the actuator mounted forward.** The tailpipe skin sits at **698 °C** and the
jet inside it at **1900 K**, against a +50/+70 °C rating on every sourced part. The only cool
mounting site is the compressor casing at **36 °C**, reached by a pushrod running aft outside the
engine. That pushrod, its thermal growth, and its buckling are **not designed here**.

**Two caveats on concept C that are not resolved:**
1. The stroke is **51.0 mm against the P16-50's 50 mm** — 2 % over. Either the cowl/plug
   proportions change or the 100 mm-stroke variant is used; neither was run.
2. The plug sits on the engine centreline in a 1900 K stream, on a slide bearing. Its support
   struts, cooling and thermal growth are not designed.

---

## 7. The afterburner itself (`ab_hardware.py`)

### 7.1 The turbine exit is not where the cycle thinks it is (F7.4)

The cycle model sets `turb.MN = 0.45` at design. The **real** annulus is 75.12 cm² (hub 36.67, tip
61.12 mm) and at the cycle's own Pt5/Tt5 it has to run at **M 0.761**, with 17.8° of residual swirl.
`arch_trade.turb_pout` used the 0.45 assumption to convert the cycle's Pt5 into the static pressure
handed to TurboFlow (130.8 kPa), so the turbine was designed against a back pressure that does not
match the annulus it was given.

**This is the same inconsistency Phase 6A traced as F6A.5 on the axial engine, and it is
pre-existing in the frozen centrifugal design — Phase 7 found it, it did not create it.** It is what
produces the M 1.33 choking limit in section 5.1, and it is why that limit is an engine limit rather
than an afterburner one.

### 7.2 Length is the real cost

The flow has to be diffused from that 75.12 cm² annulus at M 0.76 to the afterburner duct before
anything can be burnt, and a diffuser that does not separate is long. At the 7° equivalent-cone
half-angle limit (Idelchik, the same source Phase 2 used for the intake diffuser):

| AB duct Mach | duct Ø | diffuser 7° | diffuser 10° | diffuser 12° | burn length | Fn |
|---|---|---|---|---|---|---|
| 0.20 | 164.3 mm | **270.8 mm** | 188.6 mm | 156.4 mm | 102.7 mm | 894.6 N |
| 0.30 | 136.1 mm | 155.9 mm | 108.6 mm | 90.1 mm | 85.1 mm | 852.7 N |

**The diffuser alone is 156–271 mm — comparable with the whole 426 mm engine.** Raising the duct
Mach from 0.20 to 0.30 saves 115 mm of diffuser and 0.8 kg for 4.8 % of thrust, and stays clear of
thermal choking everywhere in the envelope. **That is the recommended change, and it was not carried
through** — the envelope and the nozzle trade were both computed on the 0.20 duct, so the closure
is reported on 0.20 and the 0.30 figures are shown alongside (section 8).

### 7.3 Flame stabilisation — computed, and it changed the answer

The first model assumed the 972 K turbine exit would make the afterburner autoignition-stabilised.
Cantera says it is not: the **autoignition delay of a fresh stoichiometric pocket is 15.8 ms**
against a recirculation-zone residence time of **0.62 ms** — a Damköhler number of **0.039**. At
1.45 bar the mixture simply does not light itself. The afterburner therefore needs a flameholder
**and an igniter**.

Once lit, it holds easily. A well-stirred-reactor blowout calculation (Longwell & Weiss, the
standard bluff-body stabilisation model; continuation down in residence time, because a PSR is
bistable and bisecting from an equilibrated start reports no blowout at all) gives **τ_blowout
0.039 ms** against 0.62 ms available — **Da 15.8**, and the minimum gutter that still holds is
**1.6 mm** against the 25 mm assumed. Blowout is not a constraint here.

Burn length comes from turbulent flame spreading, not autoignition: **103 mm** at duct Mach 0.20
with 2 gutter rings, against 1917 mm if autoignition had been the mechanism.

* **Tool limit (F7.5):** `nDodecane_Reitz.yaml` carries **no gas-phase transport data for c12h26**,
  so a laminar flame speed cannot be solved with it at all. The turbulent flame speed used is
  S_T ≈ 2u′ = 24 m/s, which is turbulence-dominated, so a missing S_L of 1–3 m/s changes the burn
  length by a few per cent. The correlation constant itself (A7.14) is an order-of-magnitude
  estimate.

### 7.4 Liner cooling is the hard problem (R7.3)

In a turbojet afterburner there is no cold air. The only coolant available is turbine-exit gas
**already at 972 K**, and the flame is at 1900 K. For a sheet Hastelloy-X liner at a 1200 K metal
limit the required film effectiveness is

> η_film = (1900 − 1200) / (1900 − 972) = **0.754**

Above about 0.5, conventional single-slot film cooling will not do it; a continuously-injecting
corrugated (screech) liner is needed — which is what real afterburners use, and which is what the
mass model assumes. **No cooling design was done and no liner temperature was computed.** This is
the least-resolved part of the afterburner.

### 7.5 Module mass and length

Bottom-up, at duct Mach 0.20 and the 7° diffuser limit: **2.928 kg**, 373.5 mm (diffuser 270.8 +
burn 102.7), plus the 110 mm nozzle cowl. The largest items are the diffuser outer cone, the outer
casing and the corrugated liner.

---

## 8. Closure against 25 kg (`ab_closure.py`)

Added: AB module 2.928 + plug nozzle 0.850 + actuator and linkage 0.155 + AB fuel system 0.150 =
**4.082 kg**. Engine length **426.2 → 909.6 mm (+484 mm, +113 %)**.

**Fuel.** The afterburner burns 0.0665 kg/s against 0.0228 kg/s dry — **2.91 ×**. How much that
costs depends entirely on when it is used, and the supersonic acceleration turns out to be very
short (M 1.00 → 1.02 at 5 km takes **0.66 s dry, 0.22 s wet**):

| usage | wet time | extra fuel |
|---|---|---|
| the 7 s Mach-1 hold only | 7.0 s | +0.315 kg |
| supersonic acceleration + hold | 7.2 s | +0.325 kg |
| whole brake-release-to-M 1.02 acceleration + hold | 34.7 s | +1.560 kg |

**Closure matrix** (frozen TOGW 20.085 kg, margin 4.915 kg):

| configuration | length added | hardware | fuel | TOGW | margin | closes |
|---|---|---|---|---|---|---|
| **M_ab 0.20, 7° (as computed)** | 483 mm | 4.082 kg | +0.325 | **24.78 kg** | **+0.22 kg** | **yes** |
| M_ab 0.20, 7°, afterburner used throughout | 483 mm | 4.082 kg | +1.560 | **26.02 kg** | **−1.02 kg** | **no** |
| M_ab 0.20, 12° | 369 mm | 3.510 kg | +0.325 | 24.17 kg | +0.83 kg | yes |
| M_ab 0.30, 10° (recommended, not carried through) | 304 mm | 2.872 kg | +0.325 | 23.49 kg | +1.52 kg | yes |
| M_ab 0.30, 10°, afterburner used throughout | 304 mm | 2.872 kg | +1.560 | 24.72 kg | +0.28 kg | yes |

**So the afterburner fits — but the margin is thin enough that how it is flown decides whether it
fits at all.** With the conservative 7° diffuser it closes with 0.22 kg to spare on a brief
afterburner usage and fails by 1.02 kg on a long one. The recommended duct-Mach-0.30 build closes
in every case.

**Dash margin at the closed mass** (24.78 kg, M 1.02 / 5 km): dry **+53.0 %** (pessimistic wave
drag +37.5 %), afterburner lit **+174.2 %** (+146.4 %).

**A drag caveat that matters.** The Phase 2 fuselage is fixed-geometry (L_fus 2.70 m, D_fus =
D_engine + 30 mm), so making the engine 484 mm longer changes almost nothing in the drag model —
zero-lift drag area moves 81.9 → 82.6 cm². That is a **limitation of the model, not a result**: a
910 mm engine in a 2.70 m fuselage has real consequences for centre of gravity, tail arrangement,
structural layout and the nozzle/boattail junction, **none of which is modelled here**. Separately,
correcting the frozen closure's leftover Phase 2 placeholder nozzle and capture areas (49.1 → 70.8
and 47.5 → 55.1 cm²) by itself moves the dash margin +54.70 % → +55.13 %.

---

## 9. CAD (`ab_cad.py`, `ab_render.py`)

`cad/engine_with_afterburner_assembly.step`, with the parts in `cad/afterburner/`, figures
`plots/phase7_ab_section.png` and `plots/phase7_ab_cutaway.png`.

**Built on the Phase 6 engine, not instead of it.** Every Phase 6 part is imported from
`cad/engine/*.step` unchanged — **25 parts carried over bit-for-bit** — and only the two the
afterburner physically replaces are dropped: `nozzle_outer_cone` (the dry convergent nozzle) and
`tail_cone`. Nothing upstream of the turbine exit was re-drawn, so the compressor, combustor,
turbine, shaft and impeller in this assembly are the geometry Phase 6 already checked. **17 new
parts** are added, plus the plug drawn a second time in its dry position as a separate file.
**42 of 42 solids pass `BRepCheck_Analyzer`.**

Every new dimension is read from the Phase 7 data files (`ab_hardware.json`, `ab_nozzle_trade.json`,
`ab_design_point.json`) and the Phase 6 parameter sheet — nothing is typed into the CAD script.

| section | x from the impeller nose | geometry |
|---|---|---|
| turbine exit (where the afterburner starts) | 296.4 mm | hub 36.67, tip 61.12 mm |
| diffuser | 296.4 → 567.2 mm (270.8 mm) | outer wall 64.02 → 82.09 mm (3.82°), hub 36.67 → 3.0 mm (7.65°) |
| burn section | 567.2 → 669.9 mm (102.7 mm) | duct r 82.09 mm, corrugated liner at 76.09 mm, 2 gutter rings |
| nozzle cowl | 669.9 → 779.9 mm (110.0 mm) | 82.09 → 62.00 mm |
| plug | shoulder 40.5 mm into the cowl (wet) | dry position 91.4 mm, **51 mm stroke**; tip at x 810.3 mm |

**Length, corrected.** The dry engine's nozzle ended at x 352.5 mm, and the afterburner replaces it,
so the engine grows by **457.9 mm**, not by the 483.5 mm module length the closure charged. The
closure therefore used the conservative figure, which is the right way round.

### 9.1 The flow path fits; the actuator does not

| part | max radius | vs the 93.31 mm envelope |
|---|---|---|
| nozzle actuator | 118.31 mm | **+25.00 mm** |
| nozzle pushrod | 110.31 mm | **+17.00 mm** |
| nozzle radial link | 107.31 mm | **+14.00 mm** |
| igniter | 98.09 mm | **+4.78 mm** |
| fuel manifold | 91.09 mm | −2.22 mm |
| afterburner duct and casing | 83.09 mm | −10.22 mm |
| everything else | ≤ 82.09 mm | inside |

**The afterburner itself fits comfortably** — the duct sits at r 83.09 mm inside a 93.31 mm
envelope, a 10.2 mm free annulus, because the compressor diffuser sets the engine diameter and the
afterburner is slimmer than the combustor it follows. **What does not fit is the nozzle actuator,
and there is nowhere in the aircraft to put it:**

* a Volz DA 22 case is 22.0 mm on its smallest side and the Actuonix P16 body about 20 mm;
* over the afterburner duct there is a 10.2 mm annulus — too small;
* over the compressor casing, where D7.4 says the actuator has to sit for temperature, there is no
  annulus at all (the casing *is* the envelope);
* Phase 6 measured the engine-to-fuselage-skin gap at **8.7 mm** — too small as well.

This is **Phase 6A's F6A.2 repeated on the centrifugal engine** (R7.8). The two fixes — a local
fairing, which changes the airframe cross-section and therefore the wave drag the whole dash margin
rests on, or a longer remote linkage — are **not assessed**. The actuation train is drawn where it
actually lands, proud of the engine line, rather than tucked away.

### 9.2 Mass, tracked against the bottom-up model

| group | CAD | model | delta |
|---|---|---|---|
| diffuser + tail cone + struts | 1.373 kg | 1.244 kg | +10.3 % |
| burn casing | 0.450 kg | 0.447 kg | +0.5 % |
| screech liner | 0.243 kg | 0.303 kg | −19.7 % |
| flameholder + struts | 0.455 kg | 0.339 kg | +34.1 % |
| spray bars + manifold | 0.144 kg | 0.147 kg | −2.4 % |
| igniter | 0.032 kg | 0.060 kg | −47.3 % |
| nozzle cowl + plug + struts | 0.712 kg | 0.649 kg | +9.7 % |
| actuation | 0.332 kg | 0.255 kg | +30.2 % |
| **drawn total** | **3.741 kg** | **3.446 kg** | **+8.5 %** |

Adding the allowances the CAD does not draw (AB fuel valve and lines 0.120, plug slide bearing
0.040, actuator linkage 0.060, AB fuel system 0.150, and flanges/fasteners at 10 % of the drawn
module 0.270) gives **4.380 kg against the model's 4.082 kg: +0.298 kg**.

**That pushes the aircraft over the ceiling.** With the CAD mass and its growth allowance, TOGW goes
**24.780 → 25.100 kg, i.e. 0.100 kg over 25 kg**. The recommended duct-Mach-0.30 / 10° build is
1.210 kg lighter in the module alone and would come out at about **23.804 kg (+1.196 kg margin)** on
the same drawing basis.

So the CAD does not change the conclusion of section 8, it sharpens it: **the conservative
7°-diffuser afterburner does not fit in the mass budget, and the shorter one does.**

### 9.3 What the CAD is not

Same convention as Phase 6 — provisional, shape only, not performance-validated:

* the diffuser wall and tail cone are straight cones at the angle the length calculation used; a
  real afterburner diffuser would be contoured, and the 7° limit is a separation criterion, not a
  contour;
* the screech liner is drawn with 25 mm-pitch, 2 mm-amplitude circumferential corrugations as a
  **drawing convention**. No acoustic liner design exists (R7.3), and no cooling holes are drawn —
  which is the part of this afterburner with the least analysis behind it;
* the V-gutters are 25 mm bluff bodies at the analysed blockage, not designed gutters;
* the actuation linkage is **schematic**: it shows the forward-mounted arrangement and its run
  length, but the bellcrank, pushrod buckling and thermal growth are not designed (R7.2);
* no thermal growth, no mounts, no assembly joints, no manufacturing features anywhere.

---

## 10. What Phase 7 makes worse, and the new open risks

### It makes three frozen risks worse

* **4.1 / 4.2 surge margin.** Every afterburner number here assumes the nozzle schedule holds the
  compressor still, and it does (R-line shift 9.9e-4). But that means **the afterburner's entire
  benefit rests on the variable nozzle working**, including on its transients. A nozzle that lags
  the afterburner light-up back-pressures the compressor exactly as the fixed-nozzle column in
  section 6.1 shows — surge margin 0.282 → 0.121 — into the region no approved tool can predict.
  **No light-up or shut-down transient was analysed.**
* **4.4 exducer / diffuser-vane resonance.** The afterburner adds a 1900 K heat-release zone and a
  bluff-body flameholder immediately downstream of the turbine. Afterburner **screech** (a
  high-frequency combustion instability) is a known excitation source, and nothing here checked
  what it does to the impeller modes already crossing at idle. **Not analysed.**
* **4.5 no hardware validation.** Unchanged, and now spanning more unvalidated physics.

### New open risks

| id | risk |
|---|---|
| **R7.1** | **Turbine exit annulus chokes at M 1.33** (5.8 % margin at the dash, falling with Mach), traced to the `turb.MN = 0.45` assumption in `arch_trade.turb_pout`. Pre-existing; not fixed. It is what caps the envelope, so the extension the afterburner was asked for is limited by the frozen engine, not by the afterburner. |
| **R7.2** | **No compliant nozzle actuator installation.** The plug's 123 N is within a sourced part, but the stroke is 2 % over its travel, it must be mounted forward with an undesigned pushrod, and no plug support, cooling or thermal-growth design exists. |
| **R7.3** | **Liner cooling unresolved.** Required film effectiveness 0.754 with 972 K as the only coolant. No cooling design, no liner temperature, no screech-liner acoustic design. |
| **R7.4** | **Airframe drag above M 1.05 is outside its model's stated validity**, and inlet spillage/additive drag is absent entirely. The M 1.3–1.4 dry top speed is a band, not a number. |
| **R7.5** | **Engine length +113 % is not carried into the airframe.** CG, tail arrangement, structure and boattail are unmodelled; the drag model cannot see the change. |
| **R7.6** | **Afterburner combustion efficiency assumed** (η_AB 0.90, A7.2) with no validation at 1.45 bar and this scale. Thrust is insensitive to it; **fuel is not** (TSFC 0.258–0.302 across η_AB 0.95–0.75), and fuel is what decides the 25 kg closure. |
| **R7.8** | **The nozzle actuator and its linkage do not fit inside the engine envelope** (+25.0 mm), and the 8.7 mm engine-to-fuselage-skin gap cannot take them either. Phase 6A's F6A.2 repeated. Both fixes — a local fairing or a longer remote linkage — touch the airframe cross-section the dash margin depends on, and neither is assessed. |
| **R7.7** | **Afterburner-on operation at M > 1.33 was computed but is not physically valid** — beyond the turbine-exit choke the cycle no longer represents the engine. The M 1.4–1.6 rows in section 5 are shown for the trend only. |

### Tool findings

* **F7.1** — pyCycle's `AIR_JETA_TAB_SPEC` FAR axis stops at **0.050** (stoichiometric Jet-A is
  0.068). It **extrapolates silently** rather than erroring. Tt7 ≈ 2000 K is the ceiling of the
  thermodynamic data, not a physical one; the chosen 1900 K sits 8 % inside it.
* **F7.2** — pyCycle's `Combustor` applies `dPqP` as a fixed fraction and does **not** model the
  Rayleigh loss of heat addition. Negligible in the main burner at MN 0.10; **2.7 % of Pt** in the
  afterburner at MN 0.20 with a temperature ratio near 2. Computed and handed to the element here.
* **F7.3** — `nDodecane_Reitz.yaml` ships two phases; the default `nDodecane_RK` (Redlich-Kwong) is
  **rejected by every reactor and flame object**. Use `nDodecane_IG`. `cantera_check.py` works only
  because `equilibrate()` accepts the RK phase.
* **F7.4** — the turbine-exit Mach inconsistency (section 7.1), the centrifugal counterpart of
  Phase 6A's F6A.5.
* **F7.5** — `nDodecane_Reitz.yaml` has **no gas-phase transport data for c12h26**, so no laminar
  flame speed can be solved with it.
* **F7.13** — the CAD corrects the length bookkeeping: the afterburner *replaces* the dry nozzle, so
  the engine grows by **457.9 mm**, not by the 483.5 mm module length the closure charged. The
  closure used the conservative figure.
* **F7.6** — a perfectly-stirred-reactor blowout search must use **continuation**, not bisection: a
  PSR is bistable, and bisecting from a freshly equilibrated initial state lands on the burning
  branch at every residence time and reports no blowout. Also, sharing one `Solution` object
  between the inlet reservoir and the reactor (`clone=False`) makes the "fresh" feed track the
  reactor and silently invalidates the result.

---

## 11. Decisions for the user

1. **Is the afterburner worth it for this aircraft?** It does not extend the envelope much — the
   dry engine already reaches M 1.31–1.42 and the turbine exit chokes at M 1.33. What it buys is
   thrust margin (+174 % vs +53 % at the dash) for +4.08 kg, +484 mm, and 2.9 × the fuel flow, on
   an airframe with 0.22 kg of mass margin left. **Keep, drop, or keep only as a study?**
2. **If kept: adopt the duct-Mach-0.30 build?** It is 180 mm shorter, 1.2 kg lighter, costs 4.8 % of
   the afterburner thrust, and on the CAD mass it closes at **23.8 kg** where the drawn 7° build is
   **25.1 kg, over the ceiling**. It needs the envelope and nozzle trade re-run on it.
3. **R7.8 — where does the nozzle actuator go?** It fits nowhere inside the current cross-section.
   A local fairing changes the wave drag the dash margin rests on; a remote linkage gets longer and
   more compliant. This has to be answered before the nozzle is believed, and the nozzle is what
   the whole afterburner benefit rests on.
4. **R7.1 — fix the turbine-exit inconsistency?** It caps the envelope at M 1.33 and it also affects
   the dry engine. Fixing `arch_trade.turb_pout` means re-designing the turbine, which re-opens
   Phase 3R/4R and the freeze.
5. **The freeze's own open decisions 1–5 are still unanswered**, and Phase 7 has made 4.1/4.2 and
   4.4 harder, not easier.

| | |
|---|---|
| Phase 7 reviewed | not yet |
| Date | |
