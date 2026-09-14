"""Phase 6: CAD parameter sheet, generated from the Phase 3R / 4R analysis files (run in .venv).

Every CAD dimension is traceable: each entry is {value, unit, status, source}. Status:
  frozen      - an analysis result the design freeze carries (docs/design_freeze.md sections 1-3)
  derived     - computed here from frozen values by a stated rule (e.g. inducer metal angle from the flow angle)
  provisional - depends on an open freeze decision (diffuser, combustor length, bearing span / shaft, bleed) or was never
                designed by an analysis tool (deswirl vanes, bearing housings); built parametrically, expected to change
Airframe: Phase 2 airframe model (airframe_model.Config) at the Phase 4 engine. The inlet capture area and nozzle throat
are updated to the current engine (Phase 2 used the Phase 1 / Phase 2 engine values), and the drag effect is reported.
Outputs: data/phase6/engine_params.json, data/phase6/airframe_params.json, data/phase6/params_consistency.json
"""
import os, sys, json, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase2_airframe"))
import engine_mass as em, dash_cycle as dc
import airframe_model as afm
OUT = os.path.join(ROOT, "data", "phase6"); os.makedirs(OUT, exist_ok=True)
TAG = "ce75000_opr4_t1150_b15_cap"
P = lambda v, unit, status, source: dict(value=(float(v) if isinstance(v, (int, float, np.floating, np.integer)) and not isinstance(v, bool) else v),
                                         unit=unit, status=status, source=source)
d = json.load(open(os.path.join(ROOT, "data", "phase3r", f"cct_{TAG}.json"))); L = d["levels"]["fielded"]
cl = json.load(open(os.path.join(ROOT, "data", "phase4r_closure.json"))); rf = json.load(open(os.path.join(ROOT, "data", "phase4r_rotor_final.json")))
cyc = L["eval"]["cycle"]; sg = L["stress_geo"]; s = L["stress"]; rpm = d["rpm"]; om = rpm * math.pi / 30
cc = d["case"]["comp"]; vd = cc["geometry"]["vaned_diffuser"]; k = L["eval"]["scales"]
tt = json.load(open(os.path.join(ROOT, "data", "phase3r", f"{TAG}_ttf70_out.json"))); tg = tt["geometry"]
comb = cl["phase4_engine"]["combustor"]
SRC_CCT = f"data/phase3r/cct_{TAG}.json"; SRC_CL = "data/phase4r_closure.json"; SRC_TT = f"data/phase3r/{TAG}_ttf70_out.json"

# ---- impeller (fielded, as the stress sizing and the rotor model use it) ----
r2, r1s, r1h, Lx = sg["r2"], sg["r1s"], sg["r1h"], sg["L"]
b2g, b2e = s["blade"]["b2_geo"], sg["b2_eff"]
# axial-inflow eye velocity at the fielded flow (continuity, same rule as centrifugal_design.inducer)
T01, P01, W = cyc["Tt2_K"], cyc["Pt2_kPa"] * 1e3, cyc["W_kgps"]; R_, g_ = 287.05, 1.4; A1 = math.pi * (r1s ** 2 - r1h ** 2)
lo, hi = 1e-4, 0.99
for _ in range(80):
    M = 0.5 * (lo + hi); T = T01 / (1 + 0.2 * M * M); Pst = P01 * (T / T01) ** 3.5
    lo, hi = (M, hi) if Pst / (R_ * T) * M * math.sqrt(g_ * R_ * T) * A1 < W else (lo, M)
C1 = M * math.sqrt(g_ * R_ * T01 / (1 + 0.2 * M * M))
beta1 = lambda r: math.degrees(math.atan(om * r / C1))                  # zero-incidence metal angle from axial
r1rms = math.sqrt(0.5 * (r1s ** 2 + r1h ** 2))
imp = dict(
    rpm=P(rpm, "rpm", "frozen", SRC_CCT), n_main=P(12, "-", "frozen", "Phase 3R conventions"), n_splitter=P(12, "-", "frozen", "Phase 3R conventions"),
    splitter_start_frac_meridional=P(0.5, "-", "frozen", "Phase 3R (Aungier Z_eff = 12 + 12 x 0.5)"),
    r2=P(r2, "m", "frozen", SRC_CCT + " stress_geo (work-based fielded)"), r1_shroud=P(r1s, "m", "frozen", SRC_CCT), r1_hub=P(r1h, "m", "frozen", SRC_CCT),
    axial_length=P(Lx, "m", "frozen", "0.65 r2 (centrifugal_design / gate)"), b2_physical=P(b2g, "m", "frozen", "stress-sized blockage B2 = %.3f" % s["blade"]["B2"]),
    b2_effective=P(b2e, "m", "frozen", SRC_CCT), backsweep_deg=P(-15.0, "deg from radial (negative = backswept)", "frozen", "D3R.2 / user approval"),
    beta1_hub_deg=P(beta1(r1h), "deg from axial", "derived", "zero incidence, axial inflow, fielded eye velocity C1 = %.1f m/s" % C1),
    beta1_rms_deg=P(beta1(r1rms), "deg from axial", "derived", "as above"), beta1_shroud_deg=P(beta1(r1s), "deg from axial", "derived", "as above"),
    t_root_hub=P(s["blade"]["t_root_mm"] / 1e3, "m", "frozen", "stress sizing, Fty at MCS (impeller_stress.py)"),
    t_tip=P(0.8e-3, "m", "frozen", "stress model thickness at the shroud edge"),
    thickness_law=P("linear hub -> shroud, constant along the chord except LE/TE rounding", "-", "derived", "impeller_stress / gate plate model"),
    le_radius=P(0.4e-3, "m", "provisional", "half the tip thickness; not analysed"),
    camber_law=P("radial-fibre inducer theta_rf'(x) = (w/C1)(1 - x/L)^n, n = 3, + exducer backsweep linear in r from 0 at 0.7 r2 to the TE angle",
                 "-", "provisional", "stress model's blade (radial fibres; plate-model backsweep law); n set in the CAD for the 10 % choke margin (impeller_cad.py, D6.3)"),
    tip_clearance=P(0.25e-3, "m", "frozen", "A3.5"), hub_curve=P("quarter ellipse (r1h,0) -> (r2,L)", "-", "frozen", "impeller_stress_gate.hub_point"),
    shroud_curve=P("quarter ellipse (r1s,0) -> (r2,L-b2)", "-", "frozen", "impeller_stress_gate.shroud_point"),
    back_face=P(dict(t_rim=0.003, boss_A_over_r2=s["disc"]["A_over_r2"], boss_p=2.0, bore=0.0), "m / -", "frozen", "stress sizing (boreless, lowest-stress boss)"),
    throat_area_ratio_design=P(cc["area_throat_ratio"], "of the TOOL-level eye area", "frozen", "10 % choke margin at tool level (centrifugal_design); "
                               "the requirement carried to the fielded eye is the 10 % margin itself (0.665 x fielded eye, impeller_cad.choke_ratio)"),
    material=P("Ti-6Al-4V", "-", "frozen", "A3.2 / gate"))
# ---- diffuser (provisional: freeze 4.1 / 4.4) ----
dif = dict(r3=P(1.06 * r2, "m", "provisional", "vaneless gap 1.06 r2 (Phase 3R)"), r4=P(1.35 * r2, "m", "provisional", "R4/R2 1.35 (not optimised; freeze 4.6)"),
           width=P(b2e, "m", "provisional", "= effective impeller exit width (TurboFlow model)"),
           n_vanes=P(int(vd["number_of_vanes"]), "-", "provisional", "19; excites exducer mode 1 at idle (freeze 4.4)"),
           vane_le_deg=P(abs(vd["leading_edge_angle"]), "deg from radial", "provisional", "TurboFlow design flow angle alpha3"),
           vane_te_deg=P(vd["trailing_edge_angle"], "deg from radial", "provisional", "TurboFlow example (NASA-derived)"),
           vane_thickness=P(2.0e-3, "m", "provisional", "engine_mass assumption"),
           deswirl=P(dict(r_out=1.35 * r2, r_in=1.35 * r2 - 1.2 * b2e, axial_length=0.5 * r2, n_vanes=30), "m / -", "provisional",
                     "engine_mass envelope; deswirl never designed by an analysis tool (vane count placeholder)"),
           casing_wall=P(3e-3, "m", "frozen", "engine_mass: diffuser OD = 2 (r4 + 3 mm)"))
# ---- combustor (provisional: freeze 4.3) ----
cmb = dict(casing_OD=P(comb["OD_mm"] / 1e3, "m", "provisional", SRC_CL + " (grown to the diffuser envelope, D4R.1)"),
           Ro=P(comb["Ro_mm"] / 1e3, "m", "provisional", SRC_CL), Ri=P(comb["Ri_mm"] / 1e3, "m", "provisional", SRC_CL),
           liner_length=P(comb["L_liner_mm"] / 1e3, "m", "provisional", "0.8 x 3 x annulus height (rotor fix, freeze 4.3)"),
           section_length=P(1.15 * comb["L_liner_mm"] / 1e3, "m", "provisional", "engine_mass: 1.15 L_liner"),
           outer_liner_r=P(0.90 * comb["Ro_mm"] / 1e3, "m", "provisional", "engine_mass"), inner_liner_r=P(1.25 * comb["Ri_mm"] / 1e3, "m", "provisional", "engine_mass"),
           liner_wall=P(0.5e-3, "m", "provisional", "engine_mass"),
           vaporisers=P(dict(n=8, d=8e-3, length_frac=0.6), "-", "provisional", "engine_mass (8 vaporiser tubes)"), material_liner=P("Inconel 625", "-", "frozen", "engine_mass"))
# ---- turbine (frozen: TurboFlow design at the fielded cycle) ----
arr = lambda key: [float(x) for x in np.ravel(tg[key])]
tur = dict(source_file=P(SRC_TT, "-", "frozen", "TurboFlow, 350 MPa blade-root limit, 75 000 rpm"),
           n_ngv=P(int(round(2 * math.pi * arr("radius_mean_in")[0] / arr("pitch")[0])), "-", "frozen", SRC_TT),
           n_rotor=P(int(round(2 * math.pi * arr("radius_mean_in")[1] / arr("pitch")[1])), "-", "frozen", SRC_TT),
           **{kk: P(arr(kk), "m" if "radius" in kk or kk in ("chord", "axial_chord", "pitch", "maximum_thickness", "trailing_edge_thickness", "leading_edge_diameter", "tip_clearance", "opening") else "deg",
                    "frozen", SRC_TT + " [NGV, rotor]")
              for kk in ("radius_hub_in", "radius_hub_out", "radius_tip_in", "radius_tip_out", "chord", "axial_chord", "pitch", "opening", "maximum_thickness",
                         "trailing_edge_thickness", "leading_edge_diameter", "leading_edge_angle", "stagger_angle", "gauging_angle", "tip_clearance")},
           material=P("IN-713LC", "-", "frozen", "A3.2"))
# ---- rotor / bearings (provisional: freeze section 5) ----
e = cl["phase4_engine"]; gcomp = e["D_breakdown"]
L_comp = Lx + 0.5 * r2 + 0.01; x_t0 = L_comp + cmb["section_length"]["value"]; c_ngv, c_rot = arr("chord")
x_back = Lx + 0.003 + s["disc"]["A_over_r2"] * r2
rot = dict(shaft_od=P(0.032, "m", "provisional", "D4R.1 (rotor fix)"), shaft_id=P(0.0256, "m", "provisional", "D4R.1"),
           journal_d=P(0.012, "m", "provisional", "D4R.1, DN 0.95e6 at MCS"), journal_len=P(0.020, "m", "provisional", "cc_rotor"),
           bearing=P(dict(bore=0.012, od=0.028, width=0.008), "m", "provisional", "ISO 15 dimension series 10 (12 x 28 x 8, e.g. 6001 / 7001 size)"),
           x_front_bearing=P(x_back + 0.010, "m", "provisional", "10 mm behind the impeller back face (cc_rotor)"),
           x_rear_bearing=P(x_t0 + 0.8 * c_ngv, "m", "provisional", "under the NGV (cc_rotor)"),
           bearing_span=P(rf["span_mm"] / 1e3, "m", "provisional", "data/phase4r_rotor_final.json"),
           tunnel_r=P(0.018, "m", "provisional", "D4R.1"), damper=P(dict(k=1.75e6, c=876.0), "N/m, N s/m", "provisional", "A4R.2; cartridge not designed"),
           shaft_material=P("AISI 4340", "-", "frozen", "engine_mass"))
# ---- stations and envelope ----
r_tip_t = max(arr("radius_tip_in") + arr("radius_tip_out"))
L_turb = 1.6 * (c_ngv + c_rot); L_raw = L_comp + cmb["section_length"]["value"] + L_turb + 0.9 * r_tip_t
st = dict(x_impeller_nose=P(0.0, "m", "derived", "origin"), x_impeller_exit=P(Lx, "m", "derived", "hub exit plane"),
          x_compressor_section_end=P(L_comp, "m", "derived", "engine_mass: Lx + 0.5 r2 + 10 mm"),
          x_combustor_end=P(x_t0, "m", "derived", "engine_mass: + 1.15 L_liner"),
          x_ngv_le=P(x_t0, "m", "derived", "NGV at the combustor exit"), x_rotor_centre=P(x_t0 + 1.6 * c_ngv + 0.8 * c_rot, "m", "derived", "cc_rotor"),
          x_nozzle_exit=P(L_raw, "m", "derived", "engine_mass: turbine section 1.6 (c_NGV + c_rot) + nozzle 0.9 r_tip"),
          nozzle_A8=P(cyc["A8_cm2"] / 1e4, "m2", "frozen", SRC_CCT + " (convergent)"),
          nozzle_r8=P(math.sqrt(cyc["A8_cm2"] / 1e4 / math.pi), "m", "derived", "A8"))
env = dict(OD_model=P(e["D"] / 1e3, "m", "frozen", SRC_CL), length_components=P(L_raw, "m", "derived", "sum of the modelled component sections (engine_mass)"),
           length_calibrated=P(e["L_cal"] / 1e3, "m", "frozen", SRC_CL + " (x1.21 calibration: real engines carry flanges, starter, fittings)"),
           mass_raw=P(e["dry_raw"], "kg", "frozen", SRC_CL), mass_calibrated=P(e["dry_cal"], "kg", "frozen", SRC_CL))
eng = dict(tag=TAG, note="fielded engine (design freeze); SI units", impeller=imp, diffuser=dif, combustor=cmb, turbine=tur, rotor=rot, stations=st, envelope=env)
json.dump(eng, open(os.path.join(OUT, "engine_params.json"), "w"), indent=1)

# ---- airframe: Phase 2 model at the Phase 4 engine; capture and nozzle areas updated ----
def cfg(A_cap=None, A_noz=None):
    c = afm.Config(S_wing=0.30); c.D_engine = e["D"] / 1e3; c.L_engine = e["L_cal"] / 1e3
    if A_cap: c.A_capture = A_cap
    if A_noz: c.A_nozzle = A_noz
    return c
T0, P0, rho0, a0, mu0 = dc.isa(dc.H_DASH); A_cap_now = W / (rho0 * dc.M_DASH * a0); A_noz_now = cyc["A8_cm2"] / 1e4
cons = {}
for lab, c in (("Phase 2 inputs (capture 47.5 cm2, nozzle 49.1 cm2)", cfg()), ("capture updated", cfg(A_cap_now)), ("capture + nozzle updated", cfg(A_cap_now, A_noz_now))):
    cons[lab] = dict(CDS_nom_cm2=c.CDS(1.02, 5000.0) * 1e4, CDS_hi_cm2=c.CDS(1.02, 5000.0, E_WD=max(3.0, max(1.8, c.E_geom()))) * 1e4,
                     A_capture_cm2=c.A_capture * 1e4, A_nozzle_cm2=c.A_nozzle * 1e4)
    print(f"{lab:52s} dash drag area nominal {cons[lab]['CDS_nom_cm2']:.2f} cm2, pessimistic {cons[lab]['CDS_hi_cm2']:.2f} cm2")
c = cfg(A_cap_now, A_noz_now); srf = c.surfaces()
xs = np.linspace(0, c.L_fus, 241)
def surf(sf):
    return dict(S_ref=sf.S_ref, AR=sf.AR, taper=sf.taper, sweep_le_deg=sf.sweep_le_deg, tc=sf.tc, xc_maxt=sf.xc_maxt, x_root_le=sf.x_root_le,
                half_span=sf.half_span(), c_root=sf.c_root, c_tip=sf.c_root * sf.taper, vertical=sf.vertical,
                section="parabolic (biconvex) thickness t = 4 tc c xi (1 - xi), as the Phase 2 area-rule model")
A_w = srf["wing"].area_distribution(xs, c.r_fus)                                 # both exposed panels [m2]
r_body = c.body_radius(xs); r_waist = np.sqrt(np.maximum(r_body ** 2 - c.area_rule_waist * A_w / math.pi, 0.0))   # D2.6 waist, as the drag model
air = dict(note="Phase 2 airframe (C1) at the Phase 4 engine; capture and nozzle areas updated to the current engine", S_wing=0.30,
           body_r_waisted=r_waist.tolist(), wing_area_dist=A_w.tolist(),
           L_fus=c.L_fus, D_fus=c.D_fus, L_nose_frac=c.L_nose_frac, L_bt_frac=c.L_bt_frac, A_capture=c.A_capture, lip_wall=c.lip_wall,
           A_nozzle=c.A_nozzle, t_nozzle_wall=c.t_nozzle_wall, area_rule_waist=c.area_rule_waist,
           body_x=xs.tolist(), body_r=c.body_radius(xs).tolist(), surfaces={kk: surf(v) for kk, v in srf.items()},
           engine_face_x=c.x_wing_frac * c.L_fus + 0.1, engine_envelope=dict(D=e["D"] / 1e3, L=e["L_cal"] / 1e3),
           intake_duct_length=dc.L_DUCT, face_mach=cyc["duct"]["M_face"] if isinstance(cyc.get("duct"), dict) else None,
           chute_d=0.60, drag_consistency=cons)
json.dump(air, open(os.path.join(OUT, "airframe_params.json"), "w"), indent=1, default=float)
n_prov = sum(1 for sec in (imp, dif, cmb, tur, rot) for v in sec.values() if isinstance(v, dict) and v.get("status") == "provisional")
n_all = sum(1 for sec in (imp, dif, cmb, tur, rot) for v in sec.values() if isinstance(v, dict) and "status" in v)
json.dump(dict(C1_eye=C1, beta1=dict(hub=beta1(r1h), rms=beta1(r1rms), shroud=beta1(r1s)), L_components=L_raw, L_calibrated=e["L_cal"] / 1e3,
               drag=cons, provisional=n_prov, total=n_all), open(os.path.join(OUT, "params_consistency.json"), "w"), indent=1)
print(f"impeller: r2 {r2*1e3:.1f} mm, eye {r1s*1e3:.1f}/{r1h*1e3:.1f} mm, b2 {b2g*1e3:.1f} mm, C1 {C1:.0f} m/s, beta1 hub/rms/shroud {beta1(r1h):.1f}/{beta1(r1rms):.1f}/{beta1(r1s):.1f} deg")
print(f"stations: compressor section {L_comp*1e3:.1f} mm, combustor end {x_t0*1e3:.1f} mm, nozzle exit {L_raw*1e3:.1f} mm (modelled components); calibrated envelope {e['L_cal']:.0f} mm")
print(f"turbine: {tur['n_ngv']['value']} NGV / {tur['n_rotor']['value']} rotor; nozzle r8 {st['nozzle_r8']['value']*1e3:.1f} mm; {n_prov} of {n_all} engine parameters provisional")
print(f"airframe: L {c.L_fus} m, D_fus {c.D_fus*1e3:.1f} mm, capture {c.A_capture*1e4:.1f} cm2 (was 47.5), nozzle {c.A_nozzle*1e4:.1f} cm2 (was 49.1), engine face at x = {air['engine_face_x']:.3f} m")
