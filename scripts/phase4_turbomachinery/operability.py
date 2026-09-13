"""Phase 4: low-speed operability of the pure-axial engine.

Steady running line (sea-level static and dash conditions) from pyCycle with the Phase 4 maps:
  * compressor: stage-stacking map of the axial compressor (axial_map.build_compressor_lines),
  * turbine: TurboFlow off-design map of the designed turbine (turbine_map.py),
replacing the placeholder NPSS maps. Design point = the Phase 3 dash point (M 1.02 / 5 km, Fn 500 N,
OPR 5, T4 1150 K, fielded efficiencies; pyCycle scales the maps to it).
Along the running line the compressor operating point is located on the stacking model, which gives
  * the first-row stall index (Howell stalling deflection; >= 1: that row is stalled),
  * the surge margin to the peak-pressure line (surrogate surge line), SM = (PR_s/Wc_s)/(PR/Wc) - 1
    at constant corrected speed (the SMN definition used by pyCycle / NPSS),
  * the stage-by-stage incidence picture.
Transient margin: at fixed speed, T4 is raised (pyCycle od_mode 'NT4', shaft power left unbalanced) until the
operating point reaches the stall / surge line; the excess shaft power sets the acceleration rate.
Usage: python operability.py <trade tag> [neg_width] [out suffix]
"""
import os, sys, json, subprocess, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
import axial_offdesign as ao, axial_map as am
import cycle_model as cm, dash_cycle as dc
NP1 = os.path.join(ROOT, ".venv-np1", "Scripts", "python.exe")
KG2LBM = am.KG2LBM
BLEED_CLOSE = 0.90          # handling bleed open at or below 90 % mechanical speed
TAG = sys.argv[1] if len(sys.argv) > 1 else "ax80000_opr5_t1150_cap_blk"
NEGW = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
SUF = sys.argv[3] if len(sys.argv) > 3 else ""
OUT = os.path.join(ROOT, "data", "phase4")
os.makedirs(OUT, exist_ok=True)

trade = json.load(open(os.path.join(ROOT, "data", "phase3", f"trade_{TAG}_fielded.json")))
case, ev = trade["case"], trade["eval"]
OPR, T4 = case["cycle"]["comp_PR"], case["cycle"]["Tt4_K"]
eta_c, eta_t = ev["eta_c"], ev["eta_t"]

# ---------------- maps ----------------
c = ao.Compressor(comp=case["comp"], neg_width=NEGW)
lines_file = os.path.join(OUT, f"comp_lines_{TAG}_nw{NEGW:g}.json")
if os.path.exists(lines_file):
    lines = json.load(open(lines_file))
else:
    lines = am.build_compressor_lines(c); json.dump(lines, open(lines_file, "w"))
cmap, R_d = am.compressor_mapdata(lines, c.W_d, c.T01, c.P01)
tmap_file = os.path.join(OUT, f"turbine_map_{TAG}.json")
if not os.path.exists(tmap_file):
    r = subprocess.run([NP1, os.path.join(HERE, "turbine_map.py"), os.path.join(ROOT, "data", "phase3", f"{TAG}_tt_out.json"), tmap_file], capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError(r.stderr[-1500:])
tmap = json.load(open(tmap_file))
tdata, cover = am.turbine_mapdata(tmap)
print("compressor map: design R-line", round(R_d, 3), "| turbine map PR_tt coverage per speed", [(n, round(a, 2), round(b, 2)) for n, a, b in cover], flush=True)

def line_at(N):
    """interpolate the peak (surge surrogate) and Howell lines at corrected speed N (fraction)."""
    Ns = np.array([L["N"] for L in lines])
    f = lambda key: float(np.interp(N, Ns, [L[key] for L in lines]))
    return dict(W_peak=f("W_peak"), PR_peak=f("PR_peak"), W_howell=f("W_howell"), PR_howell=f("PR_howell"), W_choke=f("W_choke"))

def comp_state(Nc, Wc_lbm, igv=None, lines_=None, bleed=None):
    """locate an operating point on the stacking model (design-inlet corrected terms).
    SM_peak: constant-speed margin to the peak-PR (surge surrogate) line, (PR_s/Wc_s)/(PR/Wc) - 1 (pyCycle SMN);
    SMW_peak: constant-flow margin dR/R = PR_s(Wc)/PR - 1 (definition in Rolls-Royce CN112081683A)."""
    lines_ = lines_ or lines
    W = Wc_lbm / KG2LBM * (c.P01 / 101325.0) / np.sqrt(c.T01 / 288.15)
    try:
        q = c.point(Nc, W, detail=True, igv=igv, bleed=bleed)
    except ao.Choked:
        return None
    Ns = np.array([L["N"] for L in lines_]); f = lambda key: float(np.interp(Nc, Ns, [L[key] for L in lines_]))
    SM_peak = (f("PR_peak") / f("W_peak")) / (q["PR"] / W) - 1
    SMW_peak = float(np.interp(W, [L["W_peak"] for L in lines_], [L["PR_peak"] for L in lines_])) / q["PR"] - 1
    inc = {f"i_R{r['stage']}": r["i_r"] for r in q["rows"]}
    si = {f"si_R{r['stage']}": r["stall_r"] for r in q["rows"]}
    return dict(W_stack=W, PR_stack=q["PR"], eta_stack=q["eta"], stall_index=q["stall_index"], stall_row=q["stall_row"], SM_peak=SM_peak, SMW_peak=SMW_peak, **inc, **si)

def igv_needed(Nc, W, target=0.95, a_max=70.0):
    """smallest stage-1 inlet swirl (variable IGV) that keeps every row below target x Howell stalling deflection."""
    for a in np.arange(c.ang["a1"], a_max + 1e-9, 0.5):
        try: q = c.point(Nc, W, igv=a)
        except ao.Choked: return np.nan
        if q["stall_index"] <= target: return float(a)
    return np.nan

# ---------------- pyCycle ----------------
def build(mode, points, cmap_=None, bleed=False):
    prob, mp = cm.build(od_points=points, od_mode=mode, comp_map=cmap_ or cmap, turb_map=tdata, comp_bleed=bleed)
    d, _ = dc.design(OPR, T4, eta_c, eta_t, prob=prob)
    cm.set_design(prob, dc.M_DASH, dc.H_DASH, OPR, T4, eta_c, eta_t, Fn_N=500.0, duct_dPqP=d["duct"]["dPqP"], ram_recovery=d["ram_recovery"],
                  od_names=mp.od_names, od_mode=mode)
    prob['DESIGN.balance.W'] = d["W_kgps"] / 0.45359237
    prob.run_model()
    return prob, mp, d

def g(prob, n, u=None): return float(np.ravel(prob.get_val(n, units=u))[0])

def read_od(prob, pt, Nd):
    r = cm.read(prob, pt, eta_b=dc.ETA_B)
    r["N_pct"] = 100 * r["Nmech"] / Nd
    for k in ("RlineMap", "NcMap", "WcMap", "PRmap", "effMap"):
        try: r["comp_" + k] = g(prob, f"{pt}.comp.map.{k}")
        except Exception: r["comp_" + k] = np.nan
    r["pwr_net_kW"] = g(prob, f"{pt}.shaft.pwr_net", "kW")
    r["conv"] = r["res"] < 1e-4
    return r

def sweep_speed(mn, alt, Ns, label, cmap_=None, sched=None, lines_=None, a8=1.0, bleed=None):
    """bleed: (stage_after, fraction, frac_P, frac_work) overboard bleed (map lines_ must be built with the same bleed)."""
    prob, mp, d = build("N", [(mn, alt)], cmap_, bleed=bleed is not None)
    pt = mp.od_names[0]; Nd = g(prob, "DESIGN.Nmech", "rpm")
    prob.set_val(pt + ".Nmech", Ns[0] * Nd, units="rpm")
    for a in np.linspace(1.0, a8, 7)[1:] if abs(a8 - 1.0) > 1e-9 else []:        # continuation in nozzle area at the first speed
        prob.set_val(pt + ".a8s.A8_scale", a); prob.run_model()
    prob.set_val(pt + ".a8s.A8_scale", a8)
    if bleed is not None:
        prob.set_val(pt + ".comp.sb:frac_P", bleed[2]); prob.set_val(pt + ".comp.sb:frac_work", bleed[3])
        for nm in ("frac_W", "frac_P", "frac_work"): prob.set_val("DESIGN.comp.sb:" + nm, 0.0)
    prob.set_val(pt + ".fc.MN", max(mn, 1e-6)); prob.set_val(pt + ".fc.alt", alt, units="m")
    prob.set_val(pt + ".inlet.ram_recovery", dc.normal_shock_recovery(mn))
    rows = []
    for N in Ns:
        prob.set_val(pt + ".Nmech", N * Nd, units="rpm")
        bl_open = bleed is not None and N <= BLEED_CLOSE
        if bleed is not None:
            cur = float(np.ravel(prob.get_val(pt + ".comp.sb:frac_W"))[0]); tgt = bleed[1] if bl_open else 0.0
            for fr in np.linspace(cur, tgt, 7)[1:] if abs(tgt - cur) > 1e-9 else [tgt]:   # continuation when the valve opens
                prob.set_val(pt + ".comp.sb:frac_W", fr); prob.run_model()
        prob.run_model()
        r = read_od(prob, pt, Nd)
        if not r["conv"]:
            prob.run_model(); r = read_od(prob, pt, Nd)
        igv = float(sched(r["comp_NcMap"])) if sched is not None else None
        cs = comp_state(r["comp_NcMap"], r["comp_WcMap"], igv=igv, lines_=lines_, bleed=bleed[:2] if bl_open else None) if r["conv"] else None
        r["igv_deg"] = igv if igv is not None else c.ang["a1"]
        if cs: r.update(cs)
        r["case"] = label; r["A8_scale"] = a8; rows.append(r)
        print(f"  {label} N {100*N:5.1f}%: conv {r['conv']} Fn {r['Fn_N']:7.1f} N  W {r['W_kgps']:.3f}  PR {r['comp_PR']:.3f}  T4 {r['Tt4_K']:6.1f}  "
              f"Rline {r['comp_RlineMap']:.3f}  Nc {r['comp_NcMap']:.3f}  stall_idx {r.get('stall_index', np.nan):.3f} ({r.get('stall_row', '-')})  "
              f"SM_peak {r.get('SM_peak', np.nan):+.3f}  NPR {r['NPR']:.2f}", flush=True)
    return rows, d

if __name__ == "__main__":
    Ns = [1.0, 0.975, 0.95, 0.925, 0.9, 0.875, 0.85, 0.825, 0.8, 0.775, 0.75, 0.725, 0.7, 0.675, 0.65, 0.625, 0.6, 0.575, 0.55, 0.525, 0.5, 0.475, 0.45, 0.425, 0.4, 0.375, 0.35]
    sls, d = sweep_speed(0.0, 0.0, Ns, "SLS")
    dash, _ = sweep_speed(dc.M_DASH, dc.H_DASH, Ns[:13], "dash")
    # ---- variable IGV: schedule the stage-1 swirl so that no row exceeds 0.95 x its Howell stalling deflection on the SLS line
    allrows = sls + dash; vig = []
    sched = None; lines_v = None
    base = sls
    for it in range(3):
        pts = [(r["comp_NcMap"], r["W_stack"]) for r in base if r.get("W_stack") is not None and np.isfinite(r.get("W_stack", np.nan))]
        need = [(n, igv_needed(n, w)) for n, w in pts]
        need = sorted([(n, a) for n, a in need if np.isfinite(a)])
        print(f"VIGV iteration {it}: required inlet swirl vs Nc:", [(round(n, 3), a) for n, a in need], flush=True)
        if not need: break
        nn = np.array([n for n, a in need]); aa = np.maximum.accumulate(np.array([a for n, a in need])[::-1])[::-1]   # non-increasing with speed
        prev = sched
        sched = (lambda nn, aa, prev: (lambda N: max(float(np.interp(N, nn, aa)), float(prev(N)) if prev else 0.0)))(nn, aa, prev)
        lines_v = am.build_compressor_lines(c, igv_sched=sched)
        cmap_v, _ = am.compressor_mapdata(lines_v, c.W_d, c.T01, c.P01)
        base, _ = sweep_speed(0.0, 0.0, Ns, f"SLS_VIGV{it}", cmap_=cmap_v, sched=sched, lines_=lines_v)
        allrows += base
        if all((r.get("stall_index", 9) <= 0.97) for r in base if r["conv"]): break
    if sched is not None:
        json.dump(dict(N=list(np.round(np.linspace(0.3, 1.05, 16), 3)), igv_deg=[sched(n) for n in np.linspace(0.3, 1.05, 16)], lines=lines_v),
                  open(os.path.join(OUT, f"vigv_{TAG}_nw{NEGW:g}{SUF}.json"), "w"), indent=1, default=float)
    df = pd.DataFrame(allrows)
    df.to_csv(os.path.join(ROOT, "data", f"phase4_running_line_{TAG}_nw{NEGW:g}{SUF}.csv"), index=False)
    json.dump(dict(tag=TAG, neg_width=NEGW, R_design=R_d, design=d, lines=[{k: L[k] for k in ("N", "W_choke", "W_peak", "PR_peak", "W_howell", "PR_howell", "row_howell")} for L in lines],
                   turbine_cover=cover, turbine_design_check=tmap["design"]),
              open(os.path.join(ROOT, "data", f"phase4_operability_{TAG}_nw{NEGW:g}{SUF}.json"), "w"), indent=1, default=float)
