"""Phase 3 engine envelope + dry mass from component geometry and materials (no catalog lookup).

Inputs: cycle state (pyCycle), compressor design (TurboFlow centrifugal JSON or axial-design JSON),
turbine design (TurboFlow JSON, optionally scaled), combustor (theta-scaled, combustor_sizing.py).

Materials (densities from standard handbook values; allowables are conceptual design values):
  Ti-6Al-4V   4430 kg/m3  impeller / axial rotors (T3 ~500 K at the dash rules out Al 2618 at these stresses)
  Al 2618-T61 2760 kg/m3  diffuser plates, axial stators, compressor shroud and front casing
  AISI 321    7900 kg/m3  outer casing (hot section), nozzle cone, shaft tunnel
  Inconel 625 8440 kg/m3  combustor liners, vaporiser tubes
  IN-713LC    7910 kg/m3  NGV ring and turbine blisk (allowable 300 MPa for the short-life disc, ~1000 K)
  4340 steel  7850 kg/m3  shaft
Rotating discs are STRESS-SIZED: a constant-stress (Stodola) disc from the rim to the axis,
h(r) = h_rim exp(rho w^2 (r_rim^2 - r^2) / (2 sigma)), with the rim thickness set by the blade
pull (sigma_r,rim = F_blades / (2 pi r_rim h_rim) = sigma). Impeller hub is a solid of revolution
under a quarter-ellipse hub line plus a back-plate, checked against the solid-disc stress
(3+nu)/8 rho U2^2. Blades: Z x (0.7 c t) x h (airfoil area ~0.7 chord x thickness).
Allowance: +10 % fasteners, seals, lock-rings, balancing (applied at the end).
"""
import numpy as np

RHO = dict(Ti=4430.0, Al=2760.0, SS=7900.0, IN625=8440.0, IN713=7910.0, steel=7850.0)
SIG = dict(Ti=450e6, IN713=300e6)

def stodola_disc(r_rim, omega, rho, sigma, F_rim):
    """mass of a constant-stress disc (r = 0..r_rim) carrying a rim load F_rim [N] (total radial blade pull)."""
    h_rim = F_rim / (2 * np.pi * r_rim * sigma)
    h_rim = max(h_rim, 0.004)                                   # 4 mm minimum rim width (manufacturing)
    r = np.linspace(0, r_rim, 400)
    h = h_rim * np.exp(rho * omega ** 2 * (r_rim ** 2 - r ** 2) / (2 * sigma))
    return float(np.trapezoid(rho * 2 * np.pi * r * h, r)), float(h[0]), h_rim

def centrifugal_compressor_mass(cc, omega):
    g = cc["geometry"]; im = g["impeller"]; vd = g["vaned_diffuser"]
    r1h, r1s, r2, b2 = im["radius_hub_in"], im["radius_tip_in"], im["radius_out"], im["width_out"]
    Lx = im["length_axial"]; Z = im["number_of_blades"]
    # hub body: quarter-ellipse hub line from (x=0, r=r1h) to (x=Lx, r=r2), plus 0.06 r2 back-plate (solid of revolution)
    x = np.linspace(0, Lx, 200); rh = r1h + (r2 - r1h) * (1 - np.sqrt(np.clip(1 - (x / Lx) ** 2, 0, 1)))
    V_hub = np.trapezoid(np.pi * rh ** 2, x) + np.pi * r2 ** 2 * 0.06 * r2
    # blades: full + splitter equivalent Z main blades, mean thickness 1.2 mm, meridional length ~0.7 r2, mean height (r1s - r1h + b2)/2
    # Phase 3R designs carry Z_eff = Z + Z_split * split_frac (already splitter-equivalent), the physical/effective exit
    # width ratio 1/(1 - B2) and the stress-sized mean blade thickness; Phase 3 designs (no Z_eff key) keep the original
    # factor 1.5 and 1.2 mm.
    if "Z_eff" in cc:
        b2 = b2 * cc.get("b2_geo_ratio", 1.0)
        V_bl = cc["Z_eff"] * cc.get("t_blade_mean", 1.2e-3) * (0.70 * r2) * 0.5 * ((r1s - r1h) + b2)
    else:
        V_bl = Z * 1.5 * 1.2e-3 * (0.70 * r2) * 0.5 * ((r1s - r1h) + b2)     # factor 1.5: splitters
    m_imp = RHO["Ti"] * (V_hub + V_bl)
    U2 = omega * r2; sig_disc = (3 + 0.3) / 8 * RHO["Ti"] * U2 ** 2
    r3, r4 = g["vaneless_diffuser"]["radius_out"], vd["radius_out"]
    m_diff = RHO["Al"] * (np.pi * (r4 ** 2 - r1s ** 2) * 2 * 3e-3                                  # front shroud + back plate, 3 mm each
                          + vd["number_of_vanes"] * (r4 - r3) * 1.4 * b2 * 2.0e-3                  # radial vanes
                          + np.pi * (r4 ** 2 - (r4 - 1.2 * b2) ** 2) * 0.35 * (0.5 * r2) * 0.25)   # axial de-swirl ring (25 % solid)
    m_cover = RHO["Al"] * np.pi * (r1s + r2) * np.hypot(Lx, r2 - r1s) * 2.0e-3 + RHO["Al"] * np.pi * ((r1s + 0.012) ** 2 - r1s ** 2) * 0.03  # shroud + inlet lip
    return dict(impeller=m_imp, diffuser_deswirl=m_diff, shroud_inlet=m_cover), dict(D_mm=2e3 * (r4 + 3e-3), L_mm=1e3 * (Lx + 0.5 * r2 + 0.01),
                                                                                           U2=U2, sigma_disc_MPa=sig_disc / 1e6, r2=r2)

def axial_compressor_mass(ax, omega):
    m_rot = m_sta = m_disc = 0.0; det = []
    for s in ax["stages"]:
        ro, stt = s["rotor"], s["stator"]
        blade_V = ro["Z"] * 0.7 * ro["chord"] * (ro["tc"] * ro["chord"]) * ro["h"]
        m_b = RHO["Ti"] * blade_V
        F = m_b * omega ** 2 * (ro["r_hub"] + 0.5 * ro["h"])
        m_d, h0, hr = stodola_disc(ro["r_hub"], omega, RHO["Ti"], SIG["Ti"], F)
        m_s = RHO["Al"] * (stt["Z"] * 0.7 * stt["chord"] * stt["tc"] * stt["chord"] * stt["h"]
                           + 2 * np.pi * stt["r_hub"] * stt["chord"] * 2e-3)            # vanes + inner shroud band
        m_rot += m_b; m_disc += m_d; m_sta += m_s
        det.append(dict(stage=s["stage"], blades=m_b, disc=m_d, disc_bore_width_mm=h0 * 1e3, stator=m_s))
    r_tip = ax["r_tip_max"]; L = ax["length"]
    m_case = RHO["Al"] * 2 * np.pi * (r_tip + 0.00125) * L * 2.5e-3
    return dict(rotor_blades=m_rot, rotor_discs=m_disc, stators=m_sta, compressor_casing=m_case, drum_ties=0.1 * (m_disc + m_rot)), \
        dict(D_mm=2e3 * (r_tip + 0.25e-3 + 2.5e-3), L_mm=1e3 * (L + 0.03), stages=det)

def turbine_mass(tt, omega, scale=1.0):
    g = tt["geometry"]
    rh_in = np.ravel(g["radius_hub_in"]) * scale; rt_in = np.ravel(g["radius_tip_in"]) * scale
    rh_out = np.ravel(g["radius_hub_out"]) * scale; rt_out = np.ravel(g["radius_tip_out"]) * scale
    chord = np.ravel(g["chord"]) * scale; pitch = np.ravel(g["pitch"]) * scale; tmax = np.ravel(g["maximum_thickness"]) * scale
    Z = 2 * np.pi * 0.5 * (rh_in + rt_in) / pitch
    h = 0.5 * ((rt_in - rh_in) + (rt_out - rh_out))
    V_bl = Z * 0.7 * chord * tmax * h
    m_ngv_vanes = RHO["IN713"] * V_bl[0]; m_rotor_bl = RHO["IN713"] * V_bl[1]
    m_ngv_rings = RHO["IN713"] * 2 * np.pi * (rh_in[0] + rt_in[0]) * chord[0] * 2.5e-3
    F = m_rotor_bl * omega ** 2 * (rh_out[1] + 0.5 * h[1])
    m_disc, h0, hr = stodola_disc(float(rh_out[1]), omega, RHO["IN713"], SIG["IN713"], F)
    r_tip = float(max(rt_in.max(), rt_out.max()))
    m_shroud = RHO["IN713"] * 2 * np.pi * r_tip * (chord.sum() * 1.4) * 2.0e-3            # turbine shroud ring
    return dict(ngv_vanes=m_ngv_vanes, ngv_rings=m_ngv_rings, turbine_blades=m_rotor_bl, turbine_disc=m_disc, turbine_shroud=m_shroud), \
        dict(D_mm=2e3 * (r_tip + 0.3e-3 + 2.0e-3), L_mm=1e3 * chord.sum() * 1.6, r_tip=r_tip, disc_bore_width_mm=h0 * 1e3, Z=Z.tolist(), h_mm=(h * 1e3).tolist())

def engine(cycle, comp_kind, comp, turb, comb, rpm, turb_scale=1.0, shaft_od=0.016, shaft_id=0.008, tunnel_r=0.014, damper_kg=0.0):
    """shaft_od / shaft_id / tunnel_r / damper_kg: Phase 4 rotordynamic design overrides (defaults = the Phase 3 model)."""
    omega = rpm * np.pi / 30
    if comp_kind == "centrifugal":
        mc, gc = centrifugal_compressor_mass(comp, omega)
    elif comp_kind == "axicentrifugal":
        mca, gca = axial_compressor_mass(comp["axial"], omega)
        mcc, gcc = centrifugal_compressor_mass(comp["centrifugal"], omega)
        mc = {**{"ax_" + k: v for k, v in mca.items()}, **{"cc_" + k: v for k, v in mcc.items()},
              "transition_duct": RHO["Al"] * 2 * np.pi * comp["axial"]["r_tip_max"] * 0.015 * 1.5e-3}
        gc = dict(D_mm=max(gca["D_mm"], gcc["D_mm"]), L_mm=gca["L_mm"] + gcc["L_mm"] + 15.0, L_cc_mm=gcc["L_mm"],
                  U2=gcc["U2"], sigma_disc_MPa=gcc["sigma_disc_MPa"], D_axial_mm=gca["D_mm"], D_diffuser_mm=gcc["D_mm"])
    else:
        mc, gc = axial_compressor_mass(comp, omega)
    mt, gt = turbine_mass(turb, omega, turb_scale)
    Ro = comb["Ro_mm"] / 1e3; Ri = comb["Ri_mm"] / 1e3; Ll = comb["L_liner_mm"] / 1e3
    D_eng = max(gc["D_mm"], comb["OD_mm"], gt["D_mm"])                       # engine casing = largest component envelope
    R_case = D_eng / 2e3
    # liners: outer liner at ~0.90 Ro, inner at ~1.25 Ri, 0.5 mm; dome; 8 vaporiser tubes
    m_liner = RHO["IN625"] * (2 * np.pi * (0.90 * Ro) * Ll + 2 * np.pi * (1.25 * Ri) * Ll + np.pi * ((0.9 * Ro) ** 2 - (1.25 * Ri) ** 2)) * 0.5e-3 \
        + RHO["IN625"] * 8 * np.pi * 4e-3 * 0.6 * Ll * 0.3e-3
    L_total = gc["L_mm"] / 1e3 + Ll * 1.15 + gt["L_mm"] / 1e3 + 0.9 * gt["r_tip"]          # compressor + combustor + turbine + exhaust cone
    L_hot = Ll * 1.15 + gt["L_mm"] / 1e3
    L_cc_case = gc["L_mm"] if comp_kind == "centrifugal" else gc.get("L_cc_mm", 0.0)          # Al casing around the centrifugal stage
    m_case = RHO["SS"] * 2 * np.pi * R_case * L_hot * 0.6e-3 + RHO["Al"] * 2 * np.pi * R_case * (L_cc_case / 1e3) * 1.0e-3
    m_nozzle = RHO["SS"] * np.pi * (gt["r_tip"] + np.sqrt(cycle["A8_cm2"] / 1e4 / np.pi)) * np.hypot(0.9 * gt["r_tip"], gt["r_tip"] - np.sqrt(cycle["A8_cm2"] / 1e4 / np.pi)) * 0.5e-3 \
        + RHO["SS"] * np.pi * 0.6 * gt["r_tip"] * 0.9 * gt["r_tip"] * 0.5e-3                                                     # outer cone + inner tail cone
    L_shaft = L_total * 0.72
    m_shaft = RHO["steel"] * np.pi / 4 * (shaft_od ** 2 - shaft_id ** 2) * L_shaft
    m_tunnel = RHO["SS"] * 2 * np.pi * tunnel_r * L_shaft * 1.0e-3 + 0.12                 # shaft tunnel + 2 bearing housings/preload
    items = dict(**mc, **mt, combustor_liners=m_liner, outer_casing=m_case, nozzle_cones=m_nozzle, shaft=m_shaft, shaft_tunnel_bearing_housings=m_tunnel,
                 bearings_2x_hybrid=0.05, starter_motor=0.18, fuel_manifold_igniter=0.08)
    if damper_kg: items["bearing_dampers"] = damper_kg
    sub = sum(items.values()); items["fasteners_seals_balancing_10pct"] = 0.10 * sub
    return dict(items=items, dry_mass_kg=float(sum(items.values())), D_engine_mm=float(D_eng), L_engine_mm=float(L_total * 1e3),
                D_breakdown=dict(compressor=gc["D_mm"], combustor=comb["OD_mm"], turbine=gt["D_mm"]), comp_geo=gc, turb_geo=gt)
