# Impeller stress gate: pure centrifugal, OPR 4, 85 000 rpm, fielded tip speed 537 m/s (2026-09-13)

> **Note (Phase 3R, 2026-09-14).** The solvers and criteria here are verified and are reused as a design constraint in
> `scripts/phase3_cycle/impeller_stress.py`. The impeller they were applied to came from TurboFlow with a defective slip
> model: its real tip speed for PR 4 would have been higher still. The Phase 3R impeller (`docs/phase3r_centrifugal.md`)
> is stress-sized at 105 % speed.

A fast decision gate run before Phase 4. The question: does the pure-centrifugal impeller pass a real stress check
at the fielded tip speed, where the Phase 3 solid-disc screening gave 526 MPa against a 450 MPa
conceptual allowable? This is not a redesign. The impeller geometry is the Phase 3 TurboFlow design
scaled to the fielded tip speed, and only the hub back-face shape and the blade root thickness are varied.

## Verdict

**The impeller as designed does NOT pass.**

| part | result at 537 m/s | criterion | status |
|---|---|---|---|
| disc / hub, through-bore (12 mm shaft) | best 529 MPa von Mises peak (bore); 580-601 MPa with the thermal gradient | Fty 620 MPa (minimum) | passes, yield margin +18 % mechanical, **+3.5 to +7 %** with thermal |
| disc / hub, boreless (stub shaft on the back face) | best 304 MPa; 319-326 MPa with thermal | Fty 620 MPa | passes, **+90 %** |
| disc burst (both attachments) | N_burst / N = 1.71 (bored), 1.92 (boreless) | >= 1.20 (14 CFR 33.27) | **passes** |
| **exducer blade root (30 deg backsweep)** | **656 MPa at a 3.5 mm root, 1016 MPa at 2.5 mm** (with the fillet factor) | Fty 620 MPa | **fails** at any aerodynamically acceptable root thickness |
| inducer blade root (tension) | 220 MPa | Fty 620 MPa | passes |

The disc is not the problem. With a boreless hub it carries the load with large margin. The
failure is in the backswept exducer blades. At 537 m/s the centrifugal force on a blade that
leans 30 deg away from radial bends it about its hub root. The root reaches the 620 MPa minimum yield
only at about 3.7 mm or more, which blocks 23 % of the exit flow area at the hub (about 14 % averaged
over the span). That has no margin left; 5 mm gives 421 MPa and blocks 32 % / 18 %. The Phase 3 aero
design assumed 5 %. *(Corrected 2026-09-14: the first version said "5 mm or more", which was simply
the next computed point; the interpolated threshold is 3.7 mm. The verdict does not change.)*

Per the gate instruction, the programme therefore proceeds on the pure axial (OPR 5), which was
recommended in Phase 3 and committed in b40812b.

**What this does not prove:** that a centrifugal impeller for this engine is impossible. Industrial
titanium impellers run at these tip speeds with backswept blades. The stress checks below show two
levers that would likely close it. Neither has been evaluated aerodynamically here, so neither
counts as a pass:
* **Less backsweep.** At 20 deg the 3.5 mm root falls to 444 MPa (+40 % margin); at 10 deg a 2.5 mm
  root gives 348 MPa. Less backsweep changes the stage's work, efficiency and stability, and would
  need a new TurboFlow design and a new cycle point.
* **Backsweep concentrated near the tip.** Starting the backsweep at 85 % of the tip radius
  instead of 70 % drops the 3.5 mm root to 517 MPa (+20 %).
* Blade rake or lean at the exit, which real impellers use to balance this bending, needs a 3D
  blade model and 3D FE. No approved tool here supports it.

## 1. Method

Script: `scripts/phase4_turbomachinery/impeller_stress_gate.py` (about 7 s); supplementary thermal
and backsweep cases in `impeller_gate_extras.py`. Results: `data/phase4_impeller_stress_gate.json`,
`data/phase4_impeller_gate_extras.json`.

**Tool: scikit-fem 12.0.2** (BSD-3, pure-Python FE assembly). Two solvers were built on it:
* `axisym_fe.py`: axisymmetric linear-elastic rotating-body FE on quadratic (P2) triangles. It
  handles centrifugal body force, surface tractions and a thermal strain field.
* A Kirchhoff plate FE on Morley elements for one exducer blade.

**Verification before use** (`verify_axisym_fe.py` and the verification block in the gate script):

| case | FE | closed form | error |
|---|---|---|---|
| rotating solid disc, hoop stress at centre | 18.496 MPa | 18.495 MPa (Timoshenko & Goodier sec. 32) | +0.00 % |
| rotating solid disc, hoop stress at rim | 7.335 | 7.310 | +0.35 % |
| rotating disc with bore a = 0.2 b, hoop stress at bore | 37.12 | 37.28 | -0.44 % |
| thin disc, parabolic temperature, hoop at centre / rim | 24.745 / -49.33 | 24.750 / -49.50 (Timoshenko & Goodier sec. 150) | -0.02 / -0.35 % |
| uniform clamped plate strip, uniform load, root bending | +5 % over cantilever theory 3 q b^2 / t^2 | | conservative |

**Geometry** (Phase 3 centrifugal, scaled to the fielded tip speed at 85 000 rpm):

| quantity | value |
|---|---|
| tip radius r2 | 60.3 mm |
| exit blade height b2 | 11.4 mm (b2 / r2 = 0.189) |
| inducer shroud / hub radius | 48.8 / 17.1 mm |
| axial length | 39.2 mm |
| blades | 12 main + 12 splitters (from mid-meridian), mean thickness 1.2 mm |
| exit blade angle | -30 deg (backswept) |

Hub and shroud lines are quarter ellipses. The back face is shaped as
z_back(r) = L + t_rim + A ((r2 - r)/(r2 - r_bore))^p, i.e. a boss thickening towards the bore. The
sweep covers t_rim 3 / 4.5 mm, A 0-18 mm, p 1 / 2, and two shaft attachments: a 6 mm-radius
through-bore for a tie-bolt or shaft, and a boreless hub with a stub shaft.

**Loads.** Centrifugal body force at 85 000 rpm. The blades' centrifugal pull is applied as radial
traction on the hub surface. Blade hoop stiffness is ignored, which is conservative for the hub.
Thermal case: metal temperature equals the local air total temperature, from 309 K at the eye
(dash inlet total temperature) to 520 K at the exit (fielded dash cycle). The field is
dT = 211 K (r/r2)^n with n = 1 and 2 as bounding shapes.

**Material: Ti-6Al-4V annealed, at about 250 C.**
* The ATI Grade 5 technical data sheet (2012) gives typical values at 480 F of Fty ~100 ksi and
  Ftu ~111 ksi, with E ~14.2 Msi (98 GPa) and a mean CTE of ~5.1e-6 /F (9.2e-6 /K).
* These are reduced to a minimum basis with the AMS 4928 room-temperature minimum/typical ratios
  (120/133 and 130/146): **Fty 620 MPa, Ftu 681 MPa**.
* Density 4430 kg/m3, Poisson's ratio 0.34. The alloy's service limit is about 350 C (Carpenter
  data sheet), and the exit air is at 247 C.

**Criteria.**
* Yield: peak von Mises stress below the minimum Fty.
* Burst: the average-tangential-stress (Robinson) criterion N_burst / N = sqrt(k Ftu / sigma_t,avg)
  with k = 0.85 must be at least 1.20. 14 CFR 33.27 requires no burst for 5 min at 120 % of the
  maximum permissible speed.
* Blade root: the stress at the blade/hub fillet with Kt 1.4 (Peterson's stepped-bar range for a
  generous fillet) must be below Fty.

**Blade model.** One exducer blade from 0.7 r2 to r2 is modelled as a Kirchhoff plate in the
meridional plane, clamped along the hub, which is conservative because it treats the hub as
rigid. Thickness tapers linearly from t_root to 0.8 mm at the shroud edge. The load is the
component of the blade's own centrifugal force normal to the blade, q = rho t(z) omega^2 r
sin(beta(r)). The blade angle beta rises linearly from 0 at 0.7 r2 to 30 deg at r2. Gas bending is
neglected because the blade pressure difference (~0.1 MPa) is about 0.3 % of this load.

## 2. Hub / disc results

Mechanical load only. Units are mm, MPa and kg. Mass includes the blades.

| r_bore | t_rim | A | p | von Mises peak | bore hoop | avg hoop | mass | yield margin | N_burst / N |
|---|---|---|---|---|---|---|---|---|---|
| 6 | 3.0 | 0 | 1 | 828 | 827 | 207 | 0.69 | -25 % | 1.67 |
| 6 | 3.0 | 6 | 1 | 701 | 698 | 215 | 0.80 | -11 % | 1.64 |
| 6 | 3.0 | 6 | 2 | 618 | 589 | 204 | 0.75 | +1 % | 1.69 |
| 6 | 3.0 | 12 | 1 | 611 | 572 | 221 | 0.91 | +2 % | 1.62 |
| 6 | 3.0 | 12 | 2 | 547 | 493 | 201 | 0.81 | +14 % | 1.70 |
| 6 | 3.0 | 18 | 1 | 598 | 546 | 226 | 1.02 | +4 % | 1.60 |
| **6** | **3.0** | **18** | **2** | **529** | 472 | 199 | 0.87 | **+18 %** | **1.71** |
| 6 | 4.5 | 0 | 1 | 920 | 919 | 228 | 0.76 | -32 % | 1.59 |
| 6 | 4.5 | 12 | 2 | 597 | 538 | 219 | 0.88 | +4 % | 1.63 |
| 6 | 4.5 | 18 | 2 | 574 | 512 | 215 | 0.94 | +8 % | 1.64 |
| 0 | 3.0 | 0 | 1 | 433 | 397 | 165 | 0.71 | +44 % | 1.87 |
| 0 | 3.0 | 12 | 2 | 317 | 279 | 159 | 0.81 | +96 % | 1.91 |
| **0** | **3.0** | **18** | **2** | **304** | 260 | 156 | 0.86 | **+105 %** | **1.92** |
| 0 | 4.5 | 18 | 2 | 333 | 283 | 171 | 0.94 | +87 % | 1.84 |

The full 28-case sweep is in the JSON file. A flat back face with a bore fails, reaching 828-920
MPa at the bore. This is the familiar factor-of-two hoop-stress concentration at a small hole in a
rotating disc. Thickening the hub towards the bore brings the peak down to 529 MPa, which is the
~530 MPa the Phase 3 screening asked about. It passes with an 18 % yield margin on the minimum
strength. A thicker rim only adds load and makes things worse.

With the thermal gradient (the rim hot, the bore cold) the bore hoop stress rises by 30-70 MPa:

| hub | mechanical | + thermal, linear | + thermal, quadratic | yield margin, worst |
|---|---|---|---|---|
| bored, A 18, p 2 | 529 | 601 | 580 | **+3.5 %** |
| bored, A 12, p 2 | 547 | 614 | 594 | +1.3 % |
| boreless, A 18, p 2 | 304 | 319 | 326 | +90 % |
| boreless, A 12, p 2 | 317 | 332 | 337 | +84 % |

**Conclusion for the disc:** the through-bore hub is only marginal once the thermal gradient is
included. The boreless hub passes with large margin at about the same mass (0.86 kg with blades),
with burst ratios of 1.8-1.9 against a requirement of 1.2. **The disc passes, provided it is boreless.**

## 3. Blade results

Exducer blade root, 30 deg backsweep, 537 m/s, stress with Kt 1.4:

| root thickness | root stress | root blockage (24 blades) | span-mean blockage |
|---|---|---|---|
| 1.5 mm | 2064 MPa | 9.5 % | 7.3 % |
| 2.5 mm | 1016 MPa | 15.8 % | 10.4 % |
| 3.5 mm | 656 MPa | 22 % | 13.6 % |
| 5 mm | 421 MPa | 32 % | 18 % |
| 7 mm | 283 MPa | 44 % | 24 % |

The largest plate deflection is 0.14 mm at a 3.5 mm root, against a tip clearance of 0.25 mm.

Sensitivity (not a design, and the aerodynamic side is not evaluated):

| exit backsweep | root 2.5 mm | root 3.5 mm |
|---|---|---|
| 10 deg | 348 MPa | 224 MPa |
| 20 deg | 689 MPa | 444 MPa |
| 30 deg (design) | 1016 MPa | 656 MPa |
| 40 deg | 1324 MPa | 854 MPa |

Where the backsweep begins, at a 3.5 mm root and 30 deg: from 0.5 r2 gives 798 MPa, from 0.7 r2
(the base case) 656 MPa, and from 0.85 r2 517 MPa.

The root bending stress scales as rho omega^2 r sin(beta2) b2^2 / t. The load is set by the tip
speed and the backsweep, and it is resisted only by the root thickness. A blade 1.2 mm thick on
average, as assumed in the Phase 3 aero design, is about three times too thin at the root for 30
deg of backsweep at 537 m/s.

Inducer blade root, in radial tension with a taper factor of 0.6: 220 MPa, which passes.

## 4. Conservatisms and gaps

**Conservative:**
* The rigid-hub clamp on the blade.
* Blade hoop stiffness ignored in the hub model.
* The blade treated as a flat plate with a free inner edge at 0.7 r2. The real blade continues
  inward and is stiffer.

**Non-conservative or not modelled:**
* No fillet detail in the disc model. The bore peak sits on a smooth surface.
* No low-cycle fatigue. Two flights a day is a low cycle count, but the mission profile adds
  start-stop cycles.
* No blade vibration or Campbell diagram.
* No creep. At 247 C this is negligible for Ti-6Al-4V.
* The 3D blade shape, including rake and lean, is not modelled.

**Material basis:** a typical data-sheet curve scaled to a minimum basis. It is not MMPDS A- or
B-basis design data.

## 5. Effect on the programme

* The Phase 3 recommendation stands: the **pure axial, 5 stages, OPR 5, 65 000 rpm, capped
  turbine**. Phase 4 starts there, with low-speed operability and stall, then shaft dynamics.
* The pure centrifugal drops from third to "not qualified as designed". Reviving it would take a
  redesigned exducer: about 20 deg of backsweep, or backsweep confined to the outer 15 % of the
  radius, with a boreless hub. That needs a new TurboFlow design, cycle point and thrust margin,
  and a 3D FE check. It is the user's call whether that is worth doing. The margin it would have
  to preserve is +44 % pessimistic.
* The axial-centrifugal (2 axial + cc, OPR 4) stays the stress-safe fallback. Its impeller at 394
  m/s is 27 % slower, so its blade bending, which scales with U^2, should fall by roughly half (not computed).
