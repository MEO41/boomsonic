# Phase 3 — Engine cycle and architecture trade (2026-09-13)

Scripts: `scripts/phase3_cycle/` (list in section 12). The Phase 2 catalog-fit engine (6.83 kg,
188 mm) is **not** used anywhere in this phase: every engine mass and diameter below comes from
a designed geometry and its materials.

**Answer to the margin question (fielded efficiency, the realistic case): the 25 % dash thrust
margin holds for both architectures, in both drag cases.** Recommended: the 5-stage axial at
OPR 5 (section 8). The centrifugal also passes, but its pass is conditional on impeller stress.

**Phase 3b (section 13): axial-centrifugal (1-2 axial stages + 1 centrifugal).** It closes the
impeller-stress problem (fielded stress factor 1.06-1.58 vs 0.86), but it is not shorter than the
5-stage axial (632-704 vs 663 mm) and it is the heaviest option (8.7-9.5 kg vs 6.6 / 7.3 kg). Its
best variant (2 axial stages, OPR 4) gives +75 % / +51 % margin, between the two pure options; two
of its four variants fail the 25 % pessimistic target. It relocates the risk rather than removing
it. The recommendation is unchanged; the best AC variant becomes the second choice, ahead of the
pure centrifugal unless the impeller is qualified at ~530 MPa.

## 1. Tools: what was used for what, and what did not work

| Job | Tool | Why this tool | Verification / finding |
|---|---|---|---|
| cycle, on-design and off-design | NASA pyCycle (TABULAR air/Jet-A, CEA-derived) | only surveyed cycle tool with real-gas equilibrium thermo and off-design balances | Cantera cross-check at the combustor exit |
| gas properties at combustor / turbine entry | Cantera 3.2 (n-dodecane surrogate, 100 species) | independent equilibrium chemistry | T4 within 3.3 K (0.3 %), gamma within 0.0002, cp within 0.6 % of pyCycle |
| centrifugal compressor efficiency and geometry | TurboFlow 0.1.18 (Oh loss set, Wiesner slip, throat choke check) | needs ~15 conceptual geometry inputs a meanline pre-sizing can supply. NASA turbo-design's centrifugal module (validated on HECC in Phase 0) needs measured blade-coordinate quantities (throat areas, camber lengths, TE blockage) that do not exist for a new design | converges; a choked inducer throat is detected and removed by opening the throat |
| axial compressor efficiency | **none of the approved tools can** | turbo-design: `lieblein.py` is an empty file, the OTAC loss classes are documented placeholders returning zero, `DiffusionLoss` is an ad-hoc ramp whose diffusion factor omits solidity. TurboDesigner takes efficiency as an INPUT. TurboFlow has no axial compressor | next-best method: TurboDesigner geometry and velocity triangles + the Howell cascade method (Saravanamuttoo et al., *Gas Turbine Theory*, ch. 5) with explicit Reynolds, tip-clearance (Freeman) and transonic-shock penalties. Verified: row efficiency 0.90-0.92 at conventional scale, as in the textbook |
| axial compressor geometry | TurboDesigner 2.0.0 | free-vortex stage-by-stage triangles, blade counts, chords, radii | **bug:** its rotor diffusion factor uses absolute velocities (0.03 at mid-span vs the matched stator's 0.40 in a 50 %-reaction stage) -> recomputed from relative triangles. The last stator's `next_flow_station` raises an assertion |
| axial turbine (both architectures) | TurboFlow design optimisation (Benner losses) | only approved tool that designs a turbine to a flow and work target | **two defects in use:** (1) the optimiser derives omega from its specific-speed variable and ignores the operating-point omega (asked for 85 000 rpm, got 104 000) -> omega imposed as an equality constraint; (2) no structural constraint: the unconstrained optimum had a 77 mm tip at 85 000 rpm, 688 m/s tip speed, ~716 MPa blade-root stress -> a 350 MPa blade-root limit (cast IN-713LC) imposed as a tip-radius constraint |
| combustor size | Lefebvre theta-parameter scaling | theta's efficiency curve is combustor-type specific (Cranfield GT Combustion notes, slide 7), so it is calibrated on 7 existing micro-turbojets and held equal | theta_ref geometric mean 7.2e7, log-scatter 20 % |
| engine mass | own bottom-up model (materials, stress-sized Stodola discs, component geometry) | no tool estimates engine mass | validated against JetCat P400-PRO and AMT Nike (section 9) |

## 2. What real engines of this class achieve (catalog data used to calibrate efficiency, not mass)

`vendor_calibration.py`: fitting published airflow, pressure ratio, thrust AND fuel flow of six
engines at once requires T4 1330-1450 K and turbine exhaust 1180-1300 K, which is 150-275 K above
the manufacturers' own EGT limits, with turbine efficiencies of only 0.60-0.77. The published
airflows are therefore nominal and cannot calibrate component efficiency.

The robust observable is SLS TSFC, since thrust and fuel flow are both test-stand measurements:
**0.145-0.167 kg/(N h)** for P220, P300, P400, Olympus HP, Titan and Nike.
`tsfc_anchor.py`: at PR 3.8 and T4 1150-1250 K, that band requires **eta_c ~0.66-0.70 with
eta_t ~0.70-0.75** (eta_b 0.90-0.95). The Phase 1 placeholder cycle (0.78 / 0.85, eta_b 1.0)
gave 0.110 kg/(N h), about 40 % better than any fielded engine. The tools used here predict
eta_c ~0.79 and eta_t ~0.93, which also beat the fielded band by a wide margin.

Every result is therefore given at two technology levels:
* **tool**: component efficiencies as predicted by TurboFlow / the Howell model (optimistic bound)
* **fielded**: eta_c 0.70 (centrifugal), eta_t 0.75, eta_b 0.95, the level that reproduces the
  measured TSFC of commercial engines (realistic design case). The axial compressor's fielded
  value applies the same ratio (0.70 / 0.794 = 0.882) to its tool efficiency, because no
  micro-scale axial compressor has published test data (assumption A3.4).

## 3. Cycle definition at the dash (D3.1)

Fn 500 N at M 1.02 / 5000 m ISA (the Phase 2 drag design point), convergent nozzle, T4 1150 K
carried from D1.1, OPR traded (section 4), burner dP/P 0.05, eta_b 0.95, nozzle Cv 0.98.

The intake is now inside the cycle and replaces the 3 % flat installation loss A2.3: normal
shock at M 1.02 (recovery 0.99998) plus a 1.32 m subsonic duct with friction 2.9 % (Haaland,
Re_D 9e5, f 0.0117) and diffusion 0.4 % (Idelchik Borda-Carnot form) = **3.3-3.4 %
total-pressure loss**.

## 4. Cycle-parameter trade (OPR, T4, nozzle) — `cycle_trade.py`, `plots/phase3_cycle_trade.png`

Airflow for Fn 500 N at the dash (kg/s) / theta-scaled combustor OD (mm):

| level | T4 | OPR 3 | OPR 4 | OPR 5 | OPR 6 |
|---|---|---|---|---|---|
| tool | 1150 K | 1.115 / 208 | 1.088 / 163 | 1.086 / 136 | 1.093 / 117 |
| fielded | 1150 K | 1.305 / 215 | 1.326 / 170 | 1.384 / 143 | 1.470 / 125 |
| fielded | 1250 K | 1.133 / 205 | 1.131 / 161 | 1.153 / 134 | 1.184 / 116 |

* **F3.3 The combustor, not the compressor, sets the engine diameter at OPR 4**, and its size
  falls steeply with pressure ratio (theta ~ P3^1.75 exp(T3/300)). Pressure ratio is therefore a
  diameter lever, and the architecture decides how much pressure ratio is affordable.
* A convergent-divergent nozzle gains 2 % (tool) / 0.2 % (fielded) at NPR 2.8-3.7: **convergent
  nozzle kept** (D3.2).
* T4 kept at 1150 K (D1.1). 1250 K is a documented lever (-15 % airflow) that needs turbine
  material and life data first (its exhaust temperature, 1076 K, exceeds most vendor EGT limits).

## 5. Combustor sizing

theta = P3^1.75 A_ref D_ref^0.75 exp(T3/300) / m_dot, calibrated on P220, P300, P400, Olympus HP,
Titan, Nike and TJ40 at SLS max (casing annulus as A_ref, annulus height as D_ref, Ri = 0.25 Ro):
geometric mean 7.24e7, log-sigma 0.20, back-calculated reference velocities 14-19 m/s.
At the dash, OPR 4, T4 1150 K the combustor casing OD is 163-170 mm (+1 sigma: 175-183 mm).

## 6. Component designs

### Centrifugal option (single stage, OPR 4, 85 000 rpm) — TurboFlow

Spool-speed trade at W 1.134 kg/s, PR 4 (`centrifugal_sweep.py`):

| rpm | eta_tt | inducer shroud M_rel | U2 | impeller D2 | diffuser OD (R4/R2 1.35) |
|---|---|---|---|---|---|
| 65 000 | 0.835 | 1.08 | 487 m/s | 143 mm | 193 mm |
| 75 000 | 0.813 | 1.21 | 495 | 126 | 170 |
| 85 000 | 0.790 | 1.34 | 505 | 114 | 153 |
| 95 000 | 0.763 | 1.47 | 518 | 104 | 140 |

R4/R2 1.45 instead of 1.35 changes efficiency by 0.0003, so 1.35 is used. 75 000 rpm was also
carried through the full system evaluation and lost: diffuser-set OD 176-195 mm and 18 % fielded
pessimistic margin.

Final design (converged with the cycle): **1 stage, eta_tt 0.794 (tool), Ti-6Al-4V impeller,
12 blades, backsweep -30 deg, U2 504 m/s, D2 113 mm, inducer tip 88 mm, b2 10.7 mm, vaned
diffuser OD 153 mm, diffuser exit M 0.21.** Turbine (TurboFlow, stress-limited): 1 stage,
eta_tt 0.935, tip radius 53.9 mm (the blade-root stress limit at 85 000 rpm), 33 NGV / 28 rotor
blades, blade height 20-22 mm.

### Axial option (5 stages, OPR 5, 65 000 rpm, turbine inside the casing) — TurboDesigner + Howell model

The design space is swept at every cycle point (`axial_design.py`, ~290 designs: 40-65 k rpm,
4-7 stages, hub/tip 0.40-0.55, Cx 170-200 m/s) with limits DF <= 0.50, de Haller >= 0.72,
first-rotor tip M_rel <= 1.35, last blade >= 10 mm; the most efficient feasible design is kept.

Final: **5 stages, 253 blades, eta_is 0.841 (tool; stage eta 0.862-0.880), hub/tip 0.40,
Cx 200 m/s, U_tip 438 m/s, first-rotor tip M_rel 1.27, max DF 0.47, casing 134 mm, blades
39 -> 14 mm tall, chords 26 -> 10 mm, Re_c 2.0-2.9e5, clearance penalty 1.3-3.4 points per
stage.** Turbine: 1 stage, eta_tt 0.925, tip 65.9 mm (capped at the compressor/combustor
envelope; the stress limit would allow 70.5 mm), 31 NGV / 30 rotor blades.

Without the envelope cap the turbine optimiser pushes the tip to its stress limit and the turbine
sets the engine diameter (+9 to +10 mm). The cap costs only 0.009 in turbine efficiency.

Other cases run through the full chain (all in `data/phase3_arch_trade_summary.csv`): axial OPR 4
(55 k rpm, 5 stages), axial OPR 6 (55 k rpm, 7 stages, capped and uncapped), and centrifugal
OPR 5 (needs U2 548 m/s, i.e. 548 MPa solid-disc stress in Ti, over the 450 MPa allowable).

## 7. Side-by-side results (dash M 1.02 / 5 km, Fn 500 N, T4 1150 K) — `plots/phase3_arch_trade.png`

Engine mass = bottom-up x 1.24 validation calibration (section 9). TOGW includes accessories
1.60 kg, re-evaluated airframe + systems + 15 % growth, and sortie fuel.

| | Centrifugal OPR 4, 85k — tool | Centrifugal — **fielded** | Axial OPR 5, 65k — tool | Axial — **fielded** |
|---|---|---|---|---|
| compressor stages | 1 (impeller) | 1 | 5 (253 blades) | 5 |
| eta_c / eta_t | 0.794 / 0.935 | 0.70 / 0.75 | 0.841 / 0.925 | 0.741 / 0.75 |
| airflow | 1.084 kg/s | 1.326 kg/s | 1.052 kg/s | 1.293 kg/s |
| TSFC at the dash | 0.139 kg/(N h) | 0.164 | 0.130 | 0.153 |
| diameter set by | combustor | compressor diffuser | combustor / turbine | turbine / compressor |
| **engine outer diameter** | **163 mm** | **175 mm** | **136 mm** | **151 mm** |
| (combustor +1 sigma) | 175 mm | 183 mm | 147 mm | 152 mm |
| engine length (calibrated) | 444 mm | 474 mm | 615 mm | 663 mm |
| **engine dry mass, calibrated** (range) | **5.52 kg** (5.17-5.84) | **6.57 kg** (6.15-6.94) | **5.96 kg** (5.58-6.30) | **7.28 kg** (6.81-7.69) |
| bottom-up (uncalibrated) | 4.46 | 5.30 | 4.81 | 5.87 |
| dash drag area nominal / pessimistic | 69.3 / 79.3 cm2 | 75.2 / 88.3 | 60.7 / 64.5 | 64.1 / 71.6 |
| dash drag nominal / pessimistic | 273 / 313 N | 296 / 348 N | 240 / 254 N | 253 / 282 N |
| **thrust margin, nominal drag** | **+83 %** | **+69 %** | **+109 %** | **+98 %** |
| **thrust margin, pessimistic drag** | **+60 %** | **+44 %** | **+97 %** | **+77 %** |
| 25 % target holds? | yes / yes | yes / yes | yes / yes | yes / yes |
| TOGW (calibrated engine) | 17.1 kg | 18.6 kg | 17.2 kg | 18.9 kg |
| margin to 25 kg | 7.9 kg | 6.4 kg | 7.8 kg | 6.1 kg |

Drag is recomputed with the full Phase 2 airframe model (friction/form + area-rule wave drag) for
each engine's real diameter, not with the linear 20-30 N per 10 mm rule. The two agree: the
model gives 23-34 N per 10 mm here.

**Robustness (`efficiency_sensitivity.py`, fielded, eta_t 0.75, both compressors at the SAME efficiency):**

| eta_c | combustor | centrifugal: OD / margin nom / pess / TOGW | axial: OD / margin nom / pess / TOGW |
|---|---|---|---|
| 0.66 | +1 sigma | 184 mm / 58 % / **32 %** / 19.4 kg | 162 mm / 84 % / **61 %** / 20.8 kg |
| 0.70 | mean | 175 mm / 69 % / 44 % / 18.6 kg | 156 mm / 92 % / 70 % / 19.6 kg |
| 0.74 | mean | 171 mm / 74 % / 50 % / 18.2 kg | 151 mm / 97 % / 77 % / 19.0 kg |

The axial's margin lead does not depend on its (unvalidated) compressor efficiency advantage. It
comes from the higher pressure ratio shrinking the combustor, which only the axial reaches within
rotor stress limits.

**Impeller stress (centrifugal only):** at the same pressure ratio a less efficient impeller needs
more work, hence more tip speed: U2 504 m/s at eta 0.794 becomes 537 m/s at the fielded 0.70.
Solid-disc peak stress (3+nu)/8 rho U2^2 in Ti-6Al-4V rises from 464 to 526 MPa against the
450 MPa conceptual allowable (factor 0.97 -> 0.86). A shaped titanium impeller can carry this
(industrial Ti turbocharger wheels run 550+ m/s), but that is a Phase 4 finite-element item. If
the impeller had to stay at its tool-level tip speed, PR would fall to 3.48, the combustor would
grow to 190 mm and the **fielded pessimistic margin would drop to 24 %**, at rather than above the
target. The axial rotors are inside their allowables by construction: first-rotor blade root
~210 MPa, discs stress-sized at 450 MPa, turbine at the 350 MPa blade limit.

**Transonic acceleration:** with the centrifugal engine's own off-design deck (RPM-limited,
placeholder maps) the excess thrust at 5 km is +259 % at M 0.70 and +150 % at M 0.95. The
minimum is the dash point itself, so the acceleration is never the binding point.

## 8. Recommendation (D3.3): axial, 5 stages, OPR 5, 65 000 rpm, turbine inside the casing

Both architectures close the 25 % margin at both technology levels and both drag cases, so
neither is flagged back as failing. The axial is recommended because, on the numbers:
1. **Margin:** +98 % / +77 % (fielded, nominal / pessimistic) against +69 % / +44 %, and still
   +61 % in the worst corner tested (eta_c 0.66, combustor +1 sigma, E_WD 3.0) against +32 %.
2. **The centrifugal's pass is conditional; the axial's is not:** the centrifugal needs its
   impeller qualified ~17 % above the conceptual stress allowable. Held to its tool-level tip speed
   it falls to 24 % pessimistic margin. The axial exceeds no allowable.
3. **Diameter:** 151 mm against 175 mm (-24 mm), which is where the drag difference comes from.
4. **The mass cost is small against the budget:** +0.71 kg engine (calibrated), +0.3 kg TOGW
   (18.9 vs 18.6 kg; +1.0 kg if its compressor is no better than the centrifugal's). Both leave
   at least 5.4 kg under 25 kg.

What the axial costs, stated plainly (these are the reasons a reviewer could choose the
centrifugal instead):
* +190 mm engine length (663 vs 474 mm) and 5 bladed rotors with 253 blades down to 10 mm chord
  and 14 mm height, against one impeller: much harder to manufacture and balance.
* Its compressor efficiency comes from a textbook loss model with no micro-scale validation, and
  its fielded efficiency is an assumed debit (A3.4). The margin conclusion survives replacing it
  with the centrifugal's value (table above), but then its mass and length get worse.
* **Operability is not yet quantified:** a fixed-geometry 5-stage compressor at PR 5 is prone to
  front-stage stall at part speed (starting, idle, throttle transients). No approved tool gives
  axial-compressor maps, so Phase 4 would need to extend the in-house Howell model to off-design.
  If Phase 4 shows it needs variable stators or bleed, the mass and complexity case changes.
* No commercial turbojet below ~1 kN uses an all-axial compressor; every one in the database is
  centrifugal.

Fallback: the centrifugal OPR 4 / 85 000 rpm design, provided the Phase 4 impeller stress
analysis clears ~530 MPa at the fielded tip speed. Not evaluated but worth naming: an
axi-centrifugal compressor (1 axial stage + 1 centrifugal) is the classic small-engine route to
OPR 5-6 and would relieve the impeller tip speed. It was outside the requested two-way trade.

## 9. Mass-model validation — `validate_mass_model.py`

The same design chain was run at two real engines' published operating points (fielded
efficiencies, T4 solved for the published thrust):

| engine | predicted mass | published | error | predicted L | published | predicted D | published |
|---|---|---|---|---|---|---|---|
| JetCat P400-PRO (0.67 kg/s, PR 3.8, 98 000 rpm) | 3.45 kg | 4.01 kg (incl. ECU/pump) | -14 % | 319 mm | 390 mm | 145 mm | 148 mm |
| AMT Nike (1.25 kg/s, PR 4.0, 61 500 rpm) | 6.98 kg | 9.15 kg (engine only) | -24 % | 430 mm | 524 mm | 203 mm | 201 mm |

The bottom-up model misses flanges, casting thicknesses and details that real engines carry, so
masses are multiplied by **1.24 (range 1.16-1.31)** and lengths by **1.22**. Diameter is within
2 % (for the P400 partly by construction, since the combustor theta is calibrated on the same
set). Both architectures receive the same factor; the axial has no validation engine of its own.

## 10. Assumptions added in Phase 3

| id | assumption | status |
|---|---|---|
| A3.1 | fielded technology level: eta_c 0.70 (centrifugal), eta_t 0.75, eta_b 0.95, from the vendor-TSFC anchor | data-based |
| A3.2 | turbine blade-root stress limit 350 MPa (IN-713LC, ~780 C, taper factor 0.6); disc allowables Ti 450 / IN-713LC 300 MPa | conceptual; Phase 4 material data |
| A3.3 | combustor of the same type and efficiency as the reference engines (equal theta), Ri = 0.25 Ro, liner length 3 x annulus height | +-1 sigma carried |
| A3.4 | axial fielded compressor efficiency = tool value x (0.70 / 0.794) | the sensitivity shows the conclusion does not depend on it |
| A3.5 | tip clearance 0.25 mm (compressors), 0.30 mm (turbine rotor); stators shrouded | Phase 4 |
| A3.6 | fielded-level geometry scaled from the tool design by sqrt(airflow ratio) at fixed rpm | approximation; conservative for the centrifugal diffuser (+4 %) |
| A3.7 | engine accessories 1.60 kg (Phase 2, AMT system data) unchanged | carried |
| A3.8 | off-design maps are pyCycle's scaled NPSS maps; the T4-limited off-design branch did not converge, and the RPM-limited branch exceeds T4max by up to 3.4 % at SLS | Phase 4 real maps |

## 11. Open items for Phase 4 (after approval)
1. Axial compressor off-design (Howell off-design loss and deviation), surge margin, start and idle.
2. Rotor dynamics of the ~0.66 m shaft at 65 000 rpm (critical speeds, bearing span).
3. Turbine material and life (IN-713LC data) and the 350 MPa blade limit.
4. Real compressor and turbine maps in pyCycle, replacing the placeholder NPSS maps; redo the mission.
5. CG and packaging of the longer engine in the 2.7 m fuselage.
6. If the centrifugal fallback is chosen: impeller FE stress at 537 m/s. **Done as the Phase 4 entry gate (`docs/phase4_impeller_stress_gate.md`): disc and burst pass (boreless hub), the 30 deg backswept exducer blade root fails; the centrifugal is not qualified as designed.**

## 12. Scripts
`dash_cycle.py` (cycle + intake), `cantera_check.py`, `vendor_calibration.py`, `tsfc_anchor.py`,
`cycle_trade.py`, `centrifugal_design.py` / `centrifugal_sweep.py` (TurboFlow), `axial_design.py` /
`axial_sweep.py`, `turbine_design.py` (TurboFlow, stress- and speed-constrained),
`combustor_sizing.py`, `engine_mass.py`, `arch_trade.py` (orchestrator; env P3_OPR, P3_CASES,
P3_TURB_CAP, P3_CC_REF), `reeval_level.py`, `validate_mass_model.py`, `efficiency_sensitivity.py`,
`engine_deck.py`, `pinch_check.py`, `compile_trade.py`; Phase 3b: `axicent_design.py` (screening: `screen W T01 P01 tag n_ax`), `axicent_sensitivity.py`, `arch_trade.py` kind `axicentrifugal:rpm:n_ax:pi_a` (env P3_OUT_SUFFIX).

## 13. Additional option (Phase 3b): axial-centrifugal compressor (1-2 axial stages + 1 centrifugal stage)

Evaluated before Phase 4, with the same tools and assumptions as the two Phase 3 options:
axial stages from TurboDesigner + the Howell loss model (`axial_design.py`), centrifugal stage
from TurboFlow with identical settings (Oh losses, Wiesner slip, beta2b -30 deg, Z 12, 0.25 mm
clearance, R4/R2 1.35), stress-limited and envelope-capped TurboFlow turbine, theta-scaled
combustor, bottom-up mass x 1.24 (the JetCat P400 / AMT Nike calibration), Phase 2 airframe drag,
and the same 450 MPa Ti-6Al-4V solid-disc impeller allowable. Single spool: the axial stages and
the impeller share one speed. Scripts: `axicent_design.py` (screening), `arch_trade.py`
(kind `axicentrifugal`), `axicent_sensitivity.py`.

**Caveat carried over unchanged:** every axial stage here uses the same textbook Howell cascade
method as the pure axial, verified only at conventional scale (row efficiency 0.90-0.92) and
never validated at micro scale. The front stage is the transonic one (tip relative Mach 1.30),
which is the most loss-sensitive part of any axial compressor. The fielded axial-stage efficiency
is the same assumed debit (x 0.882, A3.4). The transition duct from the axial exit to the impeller
eye is not loss-modelled, and the last axial stator is assumed to remove all swirl.

### 13.1 What limits the spool speed, and how much pressure ratio the impeller must carry

The first axial rotor must pass the full inlet flow (~1.06 kg/s). With the same limits as the pure
axial (tip relative Mach <= 1.35, hub/tip >= 0.40, DF <= 0.50, de Haller >= 0.72), it is feasible
only up to **70 000 rpm** (tip M_rel 1.33-1.34; infeasible from 72 000 rpm at 1.36). The trade uses
**68 000 rpm** to keep margin at the first-iteration airflow. So the impeller runs 20 % slower
than in the pure centrifugal (85 000 rpm).

Screening at W 1.08 kg/s (`data/phase3_axicent_screen_n1.csv`, `_n2.csv`; 65 000 rpm column shown,
75 000 and 85 000 rpm had no feasible front stage):

| front stages | axial PR | overall OPR | impeller PR | impeller U2 tool / fielded | Ti stress factor tool / fielded |
|---|---|---|---|---|---|
| 1 | 1.3 / 1.4 / 1.5 | 4.0 | 3.08 / 2.86 / 2.67 | 446 / 478 ... 421 / 452 m/s | 1.24 / 1.08 ... 1.39 / 1.20 |
| 1 | 1.5 | 4.5 | 3.00 | 448 / 481 | 1.23 / 1.07 |
| 1 | 1.3-1.5 | 5.0 | 3.85-3.33 | 494-471 / 529-506 | 1.01-1.11 / **0.88-0.96** |
| 2 | 1.6 / 1.8 / 2.0 | 4.0 | 2.50 / 2.22 / 2.00 | 410 / 441 ... 364 / 393 | 1.46 / 1.27 ... 1.86 / 1.60 |
| 2 | 2.0 | 5.0 | 2.50 | 421 / 454 | 1.39 / 1.19 |
| pure centrifugal (Phase 3) | - | 4.0 | 4.00 | 504 / 537 (85 000 rpm) | 0.97 / **0.86** |

The centrifugal stage has to carry a pressure ratio of 2.0-3.3 instead of 4.0. Its tip speed falls
by 15-27 %, and the fielded stress factor rises from 0.86 to 1.06-1.60. One front stage clears the
allowable up to OPR ~4.5; two front stages clear it comfortably at OPR 4 and with 19 % margin at
OPR 5. **The impeller-stress problem is closed.**

The catch: the impeller now runs at 68 000 rpm instead of 85 000. For a given tip speed its radius
is 25 % larger, and the vaned diffuser grows with it. In three of the four variants the
diffuser, not the combustor, becomes the largest diameter.

### 13.2 Full comparison (dash M 1.02 / 5 km, Fn 500 N, T4 1150 K; same method as section 7)

Fielded technology level (the realistic case); tool-level values in `data/phase3_arch_trade_summary.csv`.

| | Centrifugal, OPR 4, 85k (Phase 3) | Axial 5-stage, OPR 5, 65k (Phase 3) | **AC 1 axial + cc, OPR 4, 68k** | AC 1 axial + cc, OPR 4.5, 68k | **AC 2 axial + cc, OPR 4, 68k** | AC 2 axial + cc, OPR 5, 68k |
|---|---|---|---|---|---|---|
| axial PR / impeller PR | - / 4.0 | 5.0 / - | 1.5 / 2.67 | 1.5 / 3.0 | 2.0 / 2.0 | 2.0 / 2.5 |
| overall eta_c (fielded) | 0.700 | 0.741 | 0.725 | 0.728 | 0.721 | 0.726 |
| airflow | 1.326 kg/s | 1.293 | 1.282 | 1.294 | 1.289 | 1.323 |
| impeller U2 / Ti stress factor | 537 m/s / **0.86** | none (no impeller) | 454 / 1.20 | 482 / 1.06 | 394 / 1.58 | 456 / 1.19 |
| diameter set by | diffuser | turbine / compressor | diffuser | diffuser | combustor | diffuser |
| **engine outer diameter** | **175 mm** | **151 mm** | **182 mm** | 195 mm | **169 mm** | 185 mm |
| **engine length (calibrated)** | **474 mm** | **663 mm** | **641 mm** | 632 mm | **704 mm** | 680 mm |
| **engine dry mass, calibrated** (range) | **6.57 kg** (6.15-6.94) | **7.28 kg** (6.81-7.69) | **8.73 kg** (8.17-9.23) | 9.17 kg | **8.90 kg** (8.33-9.40) | 9.51 kg |
| dash drag nominal / pessimistic | 296 / 348 N | 253 / 282 N | 312 / 373 N | 344 / 422 N | 285 / 331 N | 320 / 385 N |
| **thrust margin nominal / pessimistic** | **+69 % / +44 %** | **+98 % / +77 %** | **+60 % / +34 %** | +45 % / **+19 %** | **+75 % / +51 %** | +56 % / +30 % |
| worst corner (eta_c 0.66, combustor +1 sigma, E_WD 3) | +32 % | +61 % | **+23 %** | not run | +32 % | **+15 %** |
| TOGW (calibrated engine) | 18.6 kg | 18.9 kg | 20.8 kg | 21.3 kg | 20.8 kg | 21.5 kg |

Tool level (same order): margin pessimistic +60 / +97 / +56 / +42 / +59 / +56 %, engine OD 163 /
136 / 166 / 176 / 163 / 166 mm, calibrated mass 5.52 / 5.96 / 7.19 / 7.40 / 7.37 / 7.42 kg.

Why the axial-centrifugal is the heaviest option: it carries the axial front stages (blades,
discs, casing) and a full impeller, diffuser and shroud. The turbine at 68 000 rpm needs a larger,
heavier disc than at 85 000 rpm (0.69 vs 0.36 kg), and the shaft is longer (0.49 vs 0.33 kg). Its
247 mm compressor section is as long as the 5-stage axial's (249 mm), and the OPR-4 variants
also carry the longer OPR-4 combustor.

Robustness of the best variant (2 axial + cc, OPR 4), equal fielded compressor efficiency
(`data/phase3_axicent_sensitivity.csv`): pessimistic margin +49 / +51 / +52 % at eta_c 0.66 / 0.70 /
0.74 with the mean combustor, and +32 / +34 / +35 % with the +1 sigma combustor. That matches the
pure centrifugal (+32 / +34 %) because both then have the same combustor-set diameter (182-184 mm).
The impeller stress factor stays at 1.47-1.65.

A shared limitation of both axial-bearing options: the fielded-level geometry is scaled from the
tool design by sqrt(airflow ratio) at fixed speed (A3.6). For the axial stages that raises the
first-rotor tip relative Mach from ~1.30 to ~1.38, above the 1.35 limit. A true fielded redesign
would need a slightly lower speed (a larger impeller for the AC, a slightly larger compressor
for the pure axial). The comparison is like-for-like, but both axial-bearing options are slightly
flattered at the fielded level.

### 13.3 Verdict: it closes the impeller-stress problem, but it relocates the risk rather than removing it

* **Stress: closed.** Every axial-centrifugal variant keeps the Ti impeller inside the allowable at
  the fielded level (factor 1.06-1.58, against 0.86 for the pure centrifugal).
* **Length: not shorter than the 5-stage axial.** Calibrated length 632-704 mm against 663 mm for
  the pure axial and 474 mm for the pure centrifugal. The front axial stage caps the shaft at
  ~70 000 rpm, so the impeller, diffuser and turbine disc grow, and the OPR-4 combustor is long.
* **Mass: the heaviest of all options.** 8.7-9.5 kg calibrated engine (+2.2 to +2.9 kg over the
  pure centrifugal, +1.4 to +2.2 kg over the pure axial). TOGW 20.8-21.5 kg, still 3.5-4.2 kg
  under 25 kg.
* **Margin: in between at best.** Only the 2-axial-stage OPR-4 variant beats the pure centrifugal
  (+75 / +51 % vs +69 / +44 %), and its worst corner (+32 %) equals the centrifugal's. The 1-stage
  OPR-4.5 and 2-stage OPR-5 variants fail the 25 % pessimistic target (+19 %, +30 % with +15 % in
  the worst corner) because their diffusers grow to 185-195 mm. None comes close to the pure
  axial (+98 / +77 %, worst corner +61 %).
* **Risk moved, not removed:** the impeller-stress risk is traded for (a) the same unvalidated
  axial-stage efficiency and transonic front-stage risk as the pure axial, only on 1-2 stages,
  (b) the largest engine mass in the study, and (c) a length no better than the pure axial.
  Operability should be more benign than a 5-stage fixed-geometry axial (1-2 lightly loaded front
  stages ahead of a centrifugal is the classic arrangement for exactly that reason). But it is not
  quantified here, because no approved tool gives axial maps.

**Effect on the Phase 3 recommendation:** unchanged. On the numbers requested here, the
axial-centrifugal does not beat the pure axial on any metric: diameter, length, mass or margin. It
beats the pure centrifugal on stress and, in its best variant, on margin, at +2.3 kg of engine and
+230 mm of length. It therefore replaces nothing, but it is a better **fallback** than the pure
centrifugal if the impeller cannot be qualified at ~530 MPa: the 2-axial-stage OPR-4 variant
keeps +51 % pessimistic margin with a 1.58 stress factor. The recommended order becomes: (1) pure
axial OPR 5; (2) axial-centrifugal 2 axial + cc, OPR 4, if the pure axial's operability or
manufacturing is judged unacceptable and the impeller is not qualified; (3) pure centrifugal OPR 4
if its impeller clears ~530 MPa (lightest and shortest by 160-230 mm).
