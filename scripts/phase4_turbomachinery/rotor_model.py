"""Conceptual lateral rotordynamic model (ROSS 2.3.0) of the pure-axial engine's rotating assembly.

ALL geometry and masses are derived from a Phase 3 trade file (data/phase3/trade_*_fielded.json)
through the same functions that produced the engine mass (arch_trade.scaled_comp + engine_mass):
nothing is hard-coded except the layout rules below, so the model re-runs on a corrected trade file.

Rotor construction (as implied by engine_mass.py):
* compressor: solid constant-stress (Stodola) Ti-6Al-4V discs, no bore (engine_mass integrates the
  disc from the rim to the axis), joined at the rim by a tie/spacer drum whose mass is engine_mass's
  'drum_ties' (10 % of discs + blades). The drum is modelled as a thin Ti shell at the disc rim
  radius, thickness from that mass. Blades: engine_mass volume Z x 0.7 c (t/c c) h, radial rods.
* shaft: 4340 steel tube, OD 16 / ID 8 mm (engine_mass), from the last compressor disc to the
  turbine disc; front stub (same tube) ahead of stage 1 when the front bearing is there.
* turbine: IN-713LC Stodola disc (300 MPa) + blades (engine_mass.turbine_mass), overhung.
* +10 % on every disc's mass and inertias: engine_mass's 'fasteners, seals, balancing' allowance.
Axial stations follow engine_mass's envelope: compressor section = axial length + 30 mm (15 mm each
end), stage pitch 1.25 (c_rotor + c_stator), combustor section 1.15 L_liner, turbine section
1.6 (c_NGV + c_rotor) with the rotor centred 1.6 c_NGV + 0.8 c_rotor from its start.
Layouts (2 rolling bearings, translational stiffness k, no moment stiffness):
  'A' straddle-mounted compressor, overhung turbine: front bearing 5 mm from the compressor front
      face (inlet hub), rear bearing under the NGV (0.8 c_NGV behind the combustor exit).
  'B' RC-model style, both bearings in the shaft tunnel: front bearing 15 mm behind the last
      compressor disc (compressor drum overhung forward), rear bearing as in A.
Variant drum=False replaces the Ti drum by the 16 mm steel shaft running through the compressor
(lower-bound stiffness, as if the discs were bored and threaded on a through-shaft).
"""
import os, sys, json, contextlib, io, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from ross_shim import rs
    import arch_trade as at
    import engine_mass as em

DEFAULT_TRADE = os.environ.get("P4_TRADE", os.path.join(ROOT, "data", "phase3", "trade_ax0_opr5_t1150_cap_blk_fielded.json"))
TI = dict(rho=em.RHO["Ti"], E=110e9, nu=0.34)          # Ti-6Al-4V (ATI data sheet ~16 Msi at RT -> 110 GPa used)
ST = dict(rho=em.RHO["steel"], E=205e9, nu=0.29)       # AISI 4340
SHAFT_OD, SHAFT_ID = 0.016, 0.008                      # engine_mass.engine
ALLOW = 1.10


def _profile_inertia(r_rim, omega, rho, sigma, F_rim):
    """mass, Ip, Id of the engine_mass constant-stress disc (same h(r) law, same rim-width rule)."""
    m, h0, h_rim = em.stodola_disc(r_rim, omega, rho, sigma, F_rim)
    r = np.linspace(0, r_rim, 400)
    h = h_rim * np.exp(rho * omega ** 2 * (r_rim ** 2 - r ** 2) / (2 * sigma))
    dm = rho * 2 * np.pi * r * h
    Ip = float(np.trapezoid(dm * r * r, r))
    Id = 0.5 * Ip + float(np.trapezoid(dm * h * h / 12.0, r))
    return float(np.trapezoid(dm, r)), Ip, Id, h0


def _blade_rod(m_b, r_h, h):
    Ip = m_b * (r_h ** 2 + r_h * h + h ** 2 / 3.0)
    return Ip, 0.5 * Ip


def geometry(trade=None):
    trade = trade or DEFAULT_TRADE
    d = json.load(open(trade)); case, ev = d["case"], d["eval"]
    assert case["kind"] == "axial", "rotor_model covers the pure-axial engine"
    s = float(np.sqrt(ev["cycle"]["W_kgps"] / case["cycle"]["W_kgps"]))
    comp = at.scaled_comp("axial", case["comp"], s)
    rpm = float(case["rpm"]); omega = rpm * np.pi / 30
    e = em.engine(ev["cycle"], "axial", comp, case["turb"], ev["combustor"]["mean"], rpm, turb_scale=s)
    assert abs(e["dry_mass_kg"] - ev["engine"]["dry_mass_kg"]) < 1e-6, "engine_mass does not reproduce the trade file"
    discs, x = [], 0.015
    for st in comp["stages"]:
        ro, sta = st["rotor"], st["stator"]
        m_b = em.RHO["Ti"] * ro["Z"] * 0.7 * ro["chord"] * (ro["tc"] * ro["chord"]) * ro["h"]
        F = m_b * omega ** 2 * (ro["r_hub"] + 0.5 * ro["h"])
        m_d, Ip_d, Id_d, h0 = _profile_inertia(ro["r_hub"], omega, em.RHO["Ti"], em.SIG["Ti"], F)
        Ip_b, Id_b = _blade_rod(m_b, ro["r_hub"], ro["h"])
        discs.append(dict(name=f"C{st['stage']}", x=x + 0.625 * ro["chord"], r_rim=ro["r_hub"], r_tip=ro["r_tip"], m_disc=m_d, m_blades=m_b,
                          m=ALLOW * (m_d + m_b), Ip=ALLOW * (Ip_d + Ip_b), Id=ALLOW * (Id_d + Id_b), bore_width=h0))
        x += 1.25 * (ro["chord"] + sta["chord"])
    L_comp = e["comp_geo"]["L_mm"] / 1e3
    m_ties = 0.1 * sum(dd["m_disc"] + dd["m_blades"] for dd in discs)
    g = case["turb"]["geometry"]
    rh_in = np.ravel(g["radius_hub_in"]) * s; rt_in = np.ravel(g["radius_tip_in"]) * s
    rh_out = np.ravel(g["radius_hub_out"]) * s; rt_out = np.ravel(g["radius_tip_out"]) * s
    chord = np.ravel(g["chord"]) * s; pitch = np.ravel(g["pitch"]) * s; tmax = np.ravel(g["maximum_thickness"]) * s
    Z = 2 * np.pi * 0.5 * (rh_in + rt_in) / pitch; hb = 0.5 * ((rt_in - rh_in) + (rt_out - rh_out))
    m_tb = float(em.RHO["IN713"] * (Z * 0.7 * chord * tmax * hb)[1])
    F = m_tb * omega ** 2 * (rh_out[1] + 0.5 * hb[1])
    m_td, Ip_td, Id_td, h0t = _profile_inertia(float(rh_out[1]), omega, em.RHO["IN713"], em.SIG["IN713"], F)
    Ip_tb, Id_tb = _blade_rod(m_tb, float(rh_out[1]), float(hb[1]))
    L_liner = ev["combustor"]["mean"]["L_liner_mm"] / 1e3
    x_t0 = L_comp + 1.15 * L_liner
    turbine = dict(name="T", x=x_t0 + 1.6 * chord[0] + 0.8 * chord[1], r_rim=float(rh_out[1]), r_tip=float(max(rt_in.max(), rt_out.max())),
                   m_disc=m_td, m_blades=m_tb, m=ALLOW * (m_td + m_tb), Ip=ALLOW * (Ip_td + Ip_tb), Id=ALLOW * (Id_td + Id_tb), bore_width=h0t)
    chk = dict(m_comp_discs=sum(dd["m_disc"] for dd in discs), em_rotor_discs=e["items"]["rotor_discs"],
               m_comp_blades=sum(dd["m_blades"] for dd in discs), em_rotor_blades=e["items"]["rotor_blades"],
               m_turb_disc=m_td, em_turbine_disc=e["items"]["turbine_disc"], m_turb_blades=m_tb, em_turbine_blades=e["items"]["turbine_blades"])
    return dict(trade=os.path.relpath(trade, ROOT), rpm=rpm, scale=s, discs=discs, turbine=turbine, m_ties=m_ties, L_comp=L_comp,
                x_t0=x_t0, c_ngv=float(chord[0]), c_rot=float(chord[1]), L_engine=e["L_engine_mm"] / 1e3, L_shaft_em=0.72 * e["L_engine_mm"] / 1e3,
                engine=dict(dry_mass_kg=e["dry_mass_kg"], D_mm=e["D_engine_mm"], L_mm=e["L_engine_mm"]), mass_check=chk)


def build(geo, layout="A", k=1e7, drum=True, shaft_od=SHAFT_OD, shaft_id=SHAFT_ID, E_scale=1.0, cxx=0.0, dx=0.010,
          t_drum=None, journal_od=None, journal_len=0.020):
    """t_drum: drum wall [m] (default: from engine_mass's drum_ties mass); journal_od: steel journal OD at the
    bearings (front stub and +-journal_len/2 around the rear bearing, ID kept) - lets a stiffer main shaft
    keep a small bearing bore (DN)."""
    ti = rs.Material(name="Ti64", rho=TI["rho"], E=TI["E"] * E_scale, Poisson=TI["nu"])
    stl = rs.Material(name="AISI4340", rho=ST["rho"], E=ST["E"] * E_scale, Poisson=ST["nu"])
    D = geo["discs"]; T = geo["turbine"]
    x1, x5 = D[0]["x"], D[-1]["x"]
    x_rear = geo["x_t0"] + 0.8 * geo["c_ngv"]
    x_front = 0.005 if layout == "A" else x5 + 0.015
    x_start = min(x_front, x1)
    pts = np.array(sorted({x_start, x_front, x_rear, T["x"]} | {dd["x"] for dd in D}))
    fine = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(np.ceil((b - a) / dx)))
        fine += list(np.linspace(a, b, n + 1)[1:])
    fine = np.array(fine)
    r_bar = np.mean([dd["r_rim"] for dd in D]); L_d = x5 - x1
    t_drum_mass = geo["m_ties"] / (TI["rho"] * 2 * np.pi * r_bar * L_d)
    t_drum = t_drum_mass if t_drum is None else t_drum
    shaft = []
    for a, b in zip(fine[:-1], fine[1:]):
        xm = 0.5 * (a + b)
        if drum and x1 < xm < x5:
            r = np.interp(xm, [dd["x"] for dd in D], [dd["r_rim"] for dd in D])
            shaft.append(rs.ShaftElement(L=b - a, idl=2 * (r - t_drum / 2), odl=2 * (r + t_drum / 2), material=ti))
        else:
            jr = journal_od is not None and (xm < x1 or abs(xm - x_rear) < journal_len / 2)
            od = journal_od if jr else shaft_od
            shaft.append(rs.ShaftElement(L=b - a, idl=min(shaft_id, 0.6 * od), odl=od, material=stl))
    node = lambda xx: int(np.argmin(np.abs(fine - xx)))
    disks = [rs.DiskElement(n=node(dd["x"]), m=dd["m"], Id=dd["Id"], Ip=dd["Ip"], tag=dd["name"]) for dd in D + [T]]
    brg = [rs.BearingElement(n=node(x_front), kxx=k, cxx=cxx, tag="front"), rs.BearingElement(n=node(x_rear), kxx=k, cxx=cxx, tag="rear")]
    rot = rs.Rotor(shaft, disks, brg)
    info = dict(layout=layout, k=k, drum=drum, x_nodes=fine.tolist(), x_front=x_front, x_rear=x_rear, t_drum_mm=t_drum * 1e3, t_drum_mass_model_mm=t_drum_mass * 1e3, journal_od=journal_od,
                node_front=node(x_front), node_rear=node(x_rear), span=x_rear - x_front, overhang_turbine=T["x"] - x_rear,
                overhang_comp=max(0.0, x_front - x1), shaft_od=shaft_od, shaft_id=shaft_id)
    return rot, info


def mass_props(rot, geo, info):
    m_sh = float(sum(el.m for el in rot.shaft_elements))
    Ip_sh = float(sum(el.m * (el.odl ** 2 + el.idl ** 2) / 8 for el in rot.shaft_elements))
    items = geo["discs"] + [geo["turbine"]]
    m = m_sh + sum(i["m"] for i in items); Ip = Ip_sh + sum(i["Ip"] for i in items)
    xs = [0.5 * (a + b) for a, b in zip(info["x_nodes"][:-1], info["x_nodes"][1:])]
    loads = [(el.m, xx) for el, xx in zip(rot.shaft_elements, xs)] + [(i["m"], i["x"]) for i in items]
    xf, xr = info["x_front"], info["x_rear"]
    W = sum(mm for mm, _ in loads) * 9.81; Mx = sum(mm * 9.81 * xx for mm, xx in loads)
    R_r = (Mx - W * xf) / (xr - xf); R_f = W - R_r
    return dict(m_rotor_kg=m, m_shaft_elements_kg=m_sh, Ip_kgm2=Ip, Ip_shaft_kgm2=Ip_sh, x_cg=Mx / W, R_front_N_1g=R_f, R_rear_N_1g=R_r)
