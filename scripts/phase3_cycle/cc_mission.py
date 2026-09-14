"""Phase 3R: off-design of a chosen centrifugal engine across the Phase 1 mission, with its REAL component maps
(run in .venv). Replaces the Phase 3 placeholder-map deck (engine_deck.py, A3.8).

Maps: TurboFlow centrifugal map of the designed stage (centrifugal_map.py, slip fixed) and TurboFlow turbine map
(turbine_map.py), both in data/phase3r/maps/; compressor surge surrogate = the peak of each speed line (method
benchmarked on the JetCat P400, cc_benchmark.py). pyCycle design point = the Phase 3R dash point at the fielded level
(maps scaled to it, as in the Phase 4 operability work).
  1. running lines (N mode) at SLS and at the dash: thrust, T4, EGT, surge margin SMN = (PR/W)_peak / (PR/W) - 1 at
     constant corrected speed; lowest steady speed at SLS (idle capability)
  2. max-thrust deck over Mach x altitude = min(100 % speed, T4 1150 K) as in engine_deck.py
  3. the Phase 2 sortie (mission_drag_polar.run) re-flown on that deck, with the calibrated engine diameter / length,
     TOGW as take-off mass, intake loss inside the cycle (flat 3 % A2.3 set to 0) and the real idle fuel flow
Usage: python cc_mission.py <tag>          outputs data/phase3r_mission_<tag>_*.csv / .json
"""
import os, sys, json, numpy as np, pandas as pd
from scipy.interpolate import RegularGridInterpolator
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase2_airframe"))
import cycle_model as cm, dash_cycle as dc
import ac_offdesign as acm, axial_map as am, axial_offdesign as ao
TAG = sys.argv[1]
D3R = os.path.join(ROOT, "data", "phase3r"); MAPS = os.path.join(D3R, "maps")
d = json.load(open(os.path.join(D3R, f"cct_{TAG}.json"))); L = d["levels"]["fielded"]; ev = L["eval"]
OPR, T4 = d["OPR"], 1150.0; eta_c, eta_t = ev["eta_c"], ev["eta_t"]
KG2LBM = am.KG2LBM
g = lambda prob, n, u=None: float(np.ravel(prob.get_val(n, units=u))[0])

c = acm.PureCC(os.path.join(MAPS, f"centrifugal_map_{TAG}.json"))
NS = tuple(sorted(set(round(l["N"], 3) for l in c.cc.lines)))
lines = []
for N in NS:
    try: lines.append(am.build_compressor_lines(c, Ns=(N,))[0])
    except Exception as e: print(f"  N {N}: no line ({e})", flush=True)
cmap, R_d = am.compressor_mapdata(lines, c.W_d, c.T01, c.P01)
L1 = [l for l in lines if l["N"] == 1.0][0]; dp = c.point(1.0, c.W_d)
SMN_design = (L1["PR_peak"] / L1["W_peak"]) / (dp["PR"] / c.W_d) - 1
print(f"compressor map: design PR {dp['PR']:.3f} (cycle OPR {OPR}), design R-line {R_d:.3f}, design SMN to peak {100*SMN_design:.1f} %"
      f"{' (peak = map end, true surge flow lower)' if L1['W_peak'] <= min(L1['W']) * 1.0001 else ''}", flush=True)
tdata, cover = am.turbine_mapdata(json.load(open(os.path.join(MAPS, f"turbine_map_{TAG}.json"))))

def smn(Nc, Wc_lbm):
    W = Wc_lbm / KG2LBM * (c.P01 / 101325.0) / np.sqrt(c.T01 / 288.15)
    try: q = c.point(Nc, W)
    except ao.Choked: return np.nan
    Ns = np.array([l["N"] for l in lines]); f = lambda k: float(np.interp(Nc, Ns, [l[k] for l in lines]))
    return (f("PR_peak") / f("W_peak")) / (q["PR"] / W) - 1

def build(mode, mn, alt):
    prob, mp = cm.build(od_points=[(mn, alt)], od_mode=mode, comp_map=cmap, turb_map=tdata)
    dd, _ = dc.design(OPR, T4, eta_c, eta_t, prob=prob)
    cm.set_design(prob, dc.M_DASH, dc.H_DASH, OPR, T4, eta_c, eta_t, Fn_N=500.0, duct_dPqP=dd["duct"]["dPqP"], ram_recovery=dd["ram_recovery"],
                  od_names=mp.od_names, od_mode=mode)
    prob["DESIGN.balance.W"] = dd["W_kgps"] / 0.45359237; prob.run_model()
    pt = mp.od_names[0]
    prob.set_val(pt + ".fc.MN", max(mn, 1e-6)); prob.set_val(pt + ".fc.alt", alt, units="m"); prob.set_val(pt + ".inlet.ram_recovery", dc.normal_shock_recovery(mn))
    return prob, pt, g(prob, "DESIGN.Nmech", "rpm"), dd

def solve(prob, pt):
    prob.run_model(); r = cm.read(prob, pt, eta_b=dc.ETA_B)
    if r["res"] >= 1e-4: prob.run_model(); r = cm.read(prob, pt, eta_b=dc.ETA_B)
    r["conv"] = r["res"] < 1e-4
    for k in ("RlineMap", "NcMap", "WcMap"): r["comp_" + k] = g(prob, f"{pt}.comp.map.{k}")
    r["SMN"] = smn(r["comp_NcMap"], r["comp_WcMap"]) if r["conv"] else np.nan
    return r

def running_line(mn, alt, Ns, label):
    prob, pt, Nd, _ = build("N", mn, alt); rows = []
    for N in Ns:
        prob.set_val(pt + ".Nmech", N * Nd, units="rpm"); r = solve(prob, pt); r.update(N_pct=100 * N, case=label)
        rows.append(r)
        print(f"  {label} N {100*N:5.1f}%: conv {r['conv']} Fn {r['Fn_N']:7.1f} W {r['W_kgps']:.3f} PR {r['comp_PR']:.3f} T4 {r['Tt4_K']:6.1f} "
              f"EGT {r['Tt5_K']-273.15:5.0f} C Rline {r['comp_RlineMap']:.3f} Nc {r['comp_NcMap']:.3f} SMN {r['SMN']:+.3f} NPR {r['NPR']:.2f}", flush=True)
    return rows

MACHS = [0.0, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0, 1.02, 1.05]
ALTS = [0.0, 300.0, 1000.0, 2500.0, 4000.0, 5000.0, 6000.0]
def deck():
    """max throttle = 100 % mechanical speed unless T4 exceeds its limit there; then the speed is reduced (secant on N
    in pyCycle N mode) until T4 = T4max. pyCycle's own T4 mode (speed balance) does not converge with these maps."""
    prob, pt, Nd, _ = build("N", 1.02, 5000.0)
    path = []
    for i, h in enumerate(ALTS[::-1]):                         # start at the design altitude side, snake through the grid
        path += [(m, h) for m in (MACHS[::-1] if i % 2 == 0 else MACHS)]
    rows = []
    for (m, h) in path:
        prob.set_val(pt + ".fc.MN", max(m, 1e-6)); prob.set_val(pt + ".fc.alt", h, units="m"); prob.set_val(pt + ".inlet.ram_recovery", dc.normal_shock_recovery(m))
        prob.set_val(pt + ".Nmech", Nd, units="rpm"); r = solve(prob, pt); binding = "N"; r100 = r
        if r["conv"] and r["Tt4_K"] > T4 + 0.5:
            binding = "T4"; n0, t0 = 1.0, r["Tt4_K"]; n1 = 0.98
            for _ in range(12):
                prob.set_val(pt + ".Nmech", n1 * Nd, units="rpm"); r = solve(prob, pt)
                if not r["conv"]: break
                t1 = r["Tt4_K"]
                if abs(t1 - T4) < 0.5: break
                n0, t0, n1 = n1, t1, float(np.clip(n1 - (t1 - T4) * (n1 - n0) / (t1 - t0) if t1 != t0 else n1 - 0.01, 0.8, 1.0))
        r["N_pct"] = 100 * r["Nmech"] / Nd
        rows.append(dict(MN=m, alt_m=h, Fn_N=r["Fn_N"] if r["conv"] else np.nan, Wf_kgps=r["Wf_kgps"] if r["conv"] else np.nan, W_kgps=r["W_kgps"],
                         T4_K=r["Tt4_K"], N_pct=r["N_pct"], SMN=r["SMN"], binding=binding, conv=r["conv"], Fn_at_100pct=r100["Fn_N"], T4_at_100pct=r100["Tt4_K"]))
    return pd.DataFrame(rows).sort_values(["alt_m", "MN"]).reset_index(drop=True)

def fly(deck_df, dash_throttle_only=False):
    import mission_drag_polar as mdp, airframe_model as afm
    D_e, L_e = L["engine_cal"]["D_engine_mm"] / 1e3, L["engine_cal"]["L_engine_mm"] / 1e3
    class Cfg(afm.Config):
        def __post_init__(self):
            super().__post_init__(); self.D_engine = D_e; self.L_engine = L_e
    mdp.Config = Cfg; mdp.INSTALL_LOSS = 0.0
    dk = deck_df.copy()
    for h in ALTS:                                                      # fill unconverged grid cells along Mach
        s = dk.alt_m == h
        for col in ("Fn_N", "Wf_kgps"):
            dk.loc[s, col] = dk.loc[s, col].interpolate(limit_direction="both")
    MS, HS = sorted(dk.MN.unique()), sorted(dk.alt_m.unique())
    grid = lambda col: np.array([[dk[(dk.MN == m) & (dk.alt_m == h)][col].iloc[0] for h in HS] for m in MS])
    mdp.Fn_i = RegularGridInterpolator((MS, HS), grid("Fn_N"), bounds_error=False, fill_value=None)
    mdp.Wf_i = RegularGridInterpolator((MS, HS), grid("Wf_kgps"), bounds_error=False, fill_value=None)
    return mdp

if __name__ == "__main__":
    Ns = [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.375, 0.35, 0.325, 0.3]
    sls = running_line(0.0, 0.0, Ns, "SLS")
    dash = running_line(dc.M_DASH, dc.H_DASH, Ns[:9], "dash")
    rl = pd.DataFrame(sls + dash); rl.to_csv(os.path.join(ROOT, "data", f"phase3r_mission_{TAG}_running_lines.csv"), index=False)
    ok = [r for r in sls if r["conv"] and np.isfinite(r["SMN"]) and r["SMN"] > 0 and r["Tt4_K"] <= T4 + 0.5]
    lowest = min(ok, key=lambda r: r["N_pct"]) if ok else None          # lowest steady speed within T4 and surge limits
    idle = min(ok, key=lambda r: r["Wf_kgps"]) if ok else None          # idle for fuel accounting: minimum-fuel steady point
    if len(sys.argv) > 2 and sys.argv[2] == "lines":             # operability comparison only
        json.dump(dict(tag=TAG, SMN_design_map=SMN_design, idle=idle, SLS_100=sls[0], dash_100=dash[0]),
                  open(os.path.join(ROOT, "data", f"phase3r_mission_{TAG}_lines.json"), "w"), indent=1, default=float)
        sys.exit(0)
    dk = deck(); dk.to_csv(os.path.join(ROOT, "data", f"phase3r_mission_{TAG}_deck.csv"), index=False)
    pd.set_option("display.width", 220); print(dk.round(3).to_string(index=False))
    mdp = fly(dk)
    wf_max_sls = float(mdp.Wf_i((0.0, 0.0)))
    if idle: mdp.IDLE_FRAC = idle["Wf_kgps"] / wf_max_sls
    # take-off mass: the trade's TOGW used the Phase 2 sortie fuel scaled by dash fuel flow; replace it by this sortie's fuel
    togw_trade, fuel_trade = L["airframe"]["TOGW_kg"], L["airframe"]["fuel_kg"]; togw = togw_trade
    for _ in range(4):
        s0 = mdp.run(0.30, E_WD=None, M0=togw)[0]
        togw_new = togw_trade - fuel_trade + s0["fuel_total_kg"]
        if abs(togw_new - togw) < 0.01: break
        togw = togw_new
    pt_ = lambda r: dict(N_pct=r["N_pct"], Fn_N=r["Fn_N"], Wf_kgps=r["Wf_kgps"], Wf_frac_of_max=r["Wf_kgps"] / sls[0]["Wf_kgps"], T4_K=r["Tt4_K"],
                         EGT_C=r["Tt5_K"] - 273.15, SMN=r["SMN"]) if r else None
    sls_max = dk[(dk.MN == 0.0) & (dk.alt_m == 0.0)].iloc[0]
    out = dict(tag=TAG, SMN_design_map=SMN_design, idle=pt_(idle), lowest_steady=pt_(lowest),
               SLS_100=dict((k, sls[0][k]) for k in ("Fn_N", "Tt4_K", "Wf_kgps", "SMN", "conv")),
               SLS_max_T4_limited=dict(Fn_N=sls_max.Fn_N, N_pct=sls_max.N_pct, T4_K=sls_max.T4_K, Wf_kgps=sls_max.Wf_kgps, SMN=sls_max.SMN),
               turbine_cover=cover, TOGW_trade=togw_trade, fuel_trade=fuel_trade, TOGW=togw, missions={})
    for E in ("nom", "hi"):
        import airframe_model as afm
        Ew = None if E == "nom" else max(3.0, max(1.8, mdp.Config(S_wing=0.30).E_geom()))
        r = mdp.run(0.30, E_WD=Ew, M0=togw)
        if r is None:
            out["missions"][E] = "INFEASIBLE"; print(E, "mission infeasible", flush=True); continue
        summ, seg = r; out["missions"][E] = dict(summary=summ, segments=seg)
        pd.DataFrame(seg).to_csv(os.path.join(ROOT, "data", f"phase3r_mission_{TAG}_segments_{E}.csv"), index=False)
        print(f"\nmission ({E} wave drag), TOGW {togw:.2f} kg:"); print(pd.DataFrame(seg).round(3).to_string(index=False))
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in summ.items()}, flush=True)
    json.dump(out, open(os.path.join(ROOT, "data", f"phase3r_mission_{TAG}.json"), "w"), indent=1, default=float)
