"""Phase 6A (EXPLORATORY, axial option): CAD parameter sheet for the 6-stage axial core (run in .venv).

Phase 6A is packaging-and-mass exploration of the axial option (docs/design_freeze_axial.md, tag
ax80000_opr5_t1150_n6_cap_3r). It is NOT a build release and NOT an architecture decision: the centrifugal
(docs/design_freeze.md) remains the baseline and its Phase 6 status is unchanged.

Every CAD dimension is traceable: each entry is {value, unit, status, source}. Status:
  frozen      - an analysis result the axial freeze carries (docs/design_freeze_axial.md sections 1-3)
  derived     - computed here from frozen values by a stated rule
  provisional - never designed by an analysis tool (variable-geometry hardware, bearing housings, ducting),
                or dependent on an open freeze item; built parametrically, expected to change

NO SCALING, NO EVEN SPACING: the six stages come one by one from the fielded blading in the trade file, and the
axial stations follow axial_design.py's own stack-up rule (row_gap_to_chord = stage_gap_to_chord = 0.25, i.e.
each row occupies 1.25 x chord). rotor_model.geometry() supplies the disc / bearing / turbine stations it used
for the rotordynamic pass, so the CAD and the rotor model share one layout.

Also computes the VARIABLE-GEOMETRY ACTUATION LOADS (section "vg_loads"), which the CAD needs to size real
actuators instead of the freeze's placeholder 3 x 75 g servos (open risk 4.4). These are first-order conceptual
relations, stated per item, not a validated actuation analysis.

Output: data/phase6a/axial_params.json
"""
import os, sys, json, math, contextlib, io, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase6_cad")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery"))
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import engine_mass as em
    import rotor_model as rm

TAG = "ax80000_opr5_t1150_n6_cap_3r"
OUT = os.path.join(AXROOT, "data", "phase6a"); os.makedirs(OUT, exist_ok=True)
SRC_AXT = f"data/phase3ax/axt_{TAG}.json"; SRC_TT = f"data/phase3ax/{TAG}_ttf_out.json"
SRC_CL = f"data/phase4ax/closure_{TAG}.json"; SRC_OPF = f"data/phase4ax/operability_{TAG}_final.json"
SRC_RD = f"data/phase4ax/rotor_{TAG}.json"; SRC_RS = f"data/phase4ax/rotor_stress_{TAG}.json"
SRC_TL = f"data/phase4ax/trade_like_{TAG}.json"

P = lambda v, unit, status, source: dict(value=(float(v) if isinstance(v, (int, float, np.floating, np.integer)) and not isinstance(v, bool) else v),
                                         unit=unit, status=status, source=source)
J = lambda rel: json.load(open(os.path.join(ROOT, rel)))

AX = J(SRC_AXT); F = AX["levels"]["fielded"]; comp = F["comp"]; cyc = F["eval"]["cycle"]
TT = J(SRC_TT); tg = TT["geometry"]
CL = J(SRC_CL); eng = CL["engine"]; comb = eng["combustor"]; drum = eng["drum"]
OPF = J(SRC_OPF); cfg = OPF["config"]
RS = J(SRC_RS)
rpm = comp["input"]["rpm"]; omega = rpm * math.pi / 30
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    geo = rm.geometry(os.path.join(ROOT, SRC_TL))

R_GAS, GAM = 287.05, 1.4

# ---------------------------------------------------------------- compressor stations (per stage, real numbers)
# axial_design.py: row_gap_to_chord = stage_gap_to_chord = 0.25 -> each row occupies 1.25 x its chord.
# rotor_model.geometry starts the first rotor LE at x = 15 mm (engine_mass adds 15 mm at each end of the compressor).
X0 = 0.015
stages, x = [], X0
for st, dsc in zip(comp["stages"], geo["discs"]):
    ro, sta = st["rotor"], st["stator"]
    x_r_le = x; x_s_le = x + 1.25 * ro["chord"]
    stages.append(dict(
        stage=int(st["stage"]),
        rotor=dict(x_le=x_r_le, chord=ro["chord"], r_hub=ro["r_hub"], r_tip=ro["r_tip"], h=ro["h"], Z=int(ro["Z"]), tc=ro["tc"],
                   t_max=ro["tc"] * ro["chord"], disc_x=dsc["x"], disc_r_rim=dsc["r_rim"], disc_bore_width=dsc["bore_width"],
                   m_disc_kg=dsc["m_disc"], m_blades_kg=dsc["m_blades"]),
        stator=dict(x_le=x_s_le, chord=sta["chord"], r_hub=sta["r_hub"], r_tip=sta["r_tip"], h=sta["h"], Z=int(sta["Z"]), tc=sta["tc"],
                    t_max=sta["tc"] * sta["chord"]),
        PR=st["PR"], U_mean=st["U_mean"], M_rel_tip=st["M_rel_tip"]))
    x += 1.25 * (ro["chord"] + sta["chord"])
L_blading = x - X0
assert abs(L_blading - comp["length"]) < 1e-9, "stage stack-up does not reproduce comp['length']"

# static state at each stage inlet (for the VIGV load and the bleed): total pressure from the cumulative stage PRs
Pt2, Tt2, W = cyc["Pt2_kPa"] * 1e3, cyc["Tt2_K"], cyc["W_kgps"]
pt, tt_ = [Pt2], [Tt2]
for st in comp["stages"]:
    pt.append(pt[-1] * st["PR"])
    tt_.append(tt_[-1] * st["PR"] ** ((GAM - 1) / GAM / max(st["eta_stage"], 1e-6)))

def static(P0, T0, M):
    T = T0 / (1 + 0.5 * (GAM - 1) * M * M); p = P0 * (T / T0) ** (GAM / (GAM - 1))
    return p, T, p / (R_GAS * T), M * math.sqrt(GAM * R_GAS * T)

# ---------------------------------------------------------------- combustor / turbine / nozzle / rotor stations
L_comp_section = geo["L_comp"]                      # blading + 15 mm each end (engine_mass comp_geo L_mm)
x_comb0 = L_comp_section
L_comb_section = 1.15 * comb["L_liner_mm"] / 1e3
x_t0 = geo["x_t0"]
c_ngv, c_rot = geo["c_ngv"], geo["c_rot"]
x_ngv_le = x_t0 + 0.3 * c_ngv                       # NGV inside the 1.6 (c_ngv + c_rot) turbine section (engine_mass rule)
x_trot_le = x_t0 + 1.6 * c_ngv
r_t_tip = float(max(np.ravel(tg["radius_tip_in"]).max(), np.ravel(tg["radius_tip_out"]).max()))
r_t_hub = float(np.ravel(tg["radius_hub_in"])[0])
Z_ngv = float(2 * math.pi * 0.5 * (np.ravel(tg["radius_hub_in"])[0] + np.ravel(tg["radius_tip_in"])[0]) / np.ravel(tg["pitch"])[0])
Z_trot = float(2 * math.pi * 0.5 * (np.ravel(tg["radius_hub_in"])[1] + np.ravel(tg["radius_tip_in"])[1]) / np.ravel(tg["pitch"])[1])
L_turb_section = 1.6 * (c_ngv + c_rot)
L_engine_raw = geo["L_engine"]                      # engine_mass L_total (raw, before the x1.209 length calibration)

A8 = cyc["A8_cm2"] / 1e4; r8 = math.sqrt(A8 / math.pi); r8_max = r8 * math.sqrt(cfg["a8_max"])

# rotor (ax_rotor adopted row: 2 mm drum, 24 / 12 mm shaft, 12 mm journals, k 1.75e6, c 876)
SHAFT_OD, SHAFT_ID, JOURNAL, TUNNEL_R, T_DRUM, JOURNAL_LEN = 0.024, 0.012, 0.012, 0.014, 0.002, 0.020
x_brg_front, x_brg_rear = 0.005, x_t0 + 0.8 * c_ngv

# ---------------------------------------------------------------- variable-geometry actuation loads
# All three are first-order conceptual estimates with the stated relation; none is a validated actuation analysis.
s1 = stages[0]; ro1 = s1["rotor"]
C_VIGV, R_CRANK, D_SPINDLE, MU_BUSH, E_CP = 0.8, 0.006, 0.003, 0.20, 0.15   # chord factor, crank arm, spindle, friction, c.p. offset
Z_igv = s1["stator"]["Z"]                                                   # = stage-1 stator count (ax_closure rule)
c_v = C_VIGV * ro1["chord"]; h_v = ro1["h"]
r_m1 = 0.5 * (ro1["r_tip"] + ro1["r_hub"])
p1, T1, rho1, V1 = static(Pt2, Tt2, comp["inlet_M"])
a2 = math.radians(cfg["vigv"] + 7.4)                                        # design exit swirl 22.4 deg (freeze 1.3)
a_m = math.atan(0.5 * math.tan(a2)); V_m = V1 / math.cos(a_m)
s_pitch = 2 * math.pi * r_m1 / Z_igv
CL_v = 2 * (s_pitch / c_v) * math.cos(a_m) * math.tan(a2)
q_v = 0.5 * rho1 * V_m ** 2
L_v = CL_v * q_v * c_v * h_v                                                # lift per vane [N]
M_h_vane = L_v * E_CP * c_v                                                 # hinge moment about a spindle at 0.30 c
M_f_vane = MU_BUSH * L_v * 0.5 * D_SPINDLE                                  # bushing friction
M_vane = M_h_vane + M_f_vane
F_ring_vigv = Z_igv * M_vane / R_CRANK
d_theta = math.radians(cfg["vigv_closure_deg"])
stroke_vigv = 2 * R_CRANK * math.sin(0.5 * d_theta)

# bleed: choked overboard port area at the stage-3 exit state, band-valve seal friction
frac_P, frac_W = cfg["frac_P"], cfg["frac_work"]
P_bleed = pt[cfg["bleed_stage"]]; T_bleed = tt_[cfg["bleed_stage"]]
W_bleed = cfg["bleed"] * W
CHOKE = math.sqrt(GAM / R_GAS) * (2 / (GAM + 1)) ** ((GAM + 1) / (2 * (GAM - 1)))
CD_PORT, MU_BAND, N_PORT = 0.80, 0.30, 8
A_port = W_bleed * math.sqrt(T_bleed) / (CHOKE * P_bleed) / CD_PORT
p_amb_dash = 54019.0                                                        # ISA 5 km (Phase 2 atmosphere)
dP_bleed = P_bleed - p_amb_dash
F_seal_bleed = dP_bleed * A_port
r_manifold = comp["stages"][2]["stator"]["r_tip"] + 0.004
M_bleed = MU_BAND * F_seal_bleed * r_manifold

# variable nozzle: 12 flaps, hinged at the front, pressure-loaded outward; actuator holds them CLOSED at the dash
N_FLAP, F_OVERLAP, L_FLAP_FAC, LINK_FRAC, LINK_ANG = 12, 1.3, 0.6, 0.8, math.radians(30.0)
Pt8, Tt8 = cyc["Pt5_kPa"] * 1e3, cyc["Tt5_K"]
GAM_H = cyc["t_out_gamma"]
p_throat = Pt8 * (2 / (GAM_H + 1)) ** (GAM_H / (GAM_H - 1))                 # choked (NPR 2.80)
A_ann = math.pi * (r_t_tip ** 2 - r_t_hub ** 2)                             # turbine exit annulus
lo, hi = 1e-4, 0.99                                                         # subsonic root of the continuity equation
for _ in range(200):
    m5 = 0.5 * (lo + hi)
    T5 = Tt8 / (1 + 0.5 * (GAM_H - 1) * m5 * m5); p5 = Pt8 * (T5 / Tt8) ** (GAM_H / (GAM_H - 1))
    w5 = p5 / (R_GAS * T5) * m5 * math.sqrt(GAM_H * R_GAS * T5) * A_ann
    lo, hi = (m5, hi) if w5 < W else (lo, m5)
p_in = p5
p_mean_flap = 0.5 * (p_in + p_throat)
# The flaps are SIZED by the fully open position (as ax_closure does), but the actuator load is bounded by the
# CLOSED position at the dash point: highest jet pressure, and the flap is then wetted over 2 pi r8 / N (the 30 %
# overlap takes up the difference). The open position is evaluated too, at the SLS idle jet pressure.
L_flap = L_FLAP_FAC * 2 * r8_max
w_flap = 2 * math.pi * r8_max * F_OVERLAP / N_FLAP                          # material width (sizing / mass)
w_wet_closed = 2 * math.pi * r8 / N_FLAP                                    # wetted width at A8 x 1.0
A_flap = L_flap * w_wet_closed
dP_flap = p_mean_flap - p_amb_dash
F_flap = dP_flap * A_flap
M_h_flap = F_flap * 0.5 * L_flap
F_link_flap = M_h_flap / (LINK_FRAC * L_flap * math.sin(LINK_ANG))
F_sync_ring = N_FLAP * F_link_flap * math.cos(LINK_ANG)
stroke_nozzle = (r8_max - r8) / math.tan(LINK_ANG)
# Linkage-independent invariants: what any mechanism must hold and do. Force and stroke trade with the lever
# ratio, the hinge moment and the work do not.
M_hinge_total = N_FLAP * M_h_flap
theta_flap = math.asin((r8_max - r8) / L_flap)
W_nozzle = M_hinge_total * theta_flap

vg_loads = dict(
    vigv=dict(
        Z=P(Z_igv, "-", "provisional", "ax_closure.vg_hardware: IGV count = stage-1 stator count"),
        chord=P(c_v, "m", "provisional", f"{C_VIGV} x rotor-1 chord (ax_closure.vg_hardware)"),
        span=P(h_v, "m", "derived", "stage-1 rotor blade height, " + SRC_AXT),
        q_dynamic=P(q_v, "Pa", "derived", f"0.5 rho V_m^2 at the compressor face (M {comp['inlet_M']:.3f}, rho {rho1:.4f} kg/m3, V_m {V_m:.1f} m/s)"),
        CL_vane=P(CL_v, "-", "derived", "cascade lift CL = 2 (s/c) cos(a_m) tan(a2), a2 = 22.4 deg design swirl (Dixon eq. 3.17)"),
        lift_per_vane=P(L_v, "N", "derived", "CL q c h"),
        hinge_moment_per_vane=P(M_vane, "N m", "derived", f"lift x {E_CP} c (centre of pressure aft of a 0.30 c spindle) + bushing friction mu {MU_BUSH}, d {D_SPINDLE * 1e3:.0f} mm"),
        unison_ring_force=P(F_ring_vigv, "N", "derived", f"Z x hinge moment / crank arm {R_CRANK * 1e3:.0f} mm"),
        stroke=P(stroke_vigv, "m", "derived", f"ring travel for {cfg['vigv_closure_deg']:.0f} deg vane rotation at the crank arm"),
        note="stationary vanes: no centrifugal term. Aero load at the DASH point (highest q at the compressor face)."),
    bleed=dict(
        stage=P(cfg["bleed_stage"], "-", "frozen", SRC_OPF),
        bleed_fraction=P(cfg["bleed"], "-", "frozen", SRC_OPF),
        P_total=P(P_bleed, "Pa", "derived", "cumulative stage PRs to the stage-3 exit"),
        T_total=P(T_bleed, "K", "derived", "cumulative stage PRs / stage efficiencies"),
        mass_flow=P(W_bleed, "kg/s", "derived", f"{cfg['bleed']:.2f} x inlet flow {W:.3f} kg/s"),
        port_area=P(A_port, "m2", "derived", f"choked flow, Cd {CD_PORT}, discharging to ambient"),
        n_ports=P(N_PORT, "-", "provisional", "Phase 6A layout choice"),
        delta_p=P(dP_bleed, "Pa", "derived", "stage-3 total minus ISA 5 km ambient (bounding: the bleed is open at <= 95 % speed)"),
        seal_force=P(F_seal_bleed, "N", "derived", "delta_p x port area"),
        valve_torque=P(M_bleed, "N m", "derived", f"band-valve seal friction mu {MU_BAND} at r {r_manifold * 1e3:.1f} mm"),
        note="bounding case: full dash pressure. The bleed actually opens at <= 95 % speed, mostly at SLS."),
    nozzle=dict(
        n_flaps=P(N_FLAP, "-", "provisional", "ax_closure.vg_hardware"),
        r8_design=P(r8, "m", "frozen", f"A8 {cyc['A8_cm2']:.1f} cm2, " + SRC_AXT),
        r8_max=P(r8_max, "m", "frozen", f"A8 x {cfg['a8_max']:.1f} (ax_operability final schedule)"),
        flap_length=P(L_flap, "m", "provisional", f"{L_FLAP_FAC} x 2 r8_max (ax_closure.vg_hardware)"),
        flap_width=P(w_flap, "m", "derived", f"{F_OVERLAP} x circumference at r8_max / {N_FLAP} (30 % overlap) - the material width"),
        flap_wetted_width_closed=P(w_wet_closed, "m", "derived", f"2 pi r8 / {N_FLAP} at A8 x1.0 - the pressure-loaded width"),
        turbine_exit_M=P(m5, "-", "derived", f"continuity on the {A_ann * 1e4:.2f} cm2 turbine exit annulus"),
        p_mean_inner=P(p_mean_flap, "Pa", "derived", f"mean of the turbine-exit static ({p_in / 1e3:.1f} kPa, M {m5:.3f}) and the choked throat static ({p_throat / 1e3:.1f} kPa, gamma {GAM_H:.3f})"),
        delta_p=P(dP_flap, "Pa", "derived", "mean inner static minus ISA 5 km ambient"),
        force_per_flap=P(F_flap, "N", "derived", "delta_p x flap area"),
        hinge_moment_per_flap=P(M_h_flap, "N m", "derived", "force at mid-flap about the front hinge"),
        hinge_moment_total=P(M_hinge_total, "N m", "derived", f"{N_FLAP} flaps: the moment ANY mechanism must hold at the dash point (linkage-independent)"),
        flap_travel=P(math.degrees(theta_flap), "deg", "derived", "flap rotation from A8 x1.0 to x2.0 at the modelled flap length"),
        actuation_work=P(W_nozzle, "J", "derived", "hinge moment x travel: the work any mechanism must do (upper bound; the moment falls as the nozzle opens)"),
        link_force_per_flap=P(F_link_flap, "N", "derived", f"pushrod at {LINK_FRAC} of the flap length, {math.degrees(LINK_ANG):.0f} deg to the flap"),
        sync_ring_force=P(F_sync_ring, "N", "derived", "axial component of the 12 link forces"),
        stroke=P(stroke_nozzle, "m", "derived", f"sync-ring travel from A8 x1.0 to x{cfg['a8_max']:.1f} at the link angle"),
        note="the actuator HOLDS the flaps closed at the dash point against the jet pressure; this is the bounding load."),
)

# ---------------------------------------------------------------- assemble
params = dict(
    tag=TAG,
    phase="6A (exploratory: packaging and mass only)",
    note=("Exploratory CAD of the AXIAL option, to resolve open risk 4.4 (unsourced variable-geometry hardware) and "
          "check radial packaging inside the 142.45 mm engine OD. NOT a build release, NOT an architecture decision. "
          "The centrifugal baseline (docs/design_freeze.md) and its Phase 6 status are unchanged."),
    sources=dict(trade=SRC_AXT, turbine=SRC_TT, closure=SRC_CL, operability=SRC_OPF, rotor=SRC_RD, rotor_stress=SRC_RS, trade_like=SRC_TL),
    cycle=dict(
        rpm=P(rpm, "rpm", "frozen", SRC_AXT), mcs_frac=P(1.05, "-", "frozen", "docs/design_freeze_axial.md 1.2"),
        W=P(W, "kg/s", "frozen", SRC_AXT), Pt2=P(Pt2, "Pa", "frozen", SRC_AXT), Tt2=P(Tt2, "K", "frozen", SRC_AXT),
        Pt3=P(cyc["Pt3_kPa"] * 1e3, "Pa", "frozen", SRC_AXT), Tt3=P(cyc["Tt3_K"], "K", "frozen", SRC_AXT),
        Tt4=P(cyc["Tt4_K"], "K", "frozen", SRC_AXT), Pt5=P(cyc["Pt5_kPa"] * 1e3, "Pa", "frozen", SRC_AXT),
        Tt5=P(cyc["Tt5_K"], "K", "frozen", SRC_AXT), A8=P(A8, "m2", "frozen", SRC_AXT),
        inlet_M=P(comp["inlet_M"], "-", "frozen", SRC_AXT)),
    compressor=dict(
        n_stages=P(len(stages), "-", "frozen", SRC_AXT),
        x_first_rotor_le=P(X0, "m", "derived", "engine_mass comp_geo: 15 mm ahead of the first rotor"),
        stack_rule=P("each row occupies 1.25 x chord (row_gap_to_chord = stage_gap_to_chord = 0.25)", "-", "frozen", "scripts/phase3_cycle/axial_design.py:41"),
        blading_length=P(L_blading, "m", "frozen", SRC_AXT + " comp.length"),
        section_length=P(L_comp_section, "m", "derived", "blading + 15 mm each end (engine_mass)"),
        r_tip_max=P(comp["r_tip_max"], "m", "frozen", SRC_AXT),
        casing_id=P(comp["r_tip_max"] + 0.25e-3, "m", "derived", "r_tip_max + 0.25 mm running clearance (axial_design)"),
        casing_od=P(comp["D_casing_mm"] / 2e3, "m", "frozen", SRC_AXT + " (2.5 mm Al wall)"),
        casing_wall=P(0.0025, "m", "frozen", "engine_mass.axial_compressor_mass"),
        tip_clearance=P(comp["input"]["clearance"], "m", "frozen", SRC_AXT),
        stages=stages),
    combustor=dict(
        x_start=P(x_comb0, "m", "derived", "end of the compressor section"),
        section_length=P(L_comb_section, "m", "derived", "1.15 x L_liner (engine_mass)"),
        L_liner=P(comb["L_liner_mm"] / 1e3, "m", "provisional", "Phase 3 length rule, not re-checked (freeze 4.9)"),
        Ro=P(comb["Ro_mm"] / 1e3, "m", "frozen", SRC_CL), Ri=P(comb["Ri_mm"] / 1e3, "m", "frozen", SRC_CL),
        OD=P(comb["OD_mm"] / 1e3, "m", "frozen", SRC_CL + " (sets the engine diameter)"),
        r_liner_outer=P(0.90 * comb["Ro_mm"] / 1e3, "m", "frozen", "engine_mass: outer liner at 0.90 Ro"),
        r_liner_inner=P(1.25 * comb["Ri_mm"] / 1e3, "m", "frozen", "engine_mass: inner liner at 1.25 Ri"),
        t_liner=P(0.5e-3, "m", "frozen", "engine_mass"), n_vaporisers=P(8, "-", "frozen", "engine_mass"),
        U_ref=P(comb["U_ref"], "m/s", "frozen", SRC_CL)),
    turbine=dict(
        x_section_start=P(x_t0, "m", "derived", "compressor section + 1.15 L_liner (rotor_model)"),
        section_length=P(L_turb_section, "m", "derived", "1.6 (c_ngv + c_rotor) (engine_mass)"),
        x_ngv_le=P(x_ngv_le, "m", "provisional", "NGV placed 0.3 c_ngv into the turbine section (Phase 6A layout)"),
        x_rotor_le=P(x_trot_le, "m", "derived", "1.6 c_ngv from the section start (engine_mass / rotor_model)"),
        r_hub=P(r_t_hub, "m", "frozen", SRC_TT), r_tip=P(r_t_tip, "m", "frozen", SRC_TT + " (on the 350 MPa root limit)"),
        c_ngv=P(c_ngv, "m", "frozen", SRC_TT), c_rotor=P(c_rot, "m", "frozen", SRC_TT),
        Z_ngv=P(Z_ngv, "-", "frozen", SRC_TT + " (2 pi r_mean / pitch)"), Z_rotor=P(Z_trot, "-", "frozen", SRC_TT),
        t_max_ngv=P(float(np.ravel(tg["maximum_thickness"])[0]), "m", "frozen", SRC_TT),
        t_max_rotor=P(float(np.ravel(tg["maximum_thickness"])[1]), "m", "frozen", SRC_TT),
        stagger_ngv=P(float(np.ravel(tg["stagger_angle"])[0]), "deg", "frozen", SRC_TT),
        stagger_rotor=P(float(np.ravel(tg["stagger_angle"])[1]), "deg", "frozen", SRC_TT),
        disc_x=P(geo["turbine"]["x"], "m", "frozen", "rotor_model (rotordynamic pass)"),
        disc_r_rim=P(geo["turbine"]["r_rim"], "m", "frozen", "rotor_model"),
        disc_bore_width=P(geo["turbine"]["bore_width"], "m", "frozen", "engine_mass Stodola disc, IN-713LC 300 MPa"),
        m_disc_kg=P(geo["turbine"]["m_disc"], "kg", "frozen", "engine_mass"), m_blades_kg=P(geo["turbine"]["m_blades"], "kg", "frozen", "engine_mass"),
        shroud_t=P(2.0e-3, "m", "frozen", "engine_mass turbine shroud ring")),
    nozzle=dict(
        r8_design=P(r8, "m", "frozen", SRC_AXT), a8_max=P(cfg["a8_max"], "-", "frozen", SRC_OPF),
        r8_max=P(r8_max, "m", "derived", "r8 sqrt(A8 ratio)"),
        x_exit=P(L_engine_raw, "m", "derived", "engine_mass L_total (raw)"),
        cone_t=P(0.5e-3, "m", "frozen", "engine_mass nozzle cones")),
    rotor=dict(
        shaft_od=P(SHAFT_OD, "m", "frozen", "ax_rotor adopted layout A (D4A.2)"), shaft_id=P(SHAFT_ID, "m", "frozen", "ax_rotor"),
        journal_od=P(JOURNAL, "m", "frozen", "ax_rotor (DN 1.008e6 at MCS)"), journal_len=P(JOURNAL_LEN, "m", "frozen", "rotor_model.build default"),
        tunnel_r=P(TUNNEL_R, "m", "frozen", "ax_closure (Phase 4 limit under the combustor hub)"),
        drum_t=P(T_DRUM, "m", "frozen", "ax_closure / ax_rotor"), drum_r_mean=P(drum["r_mean_mm"] / 1e3, "m", "frozen", SRC_CL),
        drum_length=P(drum["L_mm"] / 1e3, "m", "frozen", SRC_CL),
        x_bearing_front=P(x_brg_front, "m", "frozen", "rotor_model layout A"), x_bearing_rear=P(x_brg_rear, "m", "frozen", "rotor_model layout A"),
        bearing_span=P(x_brg_rear - x_brg_front, "m", "frozen", SRC_RD),
        bearing_bore=P(JOURNAL, "m", "frozen", "12 mm journals"),
        bearing_od=P(0.028, "m", "provisional", "12 x 28 x 8 hybrid ball bearing envelope (as Phase 6 centrifugal)"),
        bearing_width=P(0.008, "m", "provisional", "as above"),
        m_rotor_kg=P(1.5974247383484812, "kg", "frozen", SRC_RD + " (adopted row)"),
        disc_stress_MPa=P(365.0, "kg", "frozen", "ax_rotor_stress: discs re-sized to 365 MPa at design speed, burst 1.20 at MCS"),
        disc_mass_delta=P(RS["disc_check"]["mass_delta_kg"], "kg", "frozen", SRC_RS)),
    envelope=dict(
        OD=P(eng["D"] / 1e3, "m", "frozen", SRC_CL + " (combustor-set)"),
        L_raw=P(L_engine_raw, "m", "frozen", "engine_mass L_total"),
        L_calibrated=P(eng["L_cal"] / 1e3, "m", "frozen", SRC_CL + f" (raw x K_L {AX['calibration']['K_L']:.3f})"),
        K_M=P(AX["calibration"]["K_M"], "-", "frozen", SRC_AXT), K_L=P(AX["calibration"]["K_L"], "-", "frozen", SRC_AXT),
        dry_raw=P(eng["raw"], "kg", "frozen", SRC_CL), dry_calibrated=P(eng["cal"], "kg", "frozen", SRC_CL),
        radial_gap_over_compressor=P(eng["D"] / 2e3 - comp["D_casing_mm"] / 2e3, "m", "derived",
                                     "engine OD radius minus compressor casing OD radius: the space the VG hardware has to live in")),
    vg_schedule=dict(
        vigv_design_swirl=P(22.4, "deg", "frozen", "docs/design_freeze_axial.md 1.3"),
        vigv_closure=P(cfg["vigv_closure_deg"], "deg", "frozen", SRC_OPF),
        bleed_fraction=P(cfg["bleed"], "-", "frozen", SRC_OPF), bleed_stage=P(cfg["bleed_stage"], "-", "frozen", SRC_OPF),
        bleed_close_speed=P(cfg["bleed_close"], "-", "frozen", SRC_OPF), a8_max=P(cfg["a8_max"], "-", "frozen", SRC_OPF)),
    vg_loads=vg_loads,
    vg_mass_allowance=dict(
        vigv_hardware=P(0.0901, "kg", "frozen", SRC_CL + " items (geometric estimate)"),
        vigv_servo=P(0.075, "kg", "frozen", SRC_CL + " (placeholder 75 g hobby servo)"),
        bleed_hardware=P(0.0465, "kg", "frozen", SRC_CL), bleed_servo=P(0.075, "kg", "frozen", SRC_CL),
        nozzle_hardware=P(0.2785, "kg", "frozen", SRC_CL), nozzle_servo=P(0.075, "kg", "frozen", SRC_CL),
        total=P(0.6401, "kg", "frozen", SRC_CL + " (the 0.64 kg raw allowance the CAD must test)")),
    materials=dict(rho=em.RHO, note="engine_mass.RHO; Ti-6Al-4V rotating/hot, Al 2760 casings and stators, AISI 321 hot casing, IN625 liners, IN-713LC turbine, 4340 shaft"),
)

json.dump(params, open(os.path.join(OUT, "axial_params.json"), "w"), indent=1, default=float)

print(f"Phase 6A parameter sheet: {TAG}")
print(f"  compressor blading {L_blading * 1e3:.2f} mm, section {L_comp_section * 1e3:.2f} mm, casing OD {comp['D_casing_mm']:.2f} mm")
print(f"  stage pitches (mm): " + ", ".join(f"{(stages[i + 1]['rotor']['x_le'] - stages[i]['rotor']['x_le']) * 1e3:.1f}" for i in range(len(stages) - 1)))
print(f"  engine OD {eng['D']:.2f} mm, raw length {L_engine_raw * 1e3:.1f} mm (calibrated {eng['L_cal']:.1f} mm)")
print(f"  radial gap over the compressor casing: {(eng['D'] / 2e3 - comp['D_casing_mm'] / 2e3) * 1e3:.2f} mm")
print(f"  bearings at x {x_brg_front * 1e3:.1f} / {x_brg_rear * 1e3:.1f} mm (span {(x_brg_rear - x_brg_front) * 1e3:.1f} mm)")
print(f"  nozzle r8 {r8 * 1e3:.1f} -> {r8_max * 1e3:.1f} mm at A8 x{cfg['a8_max']:.1f}")
print("\nVariable-geometry actuation loads (first-order):")
print(f"  VIGV   : {Z_igv:.0f} vanes, lift {L_v:.1f} N/vane, hinge {M_vane * 1e3:.1f} N mm/vane, ring force {F_ring_vigv:.0f} N, stroke {stroke_vigv * 1e3:.2f} mm")
print(f"  bleed  : port area {A_port * 1e4:.2f} cm2, dP {dP_bleed / 1e3:.0f} kPa, seal force {F_seal_bleed:.0f} N, valve torque {M_bleed:.2f} N m")
print(f"  nozzle : {N_FLAP} flaps {L_flap * 1e3:.1f} x {w_flap * 1e3:.1f} mm (wetted {w_wet_closed * 1e3:.1f} mm closed), turbine exit M {m5:.3f}")
print(f"           dP {dP_flap / 1e3:.0f} kPa, {F_flap:.0f} N/flap, hinge {M_h_flap:.2f} N m/flap")
print(f"           link {F_link_flap:.0f} N/flap, sync-ring axial force {F_sync_ring:.0f} N, stroke {stroke_nozzle * 1e3:.1f} mm")
print(f"           INVARIANTS: total hinge moment {M_hinge_total:.1f} N m over {math.degrees(theta_flap):.1f} deg = {W_nozzle:.1f} J of work")
