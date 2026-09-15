# Phase 4: rotor dynamics of the pure-axial engine (conceptual screening, 2026-09-13)

**Engine:** the corrected Phase 3 pure-axial engine, taken from
`data/phase3/trade_ax0_opr5_t1150_cap_blk_fielded.json`:

* 6-stage axial compressor, OPR 5, design speed 80 000 rpm (overspeed to about 88 000 rpm, 110 %);
* single-stage capped turbine;
* fielded level, with geometry scaled by s = 1.114.

Every radius, mass and axial station is read from that file through `arch_trade.scaled_comp` and
`engine_mass`, and the rotor model reproduces the engine_mass disc and blade masses exactly
(`rotor_model.geometry`, mass check). An earlier scratch run on the superseded Phase 3 geometry
(65 000 rpm, 5 stages, before the blockage fix) was discarded and is not used here.

This is a screening study: linear rotor dynamics with idealised bearings. It is not a mechanical design.

## Result in brief

| question | answer |
|---|---|
| Does the rotor as sized for mass in Phase 3 pass? | **No.** The Phase 3 rotor has a 16/8 mm steel shaft and a 0.32 mm drum wall, which is just the 10 % tie allowance. It has shaft-bending critical speeds inside the 35-105 % operating range at every bearing stiffness from 6e5 to 1e9 N/m, damped or undamped. |
| Can hard-mounted ball bearings work? | **No.** At 1.9e7 N/m, with any shaft of 16-32 mm OD and any drum wall of 0.3-3 mm, a lightly damped mode sits at 40-41 krpm, which is 50 % speed. |
| Can a stiff rotor keep every critical outside the operating range without damping? | **No.** The engine is about 0.43 m long, has heavy ends (a 0.60 kg turbine, a 0.44 kg compressor stack), and the shaft is limited to about 24-28 mm OD by the combustor hub (Ri 17.4 mm). On soft supports its first free-free bending mode reaches at most about 53 krpm, against the 106 krpm target. |
| What works? | **Layout A** (front bearing at the compressor inlet hub, rear bearing under the NGV, turbine overhung by 20 mm). It needs **soft, damped bearing supports**: k about 0.6-5e6 N/m and c about 900-2000 N s/m, from squeeze-film or O-ring damper cartridges as used on ball-bearing turbochargers. It also needs a **stiffened rotor**: a 2 mm Ti drum and a 24/12 mm shaft, with 16 mm bearing journals. Every critical inside or near the operating range is then critically damped (AF < 2.5), and the only lightly damped mode is at 120 krpm, 43 % above MCS against the 26 % required. |
| Cost | Rotor mass goes from 1.39 to 1.91 kg (**+0.53 kg**, uncalibrated), and Ip from 9.3e-4 to 1.12e-3 kg m². The engine relies on the dampers: the free-free bending mode at about 36 krpm (45 % speed) is passed only because it is critically damped. |
| Rotor polar inertia (for acceleration) | **9.31e-4 kg m²** as mass-sized; **1.12e-3 kg m²** for the recommended stiffened rotor (layout A). |

## 1. Tool and verification

**ROSS** (`ross-rotordynamics` 2.3.0, PyPI) is an open-source rotor-dynamic FE code with Timoshenko
beams, discs and bearings. It was installed into `.venv` and added packages only; no existing
package changed version. Two import work-arounds are in `ross_shim.py`, and neither touches the FE
matrices or the eigen-solution:
* plotly 7 removed the `scattermapbox` template key that ROSS's plot theme uses;
* numba 0.67 cannot compile ROSS's orbit helper (`np.argmax` on a complex array), so it runs with
  `NUMBA_DISABLE_JIT=1`.

The sweeps use ROSS's assembled M, K, G and C matrices, restricted to the lateral DOFs, with the
project's own eigen-solvers: `rotordynamics.Lateral` (undamped) and `rotordynamics_damped.Damped`.

Verification (`rotordynamics_verify.py`, results in `data/phase4_rotordynamics_verification.json`):

| case | closed form | error |
|---|---|---|
| (a) simply supported uniform shaft, 1st bending, Euler-Bernoulli | (pi/L)^2 sqrt(EI/rho A) | -0.0001 % (the Timoshenko version is -0.30 %, the expected shear and rotary-inertia correction) |
| (b) Jeffcott rotor (central disc on a massless shaft) | sqrt(48 EI / m L^3) | -0.0001 % |
| (c) overhung disc on a cantilever, gyroscopic forward and backward whirl at 0-60 krpm | 2x2 disc-tip stiffness determinant (Friswell et al., *Dynamics of Rotating Machines*, ch. 3) | -0.13 to -0.20 % |
| (d) project lateral solver vs ROSS `run_modal`; forward synchronous critical vs closed form | same rotor as (c) | 0.000 % (same whirl labels); -0.19 % |
| (e) project damped solver: disc on damped supports | wn = sqrt(2k/m), zeta = c / sqrt(2km) | +0.003 % frequency, -0.006 % damping ratio |

The mesh is converged: a 5 mm mesh instead of 10 mm changes the criticals by at most 0.04 %.

## 2. Rotor model (`rotor_model.py`)

**Compressor.** Six solid constant-stress Ti-6Al-4V discs, from the engine_mass Stodola profile,
each with its blades as radial rods. Engine_mass sizes them without a bore, so the stages are joined
at the rim by a drum. In the mass model the drum is only the 10 % "drum/ties" allowance, which gives
a 0.32 mm Ti shell.

**Shaft and turbine.** A 4340 steel shaft, OD 16 / ID 8 mm (engine_mass), runs from the last
compressor disc to the turbine. The turbine is an IN-713LC Stodola disc with blades. Every disc
carries +10 % mass and inertia, matching engine_mass's allowance for fasteners, seals and balancing.

**Materials:** Ti E 110 GPa, steel E 205 GPa, with a -10 % sensitivity case for hot-metal E.

| item | mass | Ip | x from compressor front |
|---|---|---|---|
| compressor stages C1-C6 (disc + blades, +10 %) | 0.078 / 0.070 / 0.069 / 0.070 / 0.073 / 0.076 kg | 8e-5 ... 4e-5 kg m² each | 28-194 mm |
| turbine disc + blades (+10 %) | 0.601 kg | 5.95e-4 kg m² | 434 mm |
| shaft 16/8 + 0.32 mm drum (as mass-sized) | 0.351 kg | 4.0e-5 kg m² | |
| **total rotor, layout A** | **1.387 kg** | **9.31e-4 kg m²** | CG 294 mm |

**Layouts** (two rolling bearings, isotropic translational stiffness k):

| | front bearing | rear bearing | bearing span | overhang |
|---|---|---|---|---|
| **A: straddled compressor, overhung turbine** | 5 mm, in the inlet hub | under the NGV, 414 mm | 409 mm | turbine 20 mm |
| **B: both bearings in the shaft tunnel** (RC-model style) | 15 mm behind the last disc, 209 mm | under the NGV | 205 mm | compressor 181 mm, turbine 20 mm |

**Why layout A is the baseline.** It is chosen on the results, not on precedent. Layout B, the
RC-model arrangement, leaves a 181 mm, 0.44 kg compressor drum overhung, doubles the gyroscopic
bearing load (below), and passes the damped check in fewer cases (section 5). Both layouts are
reported throughout.

**Static bearing loads at 1 g (layout A):** front 4.0 N, rear 9.6 N. The recommended rotor gives
6.2 N and 12.5 N.

**Gyroscopic bearing load** in pitch or yaw, Ip Omega q / span:
* layout A: **19 N per rad/s** (23 N for the recommended rotor);
* layout B: 38 N per rad/s.

At a manoeuvre rate of about 2-3 rad/s this exceeds the weight loads by 3-5 times, so it should size
the bearings.

## 3. Criteria

These are the API 684 (2003) tutorial statements of the API 617 lateral criteria, read from the
publication. MCS is 105 % of design speed (84 000 rpm) and the minimum operating speed is idle,
taken as 35 % (28 000 rpm).

| amplification factor AF | required separation margin |
|---|---|
| AF < 2.5 | none ("critically damped") |
| 2.5 to 3.55 | 15 % above MCS, 5 % below minimum speed |
| AF > 3.55 | above MCS: 126 - 6/(AF-3) - 100 %, capped at 26 %; below minimum speed: 100 - (84 + 6/(AF-3)) %, capped at 16 % |

**Undamped analyses** (section 4) use the caps: 26 % above MCS (106 krpm) and 16 % below idle (23.5 krpm).

**Damped analyses** (section 5) use AF = 1 / (2 zeta), the half-power relation of the API 684
definition AF = Nc / (N2 - N1).

**Operating above rigid-body critical speeds is normal practice.** San Andrés (TAMU ME626 Notes 13,
2010) states that squeeze-film dampers are used primarily in aircraft jet engines to provide the
damping that rolling bearings lack, with the bearing elastically supported. Gunter (2023, "Design of
oil and air squeeze film dampers for a ball bearing turbocharger") has a turbocharger's rigid-body
modes at about 5 and 15 krpm with a 150 krpm maximum speed.

## 4. Undamped critical-speed map, Campbell diagram, modes (`rotordynamics.py`)

Plots: `axial/plots/phase4_critical_speed_map.png`, `phase4_campbell.png`, `phase4_rotor_modes.png`.
Data: `axial/data/phase4_rotordynamics.json`, `_critmap.csv`.

**Bearing stiffness sources:**
* 1.9e7 N/m: maximum radial stiffness of a 10 x 26 mm, 15 deg angular-contact ball bearing at
  63 000 rpm (Wang, Lv & Luo, *Sensors* 2023, PMC10181543).
* 4.4e7 N/m: 250 000 lb/in, Gunter's ball-bearing value on rigid supports.
* 1.75e6 N/m: optimum damper-cartridge spring rate, 10 000 +- 3 000 lb/in (Gunter 2023).
* 6e5 N/m: micro-gas-turbine bearing suspension, from manufacturer data confirmed by test (ASME
  *J. Eng. Gas Turbines Power* 146(10) 101002, 2024).

Forward synchronous critical speeds of the Phase 3 (mass-sized) rotor, in krpm (the number in
brackets is the share of strain energy in the bearings at the critical):

| layout, k | crit 1 | crit 2 | crit 3 | crit 4 | verdict (AF unknown) |
|---|---|---|---|---|---|
| A, 6e5 | 7.6 (0.90) | 10.1 (0.52) | 25.7 (0.50) | 73.8 (0.03) | fails: 25.7 is only 8 % below idle; 73.8 is in range |
| A, 1.75e6 | 10.7 (0.31) | 14.1 (0.83) | 35.4 (0.64) | 76.4 (0.11) | fails: 35.4 and 76.4 in range |
| A, 1.9e7 | 11.9 (0.02) | 40.0 (0.76) | 57.0 (0.18) | 99.8 (0.20) | fails: 40.0 and 57.0 in range; 99.8 is 19 % above MCS |
| A, 1e9 (rigid) | 12.1 | 56.8 | 97.1 | | fails |
| B, 1.75e6 | 8.1 (0.50) | 14.1 (0.90) | 28.0 (0.53) | 75.7 (0.01) | fails |
| B, 1.9e7 | 10.6 (0.06) | 39.7 (0.76) | 61.7 (0.54) | 80.8 (0.17) | fails |

The 12 krpm first mode of layout A does not move with bearing stiffness because it is a bending
mode of the whole 0.41 m span (1-2 % of its energy is in the bearings).

Sensitivities (layout A, 1.9e7):
* hot-metal E -10 %: 11.3 / 39.4 / 54.6 krpm;
* discs threaded on a through-shaft instead of the drum: 8.9 / 38.3 / 44.4 krpm.

**Stiffening sweep** (`rotordynamics_stiffening.py`, `axial/plots/phase4_rotor_stiffening.png`): layout A,
k = 6e5 / 1.75e6 / 1.9e7, drum wall 0.32-3 mm, shaft OD 16-32 mm (ID/OD 0.5, journals 16 mm).
**No case meets the worst-case undamped margins:**
* **Soft supports:** the rigid-body modes move below idle (5-18 krpm), but the rotor's first
  free-free bending mode stays at 23-53 krpm, well below the 106 krpm target. The best case
  (32 mm shaft, 2-3 mm drum) reaches at most about 53 krpm.
* **Hard supports:** a mode at 39-42 krpm, with 76-89 % of its energy in the bearings, sits
  in the range whatever the rotor stiffness.

Shaft OD above about 24 mm also collides with the 14 mm-radius shaft tunnel that engine_mass assumes
inside the combustor hub (Ri 17.4 mm).

## 5. Damped assessment (`rotordynamics_damped.py`, `axial/data/phase4_rotordynamics_damped.csv`, `axial/plots/phase4_rotor_damped_AF.png`)

Damped forward critical speeds and their AF, for three rotors × k (6e5, 1.75e6, 5e6, 1.9e7 N/m) ×
support damping c (0, 300, 876, 2000 N s/m). The value 876 N s/m is Gunter's 5 lb s/in stable case.
A case passes when every critical meets the AF-dependent margin, and any critical inside 28-84 krpm
has AF < 2.5.

| rotor | layout A passes at | layout B passes at |
|---|---|---|
| Phase 3 (16/8 shaft, 0.32 mm drum) | **none**: a bending mode at 53-64 krpm keeps AF 3.0-7.2, and on hard supports modes at 40-57 krpm | none |
| drum 2 mm, shaft 24/12, journals 16 | **k 6e5-5e6 with c 876 or 2000** | k 6e5-5e6 with c 2000 only |
| drum 2 mm, shaft 28/14, journals 16 | k 6e5-5e6 with c 876 or 2000 | none |
| any rotor on hard supports (1.9e7) | none: damping at the bearings cannot reach modes whose motion is not at the bearings | none |

**Recommended configuration** (layout A, drum 2 mm, shaft 24/12, k 1.75e6, c 876). Its damped
criticals:

| critical | AF | position | requirement |
|---|---|---|---|
| 11.1 krpm | 1.88 | below idle | none |
| 17.9 krpm | 1.84 | below idle | none |
| 35.6 krpm | 1.14 | inside the range, critically damped | none |
| 120.0 krpm | 6.2 | 43 % above MCS | >= 26 % |

With c 2000 the criticals are 20.8 krpm (AF 2.4) and 102.7 krpm (AF 2.8, 22 % above MCS against
the 15 % required). Layout A is the more robust choice: the stiffened rotor passes at both damping
levels tested (876 and 2000 N s/m), while layout B passes only at 2000 N s/m and only with the
24/12 shaft.

## 6. Recommendation (screening level)

1. **Layout A:** front bearing in the compressor inlet hub, rear bearing under the NGV, turbine
   overhung by about 20 mm.
2. **Soft, damped bearing supports.** Squeeze-film or O-ring damper cartridges around both ball
   bearings, with k about 1-2e6 N/m (window 0.6-5e6) and c of about 900-2000 N s/m, of the same
   order as Gunter's ball-bearing turbocharger cartridge. Hard-mounted bearings are not viable for
   this rotor.
3. **Stiffen the rotor** beyond the Phase 3 mass sizing: a 2 mm Ti drum joining the compressor discs
   and a 24/12 mm steel shaft (fits the 14 mm-radius tunnel), with 16 mm bearing journals. Rotor mass
   rises 1.39 → 1.91 kg (+0.53 kg, uncalibrated; about +0.66 kg with the ×1.24 mass calibration if
   applied like the rest of the engine).
4. **Numbers for the acceleration and transient work:**
   * **Ip = 1.12e-3 kg m²** for the recommended rotor (9.31e-4 kg m² as mass-sized);
   * rotor mass 1.91 kg;
   * bearing loads 6.2 / 12.5 N at 1 g, plus 23 N per rad/s of pitch or yaw rate.
5. **Criticals crossed on the way to idle:** the two rigid-body modes at 11-18 krpm (14-22 % speed)
   are crossed during the start. The bending mode at about 36 krpm (45 %) is crossed during every
   acceleration from idle and sits near the part-power range. The design depends on the dampers
   delivering their damping at that mode.

## 7. Assumptions

| id | assumption | status |
|---|---|---|
| R1 | geometry and masses from engine_mass (Stodola discs, blade volume, +10 % allowance); axial stations from the engine_mass envelope rules | traceable, conceptual |
| R2 | compressor drum = thin Ti shell at the disc rim radius; joint (tie-bolt or curvic) flexibility ignored | optimistic |
| R3 | discs rigid (lumped m, Ip, Id); no disc or blade modes | standard for lateral screening |
| R4 | bearings isotropic, translational stiffness only, no moment stiffness, speed- and load-independent; dampers linear viscous | screening; real SFDs are nonlinear |
| R5 | no aerodynamic cross-coupling (Alford), no seal forces; stability not assessed | open |
| R6 | E at room temperature (-10 % sensitivity shown) | minor |
| R7 | idle 35 %, MCS 105 % (API definition); overspeed 110 % covered by the 26 % margin above MCS | assumption |
| R8 | AF = 1/(2 zeta) from the damped eigenvalue at the critical | single-mode approximation |

## 8. Caveats and open items

* **Bearing speed.** Journals of 16 mm at 80 000 rpm give DN 1.28e6. That is above the micro gas
  turbine reference (15 mm, 70 000 rpm, DN 1e6; IntechOpen chapter 53984) and the 10 mm Wang
  bearing (DN 0.7e6). The bearing selection, lubrication and life at this DN are open. A 12-14 mm
  journal (DN 1.0-1.1e6) would need re-checking.
* **Damper realisation.** The result depends on achieving about 900 N s/m at both supports without
  degrading the stiffness window, including hot-end damper temperature and O-ring ageing. A damped
  unbalance-response calculation (clearances, bearing forces) and a stability run with aero
  cross-coupling are the next rotor-dynamic steps.
* The 85 000 rpm alternative (`trade_ax85000_*`) was not analysed.
* This is not a detailed mechanical design. There is no CAD, and no drum/joint or bearing-housing
  design.
