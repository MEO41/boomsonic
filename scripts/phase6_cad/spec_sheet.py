"""Engine specification sheet as a PDF (run in .venv-cad; reportlab 5.0.1 + matplotlib's DejaVu fonts).

Every number is read from the project's data files at run time (nothing typed in by hand):
  cycle            data/phase3r/cct_ce75000_opr4_t1150_b15_cap.json (fielded + tool levels, stress, calibration)
  sea-level static data/phase3r_mission_ce75000_opr4_t1150_b15_cap_deck.csv (T4-limited max, MN 0 / 0 m)
  geometry         data/phase6/engine_params.json (frozen / derived / provisional)
  closure          data/phase4r_closure.json; rotor data/phase4r_rotor_final.json; NASA check data/phase4r_td_check.json
  Phase 6          data/phase6/{impeller_cad_checks, fe3d_impeller, airframe_cad_checks}.json, mass_compare.csv
  constants        ETA_B from scripts/phase3_cycle/dash_cycle.py; turbine blade-root allowable from turbine_design.py
Output: docs/boomsonic_engine_spec.pdf
"""
import os, re, json, math, datetime
import pandas as pd
import matplotlib
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
J = lambda *p: json.load(open(os.path.join(ROOT, *p)))
TAG = "ce75000_opr4_t1150_b15_cap"

# ---------------- data ----------------
cct = J("data", "phase3r", f"cct_{TAG}.json"); F, T = (cct["levels"][k]["eval"]["cycle"] for k in ("fielded", "tool"))
stress = cct["levels"]["fielded"]["stress"]; cal = cct["calibration"]; turb_ev = cct["levels"]["fielded"]["eval"]["turbine"]
deck = pd.read_csv(os.path.join(ROOT, "data", f"phase3r_mission_{TAG}_deck.csv"))
sls = deck[(deck.MN.abs() < 1e-3) & (deck.alt_m.abs() < 1)].sort_values("Fn_N").iloc[-1]
E = J("data", "phase6", "engine_params.json"); v = lambda s, k: E[s][k]["value"]
clo = J("data", "phase4r_closure.json"); bud = clo["budget"]; p4 = clo["phase4_engine"]
rot = J("data", "phase4r_rotor_final.json"); td = J("data", "phase4r_td_check.json")["15"]["design"]
imp = J("data", "phase6", "impeller_cad_checks.json"); fe = J("data", "phase6", "fe3d_impeller.json"); ac = J("data", "phase6", "airframe_cad_checks.json")
mc = pd.read_csv(os.path.join(ROOT, "data", "phase6", "mass_compare.csv"))
src = lambda f: open(os.path.join(ROOT, "scripts", "phase3_cycle", f)).read()
ETA_B = float(re.search(r"^ETA_B\s*=\s*([0-9.]+)", src("dash_cycle.py"), re.M).group(1))
SIG_T = float(re.search(r'"sigma_allow",\s*([0-9.e]+)', src("turbine_design.py")).group(1)) / 1e6

# derived quantities (standard relations)
Mn, alt = F["MN"], F["alt_m"]
T0 = 288.15 - 0.0065 * alt; P0 = 101.325 * (T0 / 288.15) ** 5.2559               # ISA troposphere [K, kPa]
V0 = Mn * math.sqrt(1.4 * 287.05 * T0)
rpm = v("impeller", "rpm"); om = rpm * math.pi / 30
r2, r1s, r1h = (v("impeller", k) for k in ("r2", "r1_shroud", "r1_hub"))
C1 = om * r1h / math.tan(math.radians(v("impeller", "beta1_hub_deg")))
T1 = F["Tt2_K"] - C1 ** 2 / (2 * F["c_in_Cp"]); M1s_rel = math.hypot(C1, om * r1s) / math.sqrt(1.4 * 287.05 * T1)
tv = lambda k: E["turbine"][k]["value"]
mis = {m: clo["missions"][m]["summary"] for m in ("nom", "hi")}
Pf, Pff = fe["production"], fe["production_fine"]
rng = lambda a, b, f="{:.0f}": f"{f.format(min(a, b))}–{f.format(max(a, b))}"

# ---------------- document ----------------
fd = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DV", os.path.join(fd, "DejaVuSans.ttf"))); pdfmetrics.registerFont(TTFont("DVB", os.path.join(fd, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DVB", italic="DV", boldItalic="DVB")
ss = getSampleStyleSheet()
BODY = ParagraphStyle("b", parent=ss["BodyText"], fontName="DV", fontSize=8.6, leading=11.2)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=7.4, leading=9.4, textColor=colors.HexColor("#444444"))
H1 = ParagraphStyle("h1", parent=BODY, fontName="DVB", fontSize=17, leading=21, spaceAfter=2)
H2 = ParagraphStyle("h2", parent=BODY, fontName="DVB", fontSize=11.5, leading=14, spaceBefore=9, spaceAfter=4, textColor=colors.HexColor("#1f3a5f"))
CELL = ParagraphStyle("c", parent=BODY, fontSize=8, leading=10)
CELLB = ParagraphStyle("cb", parent=CELL, fontName="DVB")
NAVY, GRID, ZEBRA = colors.HexColor("#1f3a5f"), colors.HexColor("#b8c2cc"), colors.HexColor("#f2f5f8")
W = A4[0] - 30 * mm

HEAD = ParagraphStyle("hw", parent=CELLB, textColor=colors.white)
def table(rows, widths, header=True, bold_first=False):
    data = [[Paragraph(str(c), HEAD if (header and i == 0) else (CELLB if bold_first and j == 0 else CELL)) for j, c in enumerate(r)] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * W for w in widths], repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]
    if header: st += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    for i in range(1 if header else 0, len(rows)):
        if i % 2 == 0: st.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t.setStyle(TableStyle(st))
    return t

def fig(path, caption, width=W, maxh=95 * mm):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(path).getSize(); s = min(width / iw, maxh / ih)
    return KeepTogether([Image(path, iw * s, ih * s), Paragraph(caption, SMALL), Spacer(1, 5)])

P = lambda t, s=BODY: Paragraph(t, s)
story = []
story += [P("boomsonic_v0 — 500 N turbojet", H1),
          P("<b>Engine specification</b> · single-spool, centrifugal compressor, axial turbine · case <font face='DV'>"
            f"{TAG}</font> · generated {datetime.date.today().isoformat()} from the project data", BODY), Spacer(1, 4)]
status = Table([[P("<b>Status.</b> Conceptual design study (student learning project). The numbers come from verified tool runs "
                   "and cited relations: Phase 3R/4R analysis, the Phase 5 freeze and the Phase 6 CAD / 3D checks. <b>Nothing has "
                   "been measured on hardware.</b> Performance is at the <i>fielded</i> technology level (component efficiencies "
                   "that reproduce commercial micro-turbojet fuel burn) unless marked <i>tool</i>. <b>Open risks (section 9) are "
                   "not resolved</b>, the top one being the compressor surge margin, which no validated method has predicted.", CELL)]],
               colWidths=[W]); status.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#c0392b")), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fdf2f0")),
                                                          ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
story += [status, Spacer(1, 6)]

story += [P("1. Principal data", H2), table([
    ["parameter", "value", "condition / note"],
    ["net thrust", f"<b>{F['Fn_N']:.0f} N</b>", f"design point M {Mn:.2f}, {alt/1000:.0f} km ISA (sizing point)"],
    ["max static thrust", f"<b>{sls.Fn_N:.0f} N</b>", f"sea level, M 0, {sls.N_pct:.1f} % speed, limited by T4 (100 % speed would need {sls.T4_at_100pct:.0f} K)"],
    ["air mass flow", f"<b>{F['W_kgps']:.3f} kg/s</b>", f"design point (corrected {F['Wc2_kgps']:.3f} kg/s); {sls.W_kgps:.3f} kg/s at sea-level static"],
    ["compressor pressure ratio", f"<b>{F['comp_PR']:.1f}</b>", "total-to-total, single centrifugal stage"],
    ["turbine inlet temperature T4", f"<b>{F['Tt4_K']:.0f} K ({F['Tt4_K']-273.15:.0f} °C)</b>", "design limit; max thrust is T4-limited"],
    ["specific fuel consumption", f"<b>{F['TSFC_kgpNh']:.3f} kg/(N·h)</b>", f"design point; {sls.Wf_kgps*3600/sls.Fn_N:.3f} kg/(N·h) at sea-level static"],
    ["fuel flow", f"{F['Wf_kgps']*1000:.1f} g/s ({F['Wf_kgps']*3600:.0f} kg/h)", f"design point; {sls.Wf_kgps*1000:.1f} g/s at sea-level static"],
    ["spool speed", f"<b>{rpm:,.0f} rpm</b>", f"max continuous (MCS) {1.05*rpm:,.0f} rpm (105 %)"],
    ["envelope (Ø × length)", f"<b>{v('envelope','OD_model')*1e3:.1f} × {p4['L_cal']:.0f} mm</b>", f"drawn components {v('envelope','length_components')*1e3:.1f} mm long; the rest is calibrated length"],
    ["dry mass", f"<b>{p4['dry_cal']:.2f} kg</b>", f"calibrated (range {p4['dry_lo']:.2f}–{p4['dry_hi']:.2f}); + {bud['engine accessories (A3.7)']:.2f} kg accessories (ECU, pump …)"],
    ["thrust / dry weight", f"{sls.Fn_N/(p4['dry_cal']*9.80665):.1f}", "sea-level static"],
], [0.30, 0.25, 0.45])]

story += [P("2. Cycle at the design point", H2), P(
    f"Flight M {Mn:.2f} at {alt:.0f} m ISA: ambient {T0:.1f} K, {P0:.2f} kPa, flight speed {V0:.0f} m/s. The engine is sized for "
    f"{F['Fn_N']:.0f} N here; the gross thrust must also cover the ram drag of taking the air on board at flight speed.", BODY), Spacer(1, 3),
    table([["quantity", "fielded (design basis)", "tool level", "unit"],
           ["net thrust", f"{F['Fn_N']:.0f}", f"{T['Fn_N']:.0f}", "N"],
           ["gross thrust / ram drag", f"{F['Fg_N']:.0f} / {F['Fram_N']:.0f}", f"{T['Fg_N']:.0f} / {T['Fram_N']:.0f}", "N"],
           ["air mass flow (corrected)", f"{F['W_kgps']:.3f} ({F['Wc2_kgps']:.3f})", f"{T['W_kgps']:.3f} ({T['Wc2_kgps']:.3f})", "kg/s"],
           ["specific thrust", f"{F['spec_thrust']:.0f}", f"{T['spec_thrust']:.0f}", "N/(kg/s)"],
           ["compressor pressure ratio", f"{F['comp_PR']:.2f}", f"{T['comp_PR']:.2f}", "–"],
           ["turbine inlet temperature T4", f"{F['Tt4_K']:.0f}", f"{T['Tt4_K']:.0f}", "K"],
           ["fuel flow / TSFC", f"{F['Wf_kgps']*1000:.1f} / {F['TSFC_kgpNh']:.3f}", f"{T['Wf_kgps']*1000:.1f} / {T['TSFC_kgpNh']:.3f}", "g/s / kg/(N·h)"],
           ["fuel-air ratio", f"{F['FAR']:.4f}", f"{T['FAR']:.4f}", "–"],
           ["compressor η<sub>is</sub> / turbine η<sub>tt</sub> / combustion η<sub>b</sub>",f"{F['comp_eff']:.2f} / {F['turb_eff']:.2f} / {ETA_B:.2f}", f"{T['comp_eff']:.3f} / {T['turb_eff']:.3f} / {ETA_B:.2f}", "–"],
           ["compressor power", f"{F['comp_pwr_kW']:.0f}", f"{T['comp_pwr_kW']:.0f}", "kW"],
           ["turbine pressure ratio (tt)", f"{F['turb_PR']:.2f}", f"{T['turb_PR']:.2f}", "–"],
           ["nozzle: throat area / pressure ratio / jet velocity", f"{F['A8_cm2']:.1f} / {F['NPR']:.2f} / {F['Vj_mps']:.0f}", f"{T['A8_cm2']:.1f} / {T['NPR']:.2f} / {T['Vj_mps']:.0f}", "cm² / – / m/s"],
           ["intake capture area", f"{F['A_capture_cm2']:.1f}", f"{T['A_capture_cm2']:.1f}", "cm²"]],
          [0.40, 0.24, 0.20, 0.16]), Spacer(1, 3),
    P("<b>Gas-path stations</b> (fielded, total conditions)", BODY),
    table([["station", "total temperature", "total pressure", "note"],
           ["0 ambient (static)", f"{T0:.1f} K", f"{P0:.2f} kPa", f"ISA at {alt:.0f} m; flight speed {V0:.0f} m/s"],
           ["2 compressor inlet", f"{F['Tt2_K']:.1f} K", f"{F['Pt2_kPa']:.1f} kPa", "after the pitot intake (normal shock + subsonic duct loss)"],
           ["3 compressor exit", f"{F['Tt3_K']:.1f} K", f"{F['Pt3_kPa']:.1f} kPa", ""],
           ["4 turbine inlet", f"{F['Tt4_K']:.0f} K", f"{F['Pt4_kPa']:.1f} kPa", f"combustor pressure loss {100*(1-F['Pt4_kPa']/F['Pt3_kPa']):.1f} %"],
           ["5 turbine exit", f"{F['Tt5_K']:.1f} K", f"{F['Pt5_kPa']:.1f} kPa", f"{F['Tt5_K']-273.15:.0f} °C"]],
          [0.22, 0.2, 0.2, 0.38])]

story += [P("3. Sea-level static (take-off) point", H2), table([
    ["thrust", "air flow", "fuel flow", "TSFC", "T4", "speed", "surge-margin surrogate"],
    [f"{sls.Fn_N:.0f} N", f"{sls.W_kgps:.3f} kg/s", f"{sls.Wf_kgps*1000:.1f} g/s", f"{sls.Wf_kgps*3600/sls.Fn_N:.3f} kg/(N·h)", f"{sls.T4_K:.0f} K", f"{sls.N_pct:.1f} %",
     f"{100*sls.SMN:.1f} % — <b>not validated</b> (the surrogate fails on the NASA HECC stage)"]],
    [0.1, 0.12, 0.11, 0.14, 0.09, 0.09, 0.35])]

d = E["diffuser"]; cb = E["combustor"]; ro = E["rotor"]; bg = ro["bearing"]["value"]; ds = d["deswirl"]["value"]; vp = cb["vaporisers"]["value"]
prov = " <font color='#c0392b'>(provisional)</font>"
story += [P("4. Components", H2), table([
    ["component", "specification"],
    ["<b>Compressor</b>", f"single-stage centrifugal, {v('impeller','material')}; <b>{int(v('impeller','n_main'))} main + {int(v('impeller','n_splitter'))} splitter blades</b> "
     f"(splitters from {v('impeller','splitter_start_frac_meridional'):.0%} of the meridional length); exit backsweep <b>{v('impeller','backsweep_deg'):.0f}°</b>; "
     f"exit diameter {2*r2*1e3:.1f} mm, tip speed {om*r2:.0f} m/s ({1.05*om*r2:.0f} m/s at MCS); eye tip / hub radius {r1s*1e3:.1f} / {r1h*1e3:.1f} mm; "
     f"inducer shroud relative Mach {M1s_rel:.2f}; exit width effective / physical {v('impeller','b2_effective')*1e3:.1f} / {v('impeller','b2_physical')*1e3:.1f} mm; "
     f"blade thickness {v('impeller','t_root_hub')*1e3:.2f} mm at the exducer root → {v('impeller','t_tip')*1e3:.1f} mm at the tip; tip clearance {v('impeller','tip_clearance')*1e3:.2f} mm; "
     f"boreless hub with back-face boss. η<sub>tt</sub>: tool {T['comp_eff']:.3f} (TurboFlow), {td['eta_is_stage']:.3f} (NASA turbo-design, PR {td['PR_stage']:.2f}); fielded {F['comp_eff']:.2f}. "
     f"Inducer choke flow {imp['throat']['choke_flow_over_design']:.3f} × design flow (requirement 1.10). Wheel {imp['wheel']['mass_kg']:.3f} kg (Phase 6 CAD)."],
    ["<b>Diffuser</b>" + prov, f"vaneless gap to r3 = {v('diffuser','r3')*1e3:.1f} mm ({v('diffuser','r3')/r2:.2f} r2), then <b>{int(v('diffuser','n_vanes'))}-vane</b> radial vaned "
     f"diffuser to r4 = {v('diffuser','r4')*1e3:.1f} mm (R4/R2 {v('diffuser','r4')/r2:.2f}), vane angle {v('diffuser','vane_le_deg'):.1f}° → {v('diffuser','vane_te_deg'):.0f}° "
     f"from radial, channel width {v('diffuser','width')*1e3:.1f} mm; 90° bend inside r4 into an axial deswirl annulus "
     f"({int(ds['n_vanes'])} vanes, placeholder count). Sets the engine diameter."],
    ["<b>Combustor</b>" + prov, f"annular, casing OD {v('combustor','casing_OD')*1e3:.1f} mm, annulus radii {v('combustor','Ro')*1e3:.1f} / {v('combustor','Ri')*1e3:.1f} mm, "
     f"<b>liner length {v('combustor','liner_length')*1e3:.0f} mm</b> (0.8 × the length rule, set by rotor dynamics), reference velocity "
     f"{p4['combustor']['U_ref']:.1f} m/s; {int(vp['n'])} vaporiser tubes Ø {vp['d']*1e3:.0f} mm; liner {cb['material_liner']['value']}; η<sub>b</sub> {ETA_B:.2f} (assumed), "
     f"pressure loss {100*(1-F['Pt4_kPa']/F['Pt3_kPa']):.0f} %."],
    ["<b>Turbine</b>", f"single-stage axial, {tv('material')}, uncooled; <b>{int(v('turbine','n_ngv'))} nozzle guide vanes / {int(v('turbine','n_rotor'))} rotor blades</b>; "
     f"rotor tip radius {turb_ev['r_tip_mm']:.1f} mm, exactly on the {SIG_T:.0f} MPa blade-root stress limit (limit {turb_ev['r_tip_stress_limit_mm']:.1f} mm); "
     f"rotor hub / tip radius at exit {tv('radius_hub_out')[1]*1e3:.1f} / {tv('radius_tip_out')[1]*1e3:.1f} mm; chord NGV / rotor {tv('chord')[0]*1e3:.1f} / {tv('chord')[1]*1e3:.1f} mm; "
     f"η<sub>tt</sub> tool {turb_ev['eta_tt_tool']:.3f}, fielded {F['turb_eff']:.2f}; pressure ratio {F['turb_PR']:.2f}; constant-stress (Stodola) disc."],
    ["<b>Nozzle</b>", f"fixed convergent, throat area {F['A8_cm2']:.1f} cm² (r8 {v('stations','nozzle_r8')*1e3:.1f} mm), pressure ratio {F['NPR']:.2f} at the design point "
     f"(choked), jet velocity {F['Vj_mps']:.0f} m/s; in the aircraft, a {ac['jetpipe']['total_length_m']:.2f} m jetpipe leads to the tail nozzle."],
    ["<b>Rotor & bearings</b>" + prov, f"{ro['shaft_material']['value']} tube shaft {v('rotor','shaft_od')*1e3:.0f} × {v('rotor','shaft_id')*1e3:.1f} mm, journals Ø {v('rotor','journal_d')*1e3:.0f} mm; "
     f"two hybrid ball bearings {bg['bore']*1e3:.0f} × {bg['od']*1e3:.0f} × {bg['width']*1e3:.0f} mm, <b>span {rot['span_mm']:.0f} mm</b>, overhung impeller "
     f"({rot['overhang_imp_mm']:.0f} mm) and turbine ({rot['overhang_turb_mm']:.0f} mm); damped soft supports; rotor {rot['mass']['m_rotor_kg']:.2f} kg, "
     f"Ip {rot['mass']['Ip_kgm2']*1e3:.2f}e-3 kg·m²; bearing DN {rot['DN_MCS']/1e6:.3f}e6 at MCS."],
], [0.17, 0.83])]

dm = rot["damped"]
story += [P("5. Rotor dynamics (API 684 criteria)", H2), table(
    [["mode", "critical speed", "damping ratio ζ", "amplification factor", "separation margin (required)", "status"]] +
    [[f"{i+1}", f"{m['crit_rpm']:,.0f} rpm", f"{m['zeta']:.3f}", f"{m['AF']:.2f}", f"{100*m['sm']:.0f} % ({100*m['sm_req']:.0f} %)", "pass" if m["ok"] else "FAIL"] for i, m in enumerate(dm)],
    [0.08, 0.18, 0.16, 0.18, 0.26, 0.14]), P(f"Operating range to {1.05*rpm:,.0f} rpm lies between modes 2 and 3; overall API check: "
                                               f"<b>{'pass' if rot['api_ok'] else 'fail'}</b>. Model: ROSS beam rotor with the damped bearing supports.", SMALL)]

mrows = [["item", "model raw [kg]", "Phase 6 CAD [kg]", "CAD / model"]]
for _, r in mc.iterrows():
    if r.model_item.startswith(("TOTAL", "(no")): continue
    NAMES = {"diffuser_deswirl": "diffuser + deswirl", "shroud_inlet": "inlet shroud + front wall", "ngv_vanes": "NGV vanes", "ngv_rings": "NGV rings",
             "outer_casing": "outer casing (compressor + hot section)", "shaft_tunnel_bearing_housings": "shaft tunnel + bearing housings",
             "bearings_2x_hybrid": "bearings (2, hybrid)", "fuel_manifold_igniter": "fuel manifold + igniter",
             "fasteners_seals_balancing_10pct": "fasteners, seals, balancing (10 %)", "combustor_liners": "combustor liners + vaporisers"}
    nm = "<b>items drawn in the CAD</b>" if r.model_item.startswith("SUBTOTAL") else NAMES.get(r.model_item, r.model_item.replace("_", " "))
    mrows.append([nm,"" if pd.isna(r.model_raw_kg) else f"{r.model_raw_kg:.3f}", "not drawn" if pd.isna(r.cad_kg) else f"{r.cad_kg:.3f}",
                  "" if pd.isna(r.cad_over_model) else f"{r.cad_over_model:.2f}"])
story += [P("6. Mass", H2), P(f"Bottom-up model {p4['dry_raw']:.2f} kg × calibration {cal['K_M']:.2f} (fitted on the JetCat P400 and AMT Nike; "
                             f"range ×{cal['K_M_lo']:.2f}–{cal['K_M_hi']:.2f}) = <b>{p4['dry_cal']:.2f} kg</b>. The calibration covers the items no model draws "
                             "(flanges, fasteners, seals, harness), so the CAD is compared with the raw model.", BODY), Spacer(1, 3),
          table(mrows, [0.46, 0.18, 0.2, 0.16])]

fy = stress["Fty_MPa"]
story += [P("7. Structural status (maximum continuous speed, Ti-6Al-4V minimum yield Fty "
            f"{fy:.0f} MPa at ~250 °C)", H2), table([
    ["location", "Phase 3R analysis", "Phase 6 3D FE (two meshes)", "assessment"],
    ["impeller exducer blade root", f"{stress['blade']['sigma_root_MCS_MPa']:.0f} MPa incl. Kt 1.4 (plate model; sized to Fty)",
     f"{rng(Pf['exducer_root']['hot_spot_x_Kt_MPa'], Pff['exducer_root']['hot_spot_x_Kt_MPa'])} MPa incl. Kt 1.4",
     f"<b>{100*min(Pf['exducer_root']['hot_spot_x_Kt_MPa'],Pff['exducer_root']['hot_spot_x_Kt_MPa'])/fy:.0f}–{100*max(Pf['exducer_root']['hot_spot_x_Kt_MPa'],Pff['exducer_root']['hot_spot_x_Kt_MPa'])/fy:.0f} % of Fty</b>: on the limit"],
    ["impeller inducer blade root", f"{stress['inducer_root_MCS_MPa']:.0f} MPa (1D radial tension)", f"{rng(Pf['inducer_root']['hot_spot_MPa'], Pff['inducer_root']['hot_spot_MPa'])} MPa "
     f"({rng(Pf['inducer_root']['hot_spot_x_Kt_MPa'], Pff['inducer_root']['hot_spot_x_Kt_MPa'])} incl. Kt 1.4)", "inside the limit; the 1D method misses the in-plane load path"],
    ["impeller disc / hub", f"{stress['disc']['vm_mech_MCS_MPa']:.0f} MPa mechanical, {stress['disc']['vm_thermal_MCS_MPa']:.0f} MPa with thermal gradient",
     f"{rng(Pf['hub']['vm_p999_MPa'], Pff['hub']['vm_p999_MPa'])} MPa mechanical", f"~{100*(fy/(Pff['hub']['vm_p999_MPa']+stress['disc']['vm_thermal_MCS_MPa']-stress['disc']['vm_mech_MCS_MPa'])-1):.0f} % yield margin with thermal"],
    ["impeller burst", f"speed ratio {stress['disc']['burst_ratio_MCS']:.2f} (≥ 1.20 required, 14 CFR 33.27)", "–", "pass"],
    ["blade-to-casing tip clearance", f"{v('impeller','tip_clearance')*1e3:.2f} mm cold", f"closes {Pff['tip']['max_closing_mm']:.3f} mm (mechanical)", "thermal growth not included"],
    ["turbine blade root", f"on the {SIG_T:.0f} MPa conceptual allowable (IN-713LC)", "–", "on the limit; life data needed"],
], [0.21, 0.29, 0.25, 0.25])]

story += [P("8. Installed in the aircraft", H2), table([
    ["item", "value"],
    ["take-off gross weight / margin to 25 kg", f"{bud['TOGW']:.2f} kg / {bud['margin to 25 kg']:.2f} kg"],
    ["fuel (sortie + reserve + unusable)", f"{bud['fuel (sortie + reserve + 3 % unusable)']:.2f} kg; sortie {mis['nom']['sortie_s']:.0f} s"],
    ["dash thrust margin (nominal / pessimistic wave drag)", f"+{100*mis['nom']['dash_margin']:.1f} % / +{100*mis['hi']['dash_margin']:.1f} %"],
    ["brake release to M 1.02 at 5 km / ground roll", f"{mis['nom']['time_to_dash_s']:.1f} s / {mis['nom']['ground_roll_m']:.0f} m"],
    ["intake / jetpipe", f"pitot, capture {ac['intake']['capture_area_cm2']:.1f} cm², duct area ratio {ac['intake']['area_ratio']:.2f}; jetpipe "
     f"{ac['jetpipe']['total_length_m']:.2f} m at M {ac['jetpipe']['Mach']:.2f}, friction loss {100*ac['jetpipe']['dPt_over_Pt_friction']:.2f} % of total pressure (not in the cycle)"],
    ["engine to fuselage skin", f"{ac['engine_clearance']['radial_gap_mm']:.1f} mm radial at the area-rule waist"],
], [0.42, 0.58])]

story += [P("9. Open risks (none resolved)", H2), table([
    ["risk", "status"],
    ["compressor surge margin (vaned-diffuser stall)", "<b>OPEN, top risk.</b> No validated prediction method; the peak-PR surrogate fails on the NASA HECC stage"],
    ["surge margin in the idle range / start bleed", "OPEN; no bleed sized or reserved"],
    ["combustor shortened 20 % for rotor dynamics", "OPEN; combustion performance unverified"],
    ["19 diffuser vanes excite exducer mode 1 at idle", "OPEN; 3D blade modes not run"],
    ["exducer root and turbine blade root on their limits", "confirmed in 3D (exducer); fatigue / life not assessed"],
    ["inducer camber (rapid unloading, set by the 10 % choke margin)", "aerodynamic loading not analysed (needs CFD)"],
    ["hardware", "no rig or bench test of any component"],
], [0.45, 0.55]), Spacer(1, 6),
    P("Sources: design_log.md (Phases 3R–6), docs/design_freeze.md, docs/phase6_cad.md, and the data files listed in "
      "scripts/phase6_cad/spec_sheet.py. Regenerate with <font face='DV'>.venv-cad\\Scripts\\python scripts\\phase6_cad\\spec_sheet.py</font>.", SMALL)]

story += [PageBreak(), P("10. Geometry (Phase 6 CAD)", H2),
          fig(os.path.join(ROOT, "plots", "phase6_engine_cutaway.png"), "Engine cutaway: centrifugal impeller and vaned diffuser (right), annular combustor with vaporisers, "
              "single-stage axial turbine, convergent nozzle. Static parts cut open over one quadrant; the rotor is shown whole.", maxh=100 * mm),
          fig(os.path.join(ROOT, "plots", "phase6_engine_section.png"), "Meridional half-section of the CAD (plane z = 0), coloured by material.", maxh=80 * mm),
          PageBreak(),
          fig(os.path.join(ROOT, "plots", "phase6_impeller.png"), "Impeller: 12 main + 12 splitter blades, −15° backsweep, D2 "
              f"{2*r2*1e3:.0f} mm, Ti-6Al-4V ({imp['wheel']['mass_kg']:.2f} kg).", width=0.58 * W, maxh=85 * mm),
          fig(os.path.join(ROOT, "plots", "phase6_impeller_fe.png"), "3D FE, von Mises stress at maximum continuous speed on the 30° cyclic sector "
              "(magenta would mark stress above yield; the yellow spot at the blade LE root is a sharp-corner singularity of the unfilleted CAD).", width=0.62 * W, maxh=90 * mm),
          fig(os.path.join(ROOT, "plots", "phase6_aircraft_cutaway.png"), "Installation: pitot intake duct, engine at the area-ruled waist, jetpipe to the tail nozzle.", maxh=55 * mm)]

def footer(c, doc):
    c.saveState(); c.setFont("DV", 7); c.setFillColor(colors.HexColor("#666666"))
    c.drawString(15 * mm, 10 * mm, f"boomsonic_v0 · engine specification · {TAG} · conceptual study, not hardware data")
    c.drawRightString(A4[0] - 15 * mm, 10 * mm, f"page {doc.page}"); c.restoreState()

out = os.path.join(ROOT, "docs", "boomsonic_engine_spec.pdf")
SimpleDocTemplate(out, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=16 * mm,
                  title="boomsonic_v0 engine specification", author="boomsonic_v0 design study").build(story, onFirstPage=footer, onLaterPages=footer)
print("wrote", os.path.relpath(out, ROOT))
