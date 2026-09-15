"""Option B check 2: low-speed operability of the corrected axial-centrifugal engine, with the same method as the
pure axial (operability.py): combined compressor map (ac_offdesign.ACCompressor -> axial_map.compressor_mapdata),
TurboFlow turbine map of the AC turbine, pyCycle design at the dash (OPR 4, T4 1150 K, fielded efficiencies), steady
running lines at SLS and at the dash, surge margins to the peak-PR (surge surrogate) line and the front-stage Howell
stall index along them.
Usage: python ac_operability.py <trade tag>
"""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
import ac_offdesign as acm, axial_map as am, axial_offdesign as ao
import cycle_model as cm, dash_cycle as dc
KG2LBM = am.KG2LBM
TAG = sys.argv[1]
NEGW = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0          # axial negative-incidence loss width (sensitivity)
CCMAP = sys.argv[3] if len(sys.argv) > 3 else None                # alternative centrifugal map file (sensitivity)
SUF = (f"_nw{NEGW:g}" if NEGW != 1.0 else "") + (("_" + os.path.basename(CCMAP).replace(".json", "").replace("centrifugal_map_" + TAG, "cc")) if CCMAP else "")
trade = json.load(open(os.path.join(ROOT, "data", "phase3", f"trade_{TAG}_fielded.json")))
case, ev = trade["case"], trade["eval"]
OPR, T4 = case["cycle"]["comp_PR"], case["cycle"]["Tt4_K"]
eta_c, eta_t = ev["eta_c"], ev["eta_t"]

c = acm.ACCompressor(TAG, neg_width=NEGW, cc_map=CCMAP)
dp = c.point(1.0, c.W_d)
print(f"combined design check: PR {dp['PR']:.4f} (design {OPR}), eta {dp['eta']:.4f} (Phase 3 tool {case['comp']['eta_overall']:.4f}); "
      f"axial PR {dp['PR_ax']:.3f}, cc PR {dp['PR_cc']:.3f} beta {dp['beta_cc']:.2f}", flush=True)
NS = (0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05)
lines = []
for N in NS:
    try:
        L = am.build_compressor_lines(c, Ns=(N,))[0]; sl = c.speed_line(N)
        L["peak_is_map_end"] = sl["peak_is_map_end"]; lines.append(L)
        print(f"  N {N:.2f}: W choke {L['W_choke']:.3f} peak W {L['W_peak']:.3f} PR {L['PR_peak']:.3f}{' (map end, not peaked)' if L['peak_is_map_end'] else ''} "
              f"| Howell W {L['W_howell']:.3f} ({L['row_howell']})", flush=True)
    except Exception as e:
        print(f"  N {N:.2f}: no line ({e})", flush=True)
json.dump(lines, open(os.path.join(AXROOT, "data", "phase4", f"comp_lines_{TAG}{SUF}.json"), "w"), default=float)
L1 = [l for l in lines if l["N"] == 1.0][0]
print(f"design-point SMN to peak {((L1['PR_peak']/L1['W_peak'])/(dp['PR']/c.W_d)-1)*100:.1f} %", flush=True)
cmap, R_d = am.compressor_mapdata(lines, c.W_d, c.T01, c.P01)
tdata, cover = am.turbine_mapdata(json.load(open(os.path.join(AXROOT, "data", "phase4", f"turbine_map_{TAG}.json"))))

def g(prob, n, u=None): return float(np.ravel(prob.get_val(n, units=u))[0])

def comp_state(Nc, Wc_lbm):
    W = Wc_lbm / KG2LBM * (c.P01 / 101325.0) / np.sqrt(c.T01 / 288.15)
    try: q = c.point(Nc, W)
    except ao.Choked: return None
    Ns = np.array([L["N"] for L in lines]); f = lambda k: float(np.interp(Nc, Ns, [L[k] for L in lines]))
    return dict(W_stack=W, PR_stack=q["PR"], stall_index=q["stall_index"], stall_row=q["stall_row"], beta_cc=q["beta_cc"],
                SM_peak=(f("PR_peak") / f("W_peak")) / (q["PR"] / W) - 1,
                SMW_peak=float(np.interp(W, [L["W_peak"] for L in lines], [L["PR_peak"] for L in lines])) / q["PR"] - 1)

def sweep(mn, alt, Ns, label):
    prob, mp = cm.build(od_points=[(mn, alt)], od_mode="N", comp_map=cmap, turb_map=tdata)
    d, _ = dc.design(OPR, T4, eta_c, eta_t, prob=prob)
    cm.set_design(prob, dc.M_DASH, dc.H_DASH, OPR, T4, eta_c, eta_t, Fn_N=500.0, duct_dPqP=d["duct"]["dPqP"], ram_recovery=d["ram_recovery"],
                  od_names=mp.od_names, od_mode="N")
    prob["DESIGN.balance.W"] = d["W_kgps"] / 0.45359237; prob.run_model()
    pt = mp.od_names[0]; Nd = g(prob, "DESIGN.Nmech", "rpm")
    prob.set_val(pt + ".fc.MN", max(mn, 1e-6)); prob.set_val(pt + ".fc.alt", alt, units="m"); prob.set_val(pt + ".inlet.ram_recovery", dc.normal_shock_recovery(mn))
    rows = []
    for N in Ns:
        prob.set_val(pt + ".Nmech", N * Nd, units="rpm"); prob.run_model()
        r = cm.read(prob, pt, eta_b=dc.ETA_B)
        if r["res"] >= 1e-4: prob.run_model(); r = cm.read(prob, pt, eta_b=dc.ETA_B)
        r["conv"] = r["res"] < 1e-4; r["N_pct"] = 100 * N; r["case"] = label
        for k in ("RlineMap", "NcMap", "WcMap"): r["comp_" + k] = g(prob, f"{pt}.comp.map.{k}")
        cs = comp_state(r["comp_NcMap"], r["comp_WcMap"]) if r["conv"] else None
        if cs: r.update(cs)
        rows.append(r)
        print(f"  {label} N {100*N:5.1f}%: conv {r['conv']} Fn {r['Fn_N']:7.1f} W {r['W_kgps']:.3f} PR {r['comp_PR']:.3f} T4 {r['Tt4_K']:6.1f} "
              f"Rline {r['comp_RlineMap']:.3f} Nc {r['comp_NcMap']:.3f} stall_idx {r.get('stall_index', np.nan):.3f} ({r.get('stall_row', '-')}) "
              f"beta_cc {r.get('beta_cc', np.nan):.2f} SMN {r.get('SM_peak', np.nan):+.3f} NPR {r['NPR']:.2f}", flush=True)
    return rows, d

if __name__ == "__main__":
    Ns = [1.0, 0.975, 0.95, 0.925, 0.9, 0.875, 0.85, 0.825, 0.8, 0.775, 0.75, 0.725, 0.7, 0.675, 0.65, 0.625, 0.6, 0.575, 0.55, 0.525, 0.5, 0.475, 0.45, 0.425, 0.4]
    sls, d = sweep(0.0, 0.0, Ns, "SLS")
    dash, _ = sweep(dc.M_DASH, dc.H_DASH, Ns[:13], "dash")
    pd.DataFrame(sls + dash).to_csv(os.path.join(AXROOT, "data", f"phase4_running_line_{TAG}{SUF}.csv"), index=False)
    json.dump(dict(tag=TAG, R_design=R_d, design_check=dp, lines=[{k: L[k] for k in ("N", "W_choke", "W_peak", "PR_peak", "W_howell", "PR_howell", "row_howell", "peak_is_map_end")} for L in lines],
                   turbine_cover=cover), open(os.path.join(AXROOT, "data", f"phase4_operability_{TAG}{SUF}.json"), "w"), indent=1, default=float)
