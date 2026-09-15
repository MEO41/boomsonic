"""Option B check 1: impeller stress of the corrected axial-centrifugal (AC) variants at 90 000 rpm, with the
SAME verified solvers, material, criteria and assumptions as the pure-centrifugal gate (impeller_stress_gate.py):
axisymmetric FE hub/disc (+ thermal gradient), Robinson burst criterion, Morley-plate exducer blade root with Kt 1.4.

Geometry: the Phase 3 TurboFlow impeller of each AC variant (data/phase3/trade_<tag>_fielded.json, case.comp.centrifugal),
scaled to the fielded engine by s = sqrt(W_fielded / W_tool) exactly as the trade scales it (arch_trade.scaled_comp),
at the design speed 90 000 rpm. Blades as in the gate: 12 main + 12 splitters from mid-meridian, mean thickness 1.2 mm,
-30 deg backsweep (the TurboFlow design value), linear taper t_root -> 0.8 mm. Back-face boss amplitude A scaled with r2
(A/r2 = 0, 0.1, 0.2, 0.3; the gate used 0-18 mm at r2 60 mm = 0-0.3 r2).
Thermal: eye T0 (fielded) -> 520 K exit, dT = (T_exit - T_eye) (r/r2)^n, n = 1, 2.
Usage: python impeller_check_ac.py
"""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, HERE)
import impeller_stress_gate as g
import axisym_fe as fe

E_HOT, ALPHA = 98e9, 9.2e-6
CASES = ["ax90000_opr4_t1150_ax2_pa2_cap_blk", "ax90000_opr4_t1150_ax1_pa1.5_cap_blk"]

def set_geometry(tag):
    d = json.load(open(os.path.join(ROOT, "data", "phase3", f"trade_{tag}_fielded.json")))
    comp = d["case"]["comp"]; cc = comp["centrifugal"]; imp = cc["geometry"]["impeller"]
    s = float(np.sqrt(d["eval"]["cycle"]["W_kgps"] / d["case"]["cycle"]["W_kgps"]))
    rpm = d["case"]["rpm"]
    g.RPM = rpm; g.W = rpm * np.pi / 30
    g.R2 = imp["radius_out"] * s; g.B2 = imp["width_out"] * s
    g.R1S = imp["radius_tip_in"] * s; g.R1H = imp["radius_hub_in"] * s
    g.L = imp["length_axial"] * s; g.LS = g.L - g.B2
    g.U2 = g.W * g.R2
    # fielded eye temperature: axial stages at the fielded efficiency (axicent_design: every stage x K_F)
    T01 = comp["axial"]["input"]["T01"]; pi_a = comp["pi_a"]; K_F = 0.70 / 0.794
    T_eye = T01 * (1 + (pi_a ** (0.4 / 1.4) - 1) / (comp["eta_ax"] * K_F))
    return dict(tag=tag, s=s, rpm=rpm, r2_mm=g.R2 * 1e3, b2_mm=g.B2 * 1e3, b2_r2=g.B2 / g.R2, r1s_mm=g.R1S * 1e3, r1h_mm=g.R1H * 1e3,
                L_mm=g.L * 1e3, U2=g.U2, U2_fielded_trade=comp["U2_fielded"], T_eye=T_eye, T_exit=d["eval"]["cycle"]["Tt3_K"])

def hub_case(r_bore, A, p, dT=None, E=110e9):
    orig = fe.solve_rotating
    def patched(*a, **k):
        k["E"] = E
        if dT is not None: k.update(dT=dT, alpha=ALPHA)
        return orig(*a, **k)
    fe.solve_rotating = patched
    try:
        return g.analyse_hub(r_bore, 0.003, A, p, omega=g.W)
    finally:
        fe.solve_rotating = orig

if __name__ == "__main__":
    out = {}
    for tag in CASES:
        geo = set_geometry(tag)
        print(f"\n=== {tag}: r2 {geo['r2_mm']:.1f} mm, b2 {geo['b2_mm']:.1f} mm (b2/r2 {geo['b2_r2']:.3f}), r1s {geo['r1s_mm']:.1f}, "
              f"U2 {geo['U2']:.0f} m/s (trade fielded U2 {geo['U2_fielded_trade']:.0f}), eye {geo['T_eye']:.0f} K -> exit {geo['T_exit']:.0f} K", flush=True)
        hubs = []
        for r_bore in (0.006, 0.0):
            for Af in (0.0, 0.1, 0.2, 0.3):
                for p in (1.0, 2.0):
                    if Af == 0.0 and p == 2.0: continue
                    d = hub_case(r_bore, Af * g.R2, p)
                    d["A_over_r2"] = Af; hubs.append(d)
        best = {rb: min([h for h in hubs if h["r_bore_mm"] == rb * 1e3], key=lambda h: h["vm_peak_MPa"]) for rb in (0.006, 0.0)}
        th = []
        for rb, h in best.items():
            for n in (1, 2):
                dT = (lambda n: (lambda r, z: (geo["T_exit"] - geo["T_eye"]) * np.clip(r / g.R2, 0, 1) ** n))(n)
                d = hub_case(rb, h["A_mm"] / 1e3, h["p"], dT=dT, E=E_HOT)
                th.append(dict(r_bore_mm=rb * 1e3, A_mm=h["A_mm"], p=h["p"], n=n, vm_MPa=d["vm_peak_MPa"], yield_MS=d["yield_MS"]))
            print(f"  hub r_bore {rb*1e3:.0f} mm best: A {h['A_mm']:.1f} mm p {h['p']:.0f}: vm {h['vm_peak_MPa']:.0f} MPa (yield MS {100*h['yield_MS']:+.0f} %), "
                  f"burst ratio {h['burst_ratio']:.2f}, mass {h['mass_total_kg']:.3f} kg; with thermal: "
                  + ", ".join(f"n{t['n']} {t['vm_MPa']:.0f} MPa ({100*t['yield_MS']:+.0f} %)" for t in th if t["r_bore_mm"] == rb * 1e3), flush=True)
        blades = []
        for tr in (1.5e-3, 2.5e-3, 3.5e-3, 5.0e-3, 7.0e-3):
            b = g.plate_root(tr); b.update(t_root_mm=tr * 1e3, blockage_root=24 * tr / (2 * np.pi * g.R2), blockage_mean=24 * (tr + 0.8e-3) / 2 / (2 * np.pi * g.R2))
            blades.append(b)
            print(f"  exducer root t {tr*1e3:.1f} mm: {b['sig_root_Kt']/1e6:6.0f} MPa (Kt 1.4)  blockage root {100*b['blockage_root']:.0f} % mean {100*b['blockage_mean']:.0f} %  tip defl {b['max_defl_mm']:.2f} mm", flush=True)
        # thickness needed for the 620 MPa minimum yield (interpolate in 1/t)
        ts = np.array([b["t_root_mm"] for b in blades]); ss = np.array([b["sig_root_Kt"] for b in blades]) / 1e6
        t_need = float(np.interp(g.FTY / 1e6, ss[::-1], ts[::-1])) if ss.min() < g.FTY / 1e6 < ss.max() else np.nan
        sens = []
        for beta in (10.0, 20.0, 30.0):
            for tr in (2.5e-3, 3.5e-3):
                sens.append(dict(beta2=beta, t_root_mm=tr * 1e3, sig_Kt_MPa=g.plate_root(tr, beta2=beta)["sig_root_Kt"] / 1e6))
        print(f"  root thickness for Fty 620 MPa: {t_need:.2f} mm; backsweep sensitivity:", [(s_["beta2"], s_["t_root_mm"], round(s_["sig_Kt_MPa"])) for s_ in sens], flush=True)
        inducer = 0.6 * g.RHO * g.W ** 2 * (g.R1S ** 2 - g.R1H ** 2) / 2 / 1e6
        print(f"  inducer blade root tension: {inducer:.0f} MPa", flush=True)
        out[tag] = dict(geometry=geo, hub_sweep=hubs, hub_best={str(k): v for k, v in best.items()}, thermal=th, exducer=blades,
                        t_root_for_yield_mm=t_need, backsweep_sensitivity=sens, inducer_root_MPa=inducer)
    json.dump(out, open(os.path.join(AXROOT, "data", "phase4_optionB_impeller.json"), "w"), indent=1, default=float)
