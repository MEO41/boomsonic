"""Phase 4 (centrifugal baseline): lateral rotordynamics of the Phase 3R engine rotor (ROSS 2.3.0, verified in
rotordynamics_verify.py; eigen-solvers and API criteria from rotordynamics.py / rotordynamics_damped.py).

Rotor (fielded engine, data/phase3r/cct_<tag>.json; nothing hard-coded except the layout rules):
* impeller: the Phase 3R stress-sized Ti-6Al-4V impeller (boreless hub, back-face boss A/r2 0.3, 12 + 12 blades at the
  sized thickness) from the verified axisymmetric FE body of impeller_stress_gate.analyse_hub: mass, Ip, Id and centre of
  mass from the FE quadrature. Overhung ahead of the front bearing; its hub is a stiff massless Ti link (OD 0.6 r2) from
  its centre of mass to the back face, where the stub shaft starts.
* shaft: AISI 4340 tube (ID/OD 0.5), OD swept 12-28 mm (the combustor hub radius Ri 20.9 mm leaves room for a ~30 mm
  tunnel); bearing journals 12 mm OD over +-10 mm at each bearing (keeps DN <= 0.9e6 at 75 000 rpm).
* turbine: IN-713LC Stodola disc + blades of the turbine designed at the fielded cycle (<tag>_ttf70_out.json), with
  engine_mass's disc law; overhung behind the rear bearing.
* +10 % on every disc's mass and inertias (engine_mass allowance), as in rotor_model.py.
Axial stations follow engine_mass's envelope: compressor section Lx + 0.5 r2 + 10 mm, combustor 1.15 L_liner, turbine
1.6 (c_NGV + c_rotor). Front bearing 10 mm behind the impeller back face (inside the diffuser hub); rear bearing under
the NGV (0.8 c_NGV behind the combustor exit) - the usual micro-turbojet layout (both bearings in the shaft tunnel).
Analyses: critical-speed map vs support stiffness and shaft OD (undamped, API 684 worst-case margins: >= 26 % above MCS,
>= 16 % below the minimum operating speed; MCS 105 %, minimum speed 35 % = the lowest steady speed of cc_mission), then
damped criticals and amplification factors with damped supports (API AF rules), mass properties and bearing loads.
Usage: python cc_rotor.py [tag]      outputs data/phase4r_rotordynamics.json|csv, plots/phase4r_rotor_*.png
"""
import os, sys, json, time, contextlib, io, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from ross_shim import rs
    import rotor_model as rm, rotordynamics as rd, rotordynamics_damped as rdd
    import engine_mass as em, impeller_stress as ist
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

TAG = sys.argv[1] if len(sys.argv) > 1 else "ce75000_opr4_t1150_b15_cap"
JOURNAL_OD, JOURNAL_LEN = 0.012, 0.020
K_HARD, K_SOFT, K_SOFT_MIN = rd.K_HARD, rd.K_SOFT, rd.K_SOFT_MIN
C_GUNTER = 876.0

def geometry(tag=TAG, A_over_r2=None, liner_factor=1.0):
    """A_over_r2: impeller back-face boss (default: the stress module's lowest-stress choice); liner_factor: combustor
    liner length relative to the Phase 3 rule L = 3 x annulus height (sets the bearing span)."""
    d = json.load(open(os.path.join(ROOT, "data", "phase3r", f"cct_{tag}.json"))); L = d["levels"]["fielded"]
    rpm = float(d["rpm"]); omega = rpm * np.pi / 30
    sg, s = L["stress_geo"], L["stress"]
    # impeller FE body (design speed; mass properties do not depend on speed)
    ist.set_geometry(rpm, sg["r2"], s["blade"]["b2_geo"], sg["r1s"], sg["r1h"], sg["L"], s["blade"]["t_mean_mm"] / 1e3)
    A = (s["disc"]["A_over_r2"] if A_over_r2 is None else A_over_r2) * sg["r2"]
    h = ist.g.analyse_hub(0.0, 0.003, A, 2.0, omega=ist.g.W)
    h_stress = dict(vm_mech_MCS_MPa=h["vm_peak_MPa"], burst_MCS=h["burst_ratio"], A_over_r2=A / sg["r2"])
    imp = dict(name="IMP", m=rm.ALLOW * h["mass_total_kg"], Ip=rm.ALLOW * h["Ip_kgm2"], Id=rm.ALLOW * h["Id_cg_kgm2"], x=h["z_cg_mm"] / 1e3,
               x_back=h["z_back_axis_mm"] / 1e3, r2=sg["r2"], m_FE=h["mass_total_kg"])
    # turbine designed at the fielded cycle
    tt = json.load(open(os.path.join(ROOT, "data", "phase3r", f"{tag}_ttf70_out.json"))); g = tt["geometry"]
    rh_in, rt_in = np.ravel(g["radius_hub_in"]), np.ravel(g["radius_tip_in"]); rh_out, rt_out = np.ravel(g["radius_hub_out"]), np.ravel(g["radius_tip_out"])
    chord, pitch, tmax = np.ravel(g["chord"]), np.ravel(g["pitch"]), np.ravel(g["maximum_thickness"])
    Z = 2 * np.pi * 0.5 * (rh_in + rt_in) / pitch; hb = 0.5 * ((rt_in - rh_in) + (rt_out - rh_out))
    m_tb = float(em.RHO["IN713"] * (Z * 0.7 * chord * tmax * hb)[1]); F = m_tb * omega ** 2 * (rh_out[1] + 0.5 * hb[1])
    m_td, Ip_td, Id_td, h0 = rm._profile_inertia(float(rh_out[1]), omega, em.RHO["IN713"], em.SIG["IN713"], F)
    Ip_tb, Id_tb = rm._blade_rod(m_tb, float(rh_out[1]), float(hb[1]))
    e = L["eval"]["engine"]; comb = L["eval"]["combustor"]["mean"]
    L_comp = e["comp_geo"]["L_mm"] / 1e3; x_t0 = L_comp + 1.15 * liner_factor * comb["L_liner_mm"] / 1e3
    turb = dict(name="T", m=rm.ALLOW * (m_td + m_tb), Ip=rm.ALLOW * (Ip_td + Ip_tb), Id=rm.ALLOW * (Id_td + Id_tb),
                x=x_t0 + 1.6 * chord[0] + 0.8 * chord[1], r_rim=float(rh_out[1]), m_disc=m_td, m_blades=m_tb)
    chk = dict(turbine_disc_engine_mass=e["items"]["turbine_disc"], turbine_disc_here=m_td, turbine_blades_engine_mass=e["items"]["turbine_blades"],
               turbine_blades_here=m_tb, impeller_engine_mass=e["items"]["impeller"], impeller_FE=h["mass_total_kg"])
    return dict(tag=tag, rpm=rpm, imp=imp, turb=turb, L_comp=L_comp, x_t0=x_t0, c_ngv=float(chord[0]), c_rot=float(chord[1]),
                Ri_comb_mm=comb["Ri_mm"], mass_check=chk, impeller_hub_stress=h_stress, liner_factor=liner_factor)

def build(geo, k=K_HARD, c=0.0, shaft_od=0.016, dx=0.008, journal_od=JOURNAL_OD, E_scale=1.0, id_ratio=0.5):
    stl = rs.Material(name="AISI4340", rho=em.RHO["steel"], E=205e9 * E_scale, Poisson=0.29)
    link = rs.Material(name="Ti_link", rho=1.0, E=110e9 * E_scale, Poisson=0.34)       # impeller hub: stiff, mass in the disc
    I, T = geo["imp"], geo["turb"]
    x_front = I["x_back"] + 0.010; x_rear = geo["x_t0"] + 0.8 * geo["c_ngv"]
    pts = sorted({I["x"], I["x_back"], x_front, x_rear, T["x"]})
    fine = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(np.ceil((b - a) / dx))); fine += list(np.linspace(a, b, n + 1)[1:])
    fine = np.array(fine); shaft = []
    for a, b in zip(fine[:-1], fine[1:]):
        xm = 0.5 * (a + b)
        if xm < I["x_back"]:
            shaft.append(rs.ShaftElement(L=b - a, idl=0.0, odl=0.6 * I["r2"] * 2, material=link))
        else:
            jr = abs(xm - x_front) < JOURNAL_LEN / 2 or abs(xm - x_rear) < JOURNAL_LEN / 2
            od = journal_od if jr else shaft_od
            shaft.append(rs.ShaftElement(L=b - a, idl=(0.5 * od if jr else id_ratio * shaft_od), odl=od, material=stl))
    node = lambda xx: int(np.argmin(np.abs(fine - xx)))
    disks = [rs.DiskElement(n=node(I["x"]), m=I["m"], Id=I["Id"], Ip=I["Ip"], tag="impeller"),
             rs.DiskElement(n=node(T["x"]), m=T["m"], Id=T["Id"], Ip=T["Ip"], tag="turbine")]
    brg = [rs.BearingElement(n=node(x_front), kxx=k, cxx=c, tag="front"), rs.BearingElement(n=node(x_rear), kxx=k, cxx=c, tag="rear")]
    info = dict(k=k, c=c, x_nodes=fine.tolist(), x_front=x_front, x_rear=x_rear, node_front=node(x_front), node_rear=node(x_rear),
                span=x_rear - x_front, overhang_imp=x_front - I["x"], overhang_turb=T["x"] - x_rear, shaft_od=shaft_od)
    return rs.Rotor(shaft, disks, brg), info

def mass_props(rot, geo, info):
    xs = [0.5 * (a + b) for a, b in zip(info["x_nodes"][:-1], info["x_nodes"][1:])]
    loads = [(el.m, xx) for el, xx in zip(rot.shaft_elements, xs)] + [(geo["imp"]["m"], geo["imp"]["x"]), (geo["turb"]["m"], geo["turb"]["x"])]
    W = sum(m for m, _ in loads) * 9.81; Mx = sum(m * 9.81 * x for m, x in loads); xf, xr = info["x_front"], info["x_rear"]
    R_r = (Mx - W * xf) / (xr - xf)
    Ip = sum(el.m * (el.odl ** 2 + el.idl ** 2) / 8 for el in rot.shaft_elements) + geo["imp"]["Ip"] + geo["turb"]["Ip"]
    return dict(m_rotor_kg=W / 9.81, Ip_kgm2=Ip, x_cg_mm=Mx / W * 1e3, R_front_N_1g=W - R_r, R_rear_N_1g=R_r,
                gyro_bearing_load_N_per_radps=Ip * geo["rpm"] * rd.RPM2RAD / info["span"])

def main():
    t0 = time.time(); geo = geometry(); rpm = geo["rpm"]; rmax = 1.7 * rpm
    out = dict(tag=TAG, rpm=rpm, idle_rpm=rd.IDLE * rpm, mcs_rpm=rd.MCS_F * rpm, geometry=geo, DN_journal=JOURNAL_OD * 1e3 * rpm * rd.MCS_F)
    print(f"impeller: m {geo['imp']['m']:.3f} kg (FE {geo['imp']['m_FE']:.3f}), Ip {geo['imp']['Ip']*1e4:.2f} e-4 kg m2, x_cg {geo['imp']['x']*1e3:.1f} mm, "
          f"back face {geo['imp']['x_back']*1e3:.1f} mm | turbine m {geo['turb']['m']:.3f} kg, Ip {geo['turb']['Ip']*1e4:.2f} e-4, x {geo['turb']['x']*1e3:.1f} mm", flush=True)
    rows = []
    for od in (0.012, 0.016, 0.020, 0.024, 0.028):
        for k in np.logspace(5.5, 9, 15):
            rot, info = build(geo, float(k), shaft_od=od)
            sp, fw, bw = rd.campbell(rot, rmax, n=24); cr = rd.forward_criticals(sp, fw)
            ty = [rd.bearing_energy_share(rot, info, v) for v in [min([(w, v) for w, dd, v in rd.lateral_modes(rot, c_) if dd == "Forward"], key=lambda t: abs(t[0] - c_))[1] for c_ in cr]]
            rows.append(dict(shaft_od_mm=od * 1e3, k=float(k), **{f"crit{i+1}_rpm": (cr[i] / rd.RPM2RAD if i < len(cr) else np.nan) for i in range(3)},
                             **{f"crit{i+1}_brg_energy": (ty[i] if i < len(ty) else np.nan) for i in range(3)}))
        print(f"  map OD {od*1e3:.0f} mm done ({time.time()-t0:.0f} s)", flush=True)
    cm = pd.DataFrame(rows); cm.to_csv(os.path.join(ROOT, "data", "phase4r_rotordynamics_critmap.csv"), index=False)
    out["cases"] = {}
    for od in (0.016, 0.020, 0.024):
        for kname, k in (("hard", K_HARD), ("soft", K_SOFT), ("softmin", K_SOFT_MIN)):
            rot, info = build(geo, k, shaft_od=od); mp = mass_props(rot, geo, info)
            sp, fw, bw = rd.campbell(rot, rmax, n=33); cr = [x / rd.RPM2RAD for x in rd.forward_criticals(sp, fw)]
            key = f"OD{od*1e3:.0f}_{kname}"
            out["cases"][key] = dict(k=k, shaft_od_mm=od * 1e3, crit_fwd_rpm=cr, verdict=rd.verdict(cr[:3], rpm), mass=mp,
                                     info={kk: v for kk, v in info.items() if kk != "x_nodes"},
                                     campbell=dict(rpm=(sp / rd.RPM2RAD).tolist(), fwd_rpm=(fw / rd.RPM2RAD).tolist(), bwd_rpm=(bw / rd.RPM2RAD).tolist()))
            print(f"  {key}: criticals {[round(x) for x in cr[:3]]} rpm -> " + ", ".join(f"{v['where']} ({'ok' if v['ok'] else 'FAIL'})" for v in out["cases"][key]["verdict"]), flush=True)
    # damped supports (squeeze-film / O-ring cartridges): API AF rules
    drows = []
    for od in (0.016, 0.020, 0.024):
        for k in (6e5, 1.0e6, 1.75e6, 3e6, 5e6, 1e7, K_HARD):
            for c in (C_GUNTER, 2000.0):
                rot, info = build(geo, k, c=c, shaft_od=od)
                crit = rdd.damped_criticals(rot, rmax, n=40); rows_, ok = rdd.assess(crit, rpm)
                drows.append(dict(shaft_od_mm=od * 1e3, k=k, c=c, ok=ok, crits=[(r["crit_rpm"], r["AF"]) for r in rows_], detail=rows_))
        print(f"  damped OD {od*1e3:.0f} mm done ({time.time()-t0:.0f} s)", flush=True)
    out["damped"] = drows
    pd.DataFrame([dict(shaft_od_mm=r["shaft_od_mm"], k=r["k"], c=r["c"], ok=r["ok"], crits=r["crits"]) for r in drows]).to_csv(
        os.path.join(ROOT, "data", "phase4r_rotordynamics_damped.csv"), index=False)
    json.dump(out, open(os.path.join(ROOT, "data", "phase4r_rotordynamics.json"), "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else float(o))
    plots(out, cm, geo)
    print(f"done in {time.time()-t0:.0f} s")

def plots(out, cm, geo):
    rpm = out["rpm"]; idle, mcs = out["idle_rpm"], out["mcs_rpm"]
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.8), sharey=True)
    for a, od in zip(ax, (16, 20, 24)):
        d = cm[cm.shaft_od_mm == od]
        for i, col in enumerate(("#1f77b4", "#d62728", "#2ca02c")):
            a.semilogx(d.k, d[f"crit{i+1}_rpm"] / 1e3, "-o", ms=3, color=col, label=f"critical {i+1}")
        a.axhspan(idle / 1e3, mcs / 1e3, color="0.85", label="35-105 % speed")
        a.axhline(mcs * 1.26 / 1e3, color="k", ls=":", lw=0.8, label="MCS + 26 %"); a.axhline(idle * 0.84 / 1e3, color="k", ls="-.", lw=0.8, label="min speed - 16 %")
        for kk, nm in ((K_SOFT_MIN, "6e5"), (K_SOFT, "1.75e6 damper"), (K_HARD, "1.9e7 ACBB")):
            a.axvline(kk, color="0.4", lw=0.8); a.text(kk * 1.1, 3, nm, rotation=90, fontsize=7)
        a.set_xlabel("bearing support stiffness k [N/m]"); a.set_title(f"shaft OD {od} mm (journals 12 mm)", fontsize=9); a.grid(alpha=.3); a.set_ylim(0, 1.7 * rpm / 1e3)
    ax[0].set_ylabel("forward synchronous critical [krpm]"); ax[0].legend(fontsize=7)
    fig.suptitle(f"Phase 4 critical-speed map, centrifugal engine rotor ({out['tag']}, undamped)", fontsize=9); fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "plots", "phase4r_rotor_critmap.png"), dpi=130); plt.close(fig)

if __name__ == "__main__":
    main()
