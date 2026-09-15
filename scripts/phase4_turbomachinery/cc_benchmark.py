"""Method benchmark for the Phase 4 operability method: apply it unchanged to the Phase 3 model of a REAL engine that
is known to idle, the JetCat P400-PRO-LN (data/microturbojet_database.csv, jetcat.de: 98 000 rpm max, 30 000 rpm idle
= 31 %, idle thrust 14 N, EGT 480-750 C; Phase 3 validation model: PR 3.8, 0.67 kg/s, TurboFlow impeller and turbine,
fielded eta_c 0.70 / eta_t 0.75, T4 solved for 425 N at SLS).
Same chain as for the axial / AC engines: TurboFlow centrifugal map (centrifugal_map.py) -> compressor_mapdata with the
peak-PR line as surge surrogate; TurboFlow turbine map (turbine_map.py); pyCycle N-mode running line at SLS.
If the method predicts that this engine cannot run down to ~31 % speed, the method is pessimistic by that much.
Usage: python cc_benchmark.py [map suffix]
"""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
import ac_offdesign as acm, axial_map as am, axial_offdesign as ao
import cycle_model as cm
TAG = "val_P400-PRO-LN"; SUF = sys.argv[1] if len(sys.argv) > 1 else ""
# Phase 3R: P3_DATA=phase3r and MAP_DIR=data/phase3r/maps re-run the benchmark on the slip-fixed P400 model; output suffix _3r
_P3D = os.environ.get("P3_DATA", "phase3")
DDIR = _P3D if os.path.isabs(_P3D) else os.path.join(ROOT, "data", _P3D); MDIR = os.path.join(ROOT, os.environ.get("MAP_DIR", os.path.join("data", "phase4")))
OSUF = "_3r" if os.environ.get("P3_DATA") == "phase3r" else ""
e = json.load(open(os.path.join(DDIR, f"{TAG}_engine.json"))); cyc = e["cycle"]
c = acm.PureCC(os.path.join(MDIR, f"centrifugal_map_{TAG}{SUF}.json"))
NS = tuple(sorted(set(round(l["N"], 3) for l in c.cc.lines)))
lines = []
for N in NS:
    try:
        L = am.build_compressor_lines(c, Ns=(N,))[0]; lines.append(L)
        print(f"  N {N:.2f}: W choke {L['W_choke']:.3f} peak W {L['W_peak']:.3f} PR {L['PR_peak']:.3f}", flush=True)
    except Exception as ex:
        print(f"  N {N:.2f}: no line ({ex})", flush=True)
cmap, R_d = am.compressor_mapdata(lines, c.W_d, c.T01, c.P01)
L1 = [l for l in lines if l["N"] == 1.0][0]; dp = c.point(1.0, c.W_d)
print(f"design check PR {dp['PR']:.3f} (3.8), design SMN to peak {((L1['PR_peak']/L1['W_peak'])/(dp['PR']/c.W_d)-1)*100:.1f} %", flush=True)
tdata, cover = am.turbine_mapdata(json.load(open(os.path.join(MDIR, f"turbine_map_{TAG}.json"))))
g = lambda prob, n, u=None: float(np.ravel(prob.get_val(n, units=u))[0])
prob, mp = cm.build(od_points=[(0.0, 0.0)], od_mode="N", design_W="fixed", comp_map=cmap, turb_map=tdata)
cm.set_design(prob, 0.0, 0.0, cyc["OPR"], cyc["Tt4_K"], 0.70, 0.75, W_kgps=cyc["W_kgps"], od_names=mp.od_names, od_mode="N")
prob.run_model()
d = cm.read(prob, "DESIGN", eta_b=0.95); print(f"design: Fn {d['Fn_N']:.1f} N (published 425), T4 {d['Tt4_K']:.0f} K, W {d['W_kgps']:.3f}", flush=True)
pt = "OD0"; Nd = g(prob, "DESIGN.Nmech", "rpm"); rows = []
for N in [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.375, 0.35, 0.325, 0.31, 0.3]:
    prob.set_val(pt + ".Nmech", N * Nd, units="rpm"); prob.run_model()
    r = cm.read(prob, pt, eta_b=0.95)
    if r["res"] >= 1e-4: prob.run_model(); r = cm.read(prob, pt, eta_b=0.95)
    r["conv"] = r["res"] < 1e-4; r["N_pct"] = 100 * N
    for k in ("RlineMap", "NcMap", "WcMap"): r["comp_" + k] = g(prob, f"{pt}.comp.map.{k}")
    if r["conv"]:
        W = r["comp_WcMap"] / am.KG2LBM; q = None
        try: q = c.point(r["comp_NcMap"], W)
        except ao.Choked: pass
        if q:
            Ns_ = np.array([l["N"] for l in lines]); f = lambda k: float(np.interp(r["comp_NcMap"], Ns_, [l[k] for l in lines]))
            r["SM_peak"] = (f("PR_peak") / f("W_peak")) / (q["PR"] / W) - 1
    rows.append(r)
    print(f"  SLS N {100*N:5.1f}% ({N*98000:6.0f} rpm): conv {r['conv']} Fn {r['Fn_N']:7.1f} N  W {r['W_kgps']:.3f}  PR {r['comp_PR']:.3f}  T4 {r['Tt4_K']:6.1f}  "
          f"EGT {r['Tt5_K']-273.15:6.0f} C  Rline {r['comp_RlineMap']:.3f}  SMN {r.get('SM_peak', np.nan):+.3f}", flush=True)
pd.DataFrame(rows).to_csv(os.path.join(ROOT, "data", f"phase4_benchmark_P400{SUF}{OSUF}.csv"), index=False)
