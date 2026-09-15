"""Phase 4A: low-speed operability of the refreshed pure axial with COMBINED variable geometry (run in .venv).

Phase 4 (operability.py, docs/phase4_operability.md) tested a variable IGV, an interstage bleed and a larger nozzle ONE
AT A TIME on the Phase 3 axial and found no single remedy below ~65-80 % speed. Option A (D4.4) needs them together.
This script schedules all three on the refreshed design (data/phase3ax/axt_<tag>.json, Phase 3A-R):
  * compressor: the stage-stacking map of the fielded blading (axial_offdesign.fielded: triangles rebuilt at the
    sizing efficiency, stage losses calibrated so the design point gives the fielded efficiency, the debit carried as
    a constant extra loss; Howell stall unchanged; R4.1 open);
  * turbine: TurboFlow off-design map of the fielded turbine (turbine_map.py; one process per speed line as in 3R);
  * pyCycle running lines at SLS (and the dash), design point = the fielded dash point;
  * VIGV: stage-1 inlet swirl scheduled on corrected speed, the smallest swirl keeping every row <= 0.95 x its Howell
    stalling deflection on the running line (iterated with the map, as Phase 4);
  * start / handling bleed: overboard after stage K (port pressure and work fractions from the design point), open at or
    below N_b = 95 % mechanical speed (AXOP_VG_OPEN; Phase 4 used 90 %, below the first fixed-geometry failure);
  * variable nozzle: A8 / A8_design = 1 above N_b, rising linearly to a8_max at 40 % (scheduled on speed).
Acceptance of a steady point (the Phase 4 criteria): converged, T4 <= 1150 K, no row beyond its Howell stalling
deflection (stall index <= 1), constant-speed margin to the peak-PR line SM >= 10 % (the transient half of the ~20 %
HP-compressor requirement). "Idle" = the lowest speed from which every point up to 100 % is acceptable.
Usage: python ax_operability.py <tag> [search | one <vigv closure deg, 0 = none> <bleed frac> <a8_max> | final <same>]
       (adopted: AXOP_A8_N=0.80 ... final 15 0.10 2.0)
Outputs: data/phase4ax/operability_<tag>_*.csv / .json
"""
import os, sys, json, glob, subprocess, itertools, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
import axial_offdesign as ao, axial_map as am, cycle_model as cm, dash_cycle as dc
NP1 = os.path.join(ROOT, ".venv-np1", "Scripts", "python.exe")
TAG = sys.argv[1]; MODE = sys.argv[2] if len(sys.argv) > 2 else "search"
OUT = os.path.join(AXROOT, "data", "phase4ax"); os.makedirs(OUT, exist_ok=True)
AX = json.load(open(os.path.join(AXROOT, "data", "phase3ax", f"axt_{TAG}.json")))
F = AX["levels"]["fielded"]; COMP = F["comp"]; CYC = F["eval"]["cycle"]
OPR, T4, ETA_C, ETA_T = CYC["comp_PR"], CYC["Tt4_K"], F["eval"]["eta_c"], F["eval"]["eta_t"]
# bleed open / nozzle ramp start: 95 % mechanical speed. The Phase 4 setting (90 %) acts below the point where the
# fixed-geometry line first fails (92.5 %, SM 9.2 %), so it could not help there (first Phase 4A batch).
BLEED_CLOSE, K_BLEED, SM_MIN, T4_MAX = float(os.environ.get("AXOP_VG_OPEN", 0.95)), 3, 0.10, 1150.0
NS = [1.0, 0.975, 0.95, 0.925, 0.9, 0.875, 0.85, 0.825, 0.8, 0.775, 0.75, 0.725, 0.7, 0.675, 0.65, 0.625, 0.6, 0.575, 0.55, 0.525, 0.5, 0.475, 0.45, 0.425, 0.4]

c = ao.fielded(COMP, ETA_C)          # triangles at the sizing efficiency, losses calibrated to the fielded efficiency (split)
# ---------------- turbine map (TurboFlow, one process per speed line; cached) ----------------
tt_file = os.path.join(AXROOT, "data", "phase3ax", f"{TAG}_ttf_out.json")
tmap_file = os.path.join(OUT, f"turbine_map_{TAG}.json")
if not os.path.exists(tmap_file):
    r = subprocess.run([NP1, os.path.join(ROOT, "scripts", "phase4_turbomachinery", "turbine_map.py"), tt_file, tmap_file], capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError(r.stderr[-1500:])
tmap = json.load(open(tmap_file)); tdata, cover = am.turbine_mapdata(tmap)

A8_N = float(os.environ.get("AXOP_A8_N", 0.40))       # speed at which the nozzle reaches a8_max (idle-thrust study: 0.80)
def a8_sched(a8_max):
    """A8 / A8_design: 1 above BLEED_CLOSE, linear to a8_max at A8_N speed (held below)."""
    return lambda N: 1.0 if N >= BLEED_CLOSE else 1.0 + (a8_max - 1.0) * min(1.0, (BLEED_CLOSE - N) / (BLEED_CLOSE - A8_N))

def bleed_port():
    dp = c.point(1.0, c.W_d, detail=True)
    P3 = np.prod([r["PR"] for r in dp["rows"][:K_BLEED]])
    return (P3 - 1) / (dp["PR"] - 1), sum(r["dT0"] for r in dp["rows"][:K_BLEED]) / sum(r["dT0"] for r in dp["rows"])
FRAC_P, FRAC_WORK = bleed_port()

def build(cmap, bleed):
    # the off-design point starts AT the design flight condition and is marched to the target (goto): at eta_c 0.709 a
    # direct jump from the dash design state to SLS diverges (NaN) even with the Phase 4 maps (found in Phase 4A)
    prob, mp = cm.build(od_points=[(dc.M_DASH, dc.H_DASH)], od_mode="N", comp_map=cmap, turb_map=tdata, comp_bleed=bleed)
    d, _ = dc.design(OPR, T4, ETA_C, ETA_T, prob=prob)
    cm.set_design(prob, dc.M_DASH, dc.H_DASH, OPR, T4, ETA_C, ETA_T, Fn_N=500.0, duct_dPqP=d["duct"]["dPqP"], ram_recovery=d["ram_recovery"],
                  od_names=mp.od_names, od_mode="N")
    prob['DESIGN.balance.W'] = d["W_kgps"] / 0.45359237
    prob.set_val(mp.od_names[0] + ".Nmech", g(prob, "DESIGN.Nmech", "rpm"), units="rpm"); prob.run_model()
    cm.seed_od_from_design(prob, mp.od_names[0])        # the default OD guesses diverge at eta_c 0.709 (found in Phase 4A)
    return prob, mp, d

def goto(prob, pt, mn, alt, n=10):
    """march the off-design point in flight condition from where it is to (mn, alt)."""
    m0 = g(prob, pt + ".fc.MN"); h0 = g(prob, pt + ".fc.alt", "m")
    for s in np.linspace(0, 1, n + 1)[1:]:
        m = m0 + s * (mn - m0); h = h0 + s * (alt - h0)
        prob.set_val(pt + ".fc.MN", max(m, 1e-6)); prob.set_val(pt + ".fc.alt", h, units="m"); prob.set_val(pt + ".inlet.ram_recovery", dc.normal_shock_recovery(m))
        prob.run_model()

def g(prob, n, u=None): return float(np.ravel(prob.get_val(n, units=u))[0])

def comp_state(Nc, Wc_lbm, lines, igv, bleed):
    W = Wc_lbm / am.KG2LBM * (c.P01 / 101325.0) / np.sqrt(c.T01 / 288.15)
    try: q = c.point(Nc, W, detail=True, igv=igv, bleed=bleed)
    except ao.Choked: return None
    Ns = np.array([L["N"] for L in lines]); f = lambda key: float(np.interp(Nc, Ns, [L[key] for L in lines]))
    return dict(W_stack=W, PR_stack=q["PR"], stall_index=q["stall_index"], stall_row=q["stall_row"], SM_peak=(f("PR_peak") / f("W_peak")) / (q["PR"] / W) - 1)

def sweep(mn, alt, label, vigv=None, bleed_f=0.0, a8_max=1.0, lines=None, cmap=None):
    bleed = bleed_f > 0
    prob, mp, d = build(cmap, bleed); pt = mp.od_names[0]; Nd = g(prob, "DESIGN.Nmech", "rpm"); a8 = a8_sched(a8_max)
    if bleed:
        prob.set_val(pt + ".comp.sb:frac_P", FRAC_P); prob.set_val(pt + ".comp.sb:frac_work", FRAC_WORK)
        for nm in ("frac_W", "frac_P", "frac_work"): prob.set_val("DESIGN.comp.sb:" + nm, 0.0)
    goto(prob, pt, mn, alt)
    rows = []
    for N in NS:
        prob.set_val(pt + ".Nmech", N * Nd, units="rpm")
        tgt_b = bleed_f if (bleed and N <= BLEED_CLOSE) else 0.0; tgt_a = a8(N)
        cur_b = float(np.ravel(prob.get_val(pt + ".comp.sb:frac_W"))[0]) if bleed else 0.0; cur_a = float(np.ravel(prob.get_val(pt + ".a8s.A8_scale"))[0])
        def run_safe():
            """OpenMDAO can raise (NaN in the thermo tables) instead of returning unconverged: treat as unconverged."""
            try: prob.run_model(); return True
            except Exception: return False
        for s in np.linspace(0, 1, 6)[1:]:                                              # continuation in valve / nozzle position
            if bleed: prob.set_val(pt + ".comp.sb:frac_W", cur_b + s * (tgt_b - cur_b))
            prob.set_val(pt + ".a8s.A8_scale", cur_a + s * (tgt_a - cur_a))
            if abs(tgt_b - cur_b) > 1e-9 or abs(tgt_a - cur_a) > 1e-9: run_safe()
        okrun = run_safe()
        try: r = cm.read(prob, pt, eta_b=dc.ETA_B); r["conv"] = okrun and r["res"] < 1e-4
        except Exception: r = dict(res=np.nan, conv=False, Fn_N=np.nan, Tt4_K=np.nan, Wf_kgps=np.nan, Nmech=N * Nd, W_kgps=np.nan)
        if not r["conv"]:
            okrun = run_safe()
            try: r = cm.read(prob, pt, eta_b=dc.ETA_B); r["conv"] = okrun and r["res"] < 1e-4
            except Exception: r = dict(res=np.nan, conv=False, Fn_N=np.nan, Tt4_K=np.nan, Wf_kgps=np.nan, Nmech=N * Nd, W_kgps=np.nan)
        if not r["conv"]:                                     # recover the solver state for the next (lower) speed
            try: cm.seed_od_from_design(prob, pt)
            except Exception: pass
        r["N_pct"] = 100 * r["Nmech"] / Nd
        for k in ("NcMap", "WcMap"): r["comp_" + k] = g(prob, f"{pt}.comp.map.{k}")
        igv = float(vigv(r["comp_NcMap"])) if vigv is not None else None
        cs = comp_state(r["comp_NcMap"], r["comp_WcMap"], lines, igv, (K_BLEED, tgt_b) if tgt_b > 0 else None) if r["conv"] else None
        if cs: r.update(cs)
        r.update(case=label, igv_deg=igv if igv is not None else c.ang["a1"], bleed=tgt_b, A8_scale=tgt_a,
                 ok=bool(r["conv"] and cs is not None and r["Tt4_K"] <= T4_MAX + 0.5 and cs["stall_index"] <= 1.0 and cs["SM_peak"] >= SM_MIN))
        rows.append(r)
    return rows

def idle_of(rows):
    """lowest speed from which every point up to the maximum-throttle speed is acceptable. Points above the T4 limit
    at the top of the line are beyond maximum throttle (the engine is T4-limited there, as in the deck) and skipped."""
    rows = sorted(rows, key=lambda r: -r["N_pct"]); low = None; i = 0
    while i < len(rows) and rows[i]["conv"] and rows[i]["Tt4_K"] > T4_MAX + 0.5: i += 1
    for r in rows[i:]:
        if not r["ok"]: break
        low = r["N_pct"]
    return low

def lines_for(vigv, bleed_f):
    bs = (lambda N, f=bleed_f: (K_BLEED, f) if N <= BLEED_CLOSE + 1e-9 else None) if bleed_f > 0 else None
    L = am.build_compressor_lines(c, igv_sched=vigv, bleed_sched=bs); cm_, _ = am.compressor_mapdata(L, c.W_d, c.T01, c.P01)
    return L, cm_

def vigv_linear(delta):
    """scheduled VIGV closure: design swirl at or above BLEED_CLOSE, closing linearly by delta [deg] at 60 % speed
    (held below). The Phase 4 stall-index-driven schedule never closed the IGV here, because the binding limit is the
    surge-surrogate margin, not rotor-1 stall (first Phase 4A batch)."""
    a1 = c.ang["a1"]
    return lambda N: a1 + delta * float(np.clip((BLEED_CLOSE - N) / (BLEED_CLOSE - 0.60), 0.0, 1.0))

def run_config(use_vigv, bleed_f, a8_max, label):
    if use_vigv and use_vigv > 1.5:                      # use_vigv = closure delta in degrees: scheduled VIGV
        vigv = vigv_linear(float(use_vigv)); L, cmap_ = lines_for(vigv, bleed_f)
        rows = sweep(0.0, 0.0, label, vigv, bleed_f, a8_max, L, cmap_)
        sched = dict(N=list(np.round(np.linspace(0.4, 1.0, 13), 3)), igv_deg=[vigv(n) for n in np.linspace(0.4, 1.0, 13)])
        return rows, vigv, L, cmap_, sched
    vigv = None; L, cmap_ = lines_for(None, bleed_f); rows = sweep(0.0, 0.0, label, None, bleed_f, a8_max, L, cmap_)
    if use_vigv:
        for it in range(3):
            pts = [(r["comp_NcMap"], r["W_stack"]) for r in rows if np.isfinite(r.get("W_stack", np.nan))]
            need = []
            for n, w in pts:
                for a in np.arange(c.ang["a1"], 70.5, 0.5):
                    try: q = c.point(n, w, igv=a)
                    except ao.Choked: a = np.nan; break
                    if q["stall_index"] <= 0.95: break
                need.append((n, float(a)))
            need = sorted([(n, a) for n, a in need if np.isfinite(a)])
            if not need: break
            nn = np.array([n for n, _ in need]); aa = np.maximum.accumulate(np.array([a for _, a in need])[::-1])[::-1]
            prev = vigv; vigv = (lambda nn, aa, prev: (lambda N: max(float(np.interp(N, nn, aa)), prev(N) if prev else 0.0)))(nn, aa, prev)
            L, cmap_ = lines_for(vigv, bleed_f); rows = sweep(0.0, 0.0, label, vigv, bleed_f, a8_max, L, cmap_)
            if all(r.get("stall_index", 9) <= 0.97 for r in rows if r["conv"]): break
    sched = dict(N=list(np.round(np.linspace(0.4, 1.0, 13), 3)), igv_deg=[vigv(n) if vigv else c.ang["a1"] for n in np.linspace(0.4, 1.0, 13)])
    return rows, vigv, L, cmap_, sched

if __name__ == "__main__":
    print(f"{TAG}: design stacking PR {c.point(1.0, c.W_d)['PR']:.3f}; bleed port after stage {K_BLEED}: frac_P {FRAC_P:.3f}, frac_work {FRAC_WORK:.3f}; "
          f"turbine map coverage {[(n, round(a, 2), round(b, 2)) for n, a, b in cover]}", flush=True)
    if MODE == "search":
        summ, allrows = [], []
        for use_vigv, bf, a8m in itertools.product((False, True), (0.0, 0.10, 0.20), (1.0, 1.3, 1.6)):
            label = f"V{int(use_vigv)}_B{int(bf*100)}_N{a8m:g}"
            try: rows, vigv, L, _, sched = run_config(use_vigv, bf, a8m, label)
            except Exception as ex:
                print(label, "FAILED", str(ex)[:200], flush=True); continue
            idle = idle_of(rows); allrows += rows
            r100 = [r for r in rows if abs(r["N_pct"] - 100) < 0.5]
            fn100 = r100[0]["Fn_N"] if r100 else np.nan
            summ.append(dict(config=label, vigv=use_vigv, bleed=bf, a8_max=a8m, idle_pct=idle, Fn_100_SLS=fn100,
                             SM_100=r100[0].get("SM_peak", np.nan) if r100 else np.nan, T4_100=r100[0]["Tt4_K"] if r100 else np.nan,
                             max_igv=max(sched["igv_deg"]), first_fail=next((f"{r['N_pct']:.1f} %: conv {r['conv']}, T4 {r['Tt4_K']:.0f}, si {r.get('stall_index', np.nan):.2f} "
                                                                          f"({r.get('stall_row', '-')}), SM {r.get('SM_peak', np.nan):+.3f}" for r in sorted(rows, key=lambda r: -r['N_pct']) if not r["ok"]), "none")))
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in summ[-1].items()}, flush=True)
            pd.DataFrame(summ).to_csv(os.path.join(OUT, f"operability_{TAG}_search.csv"), index=False)
            pd.DataFrame(allrows).to_csv(os.path.join(OUT, f"operability_{TAG}_search_points.csv"), index=False)
    elif MODE == "one":                                  # one search configuration per process (run in parallel); argv[3] = VIGV closure [deg] (0 = none)
        use_vigv, bf, a8m = float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
        label = f"V{use_vigv:g}_B{int(bf*100)}_N{a8m:g}" + ("" if A8_N == 0.40 else f"at{int(A8_N*100)}")
        rows, vigv, L, _, sched = run_config(use_vigv, bf, a8m, label)
        df = pd.DataFrame(rows); df["max_igv"] = max(sched["igv_deg"])
        df.to_csv(os.path.join(OUT, f"operability_{TAG}_cfg_{label}.csv"), index=False)
        print(label, "idle", idle_of(rows), flush=True)
    else:                                                # final <VIGV closure deg> <bleed> <a8_max>
        use_vigv, bf, a8m = float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
        rows, vigv, L, cmap_, sched = run_config(use_vigv, bf, a8m, "final_SLS")
        dash = sweep(dc.M_DASH, dc.H_DASH, "final_dash", vigv, 0.0, 1.0, *lines_for(vigv, 0.0))
        idle = idle_of(rows)
        out = dict(tag=TAG, config=dict(vigv=use_vigv, vigv_closure_deg=use_vigv, bleed=bf, bleed_stage=K_BLEED, bleed_close=BLEED_CLOSE, a8_max=a8m, frac_P=FRAC_P, frac_work=FRAC_WORK),
                   criteria=dict(SM_min=SM_MIN, T4_max=T4_MAX, stall_index_max=1.0), idle_pct=idle, vigv_schedule=sched,
                   lines=[{k: Lk[k] for k in ("N", "W_choke", "W_peak", "PR_peak", "W_howell", "PR_howell", "row_howell")} for Lk in L])
        json.dump(out, open(os.path.join(OUT, f"operability_{TAG}_final.json"), "w"), indent=1, default=float)
        pd.DataFrame(rows + dash).to_csv(os.path.join(OUT, f"operability_{TAG}_final.csv"), index=False)
        print(f"final: idle {idle} %", flush=True)
