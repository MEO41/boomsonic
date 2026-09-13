"""Phase 4: compressor and turbine maps for pyCycle from the Phase 4 off-design models.

Compressor (axial_offdesign.Compressor, stage stacking): speed lines at corrected speeds Nc (fraction of
design), each from choke down to the peak of the pressure-ratio characteristic (the surrogate surge
line, 'RlineMap = 1'), parametrised by R-line 1..3 linear in corrected flow. The first-row Howell stall
line is kept separately (post-processing), because a multistage compressor can run with its front
stage stalled at low speed without surging.
Turbine (TurboFlow performance analysis, turbine_map.py): speed lines at N/sqrt(T) fraction, on a
common total-to-total pressure-ratio grid -> corrected flow W sqrt(T0)/P0 and eta_tt.
"""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from pycycle.maps.map_data import MapData
KG2LBM = 2.2046226218

NC_GRID = (0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05)
R_GRID = np.linspace(1.0, 3.0, 25)

def build_compressor_lines(c, Ns=NC_GRID, igv_sched=None, bleed_sched=None, **kw):
    """speed lines in corrected terms at the design inlet (T01, P01) of the stacking model.
    igv_sched: optional callable N -> stage-1 inlet swirl angle [deg] (variable IGV schedule)."""
    lines = []
    for N in Ns:
        if igv_sched is not None: kw["igv"] = float(igv_sched(N))
        if bleed_sched is not None: kw["bleed"] = bleed_sched(N)
        sl = c.speed_line(N, **kw)
        pts = sl["points"]
        W = np.array([q["W"] for q in pts]); PR = np.array([q["PR"] for q in pts]); eta = np.array([q["eta"] for q in pts])
        si = np.array([q["stall_index"] for q in pts]); DF = np.array([q["maxDF"] for q in pts])
        rows = [q["stall_row"] for q in pts]
        ip = sl["i_peak"]; ist = sl["i_stall"]
        # Howell first-row stall flow: interpolate stall_index = 1 between points (W decreasing)
        W_howell = np.nan; row_howell = None
        if ist is not None and ist > 0:
            j = ist; W_howell = float(np.interp(1.0, [si[j - 1], si[j]], [W[j - 1], W[j]])); row_howell = rows[j]
        elif ist == 0:
            W_howell = float(W[0]); row_howell = rows[0]            # stalled already at choke
        lines.append(dict(N=N, igv=kw.get("igv"), W=W.tolist(), PR=PR.tolist(), eta=eta.tolist(), stall_index=si.tolist(), maxDF=DF.tolist(), stall_row=rows,
                          W_choke=sl["W_choke"], W_peak=float(W[ip]), PR_peak=float(PR[ip]), W_howell=W_howell, row_howell=row_howell,
                          PR_howell=float(np.interp(W_howell, W[::-1], PR[::-1])) if np.isfinite(W_howell) else np.nan))
    return lines

def compressor_mapdata(lines, W_d, T01, P01, N_d=1.0):
    """pyCycle MapData (alpha x Nc x Rline) in lbm/s corrected flow; returns (MapData, R_design)."""
    th = np.sqrt(T01 / 288.15); de = P01 / 101325.0
    Wc = np.zeros((len(lines), len(R_GRID))); PR = np.zeros_like(Wc); ETA = np.zeros_like(Wc)
    for i, L in enumerate(lines):
        W = np.array(L["W"])[::-1]; pr = np.array(L["PR"])[::-1]; e = np.array(L["eta"])[::-1]      # increasing W
        Wlo, Whi = L["W_peak"], L["W_choke"]
        Wr = Wlo + (R_GRID - 1) / 2 * (Whi - Wlo)
        Wc[i] = Wr * th / de * KG2LBM
        PR[i] = np.maximum(np.interp(Wr, W, pr), 1.0005)
        ETA[i] = np.clip(np.interp(Wr, W, np.nan_to_num(e, nan=0.05)), 0.05, 1.0)
    Ns = np.array([L["N"] for L in lines])
    L1 = lines[list(Ns).index(N_d)]
    R_d = 1 + 2 * (W_d - L1["W_peak"]) / (L1["W_choke"] - L1["W_peak"])
    m = MapData()
    m.defaults = dict(alphaMap=0.0, NcMap=N_d, RlineMap=float(R_d), PRmap=float(np.interp(R_d, R_GRID, PR[list(Ns).index(N_d)])))
    m.RlineStall = 1.0
    m.alphaMap = np.array([0.0, 1.0]); m.NcMap = Ns; m.RlineMap = R_GRID
    m.WcMap = np.array([Wc, Wc]); m.effMap = np.array([ETA, ETA]); m.PRmap = np.array([PR, PR])
    m.units = dict(NcMap="rpm", WcMap="lbm/s"); m.Npts = Ns.size
    m.param_data = [dict(name="alphaMap", values=m.alphaMap, default=0, units=None), dict(name="NcMap", values=m.NcMap, default=N_d, units="rpm"),
                    dict(name="RlineMap", values=m.RlineMap, default=float(R_d), units=None)]
    m.output_data = [dict(name="WcMap", values=m.WcMap, default=float(np.mean(Wc)), units="lbm/s"), dict(name="effMap", values=m.effMap, default=float(np.mean(ETA)), units=None),
                     dict(name="PRmap", values=m.PRmap, default=m.defaults["PRmap"], units=None)]
    return m, R_d

PRT_GRID = np.array([1.05, 1.15, 1.3, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0])

def turbine_mapdata(tmap):
    """pyCycle turbine MapData from turbine_map.py output: NpMap in % of design corrected speed,
    PRmap = total-to-total PR grid, WpMap = W sqrt(T0)/P0 (arbitrary consistent units), effMap = eta_tt."""
    pts = [p for p in tmap["points"] if p.get("success")]
    T0, p0 = tmap["design"]["T0"], tmap["design"]["p0"]
    Ns = sorted(set(round(p["N_frac"], 3) for p in pts))
    Wp = np.zeros((len(Ns), len(PRT_GRID))); E = np.zeros_like(Wp); cover = []
    for i, N in enumerate(Ns):
        q = sorted([p for p in pts if round(p["N_frac"], 3) == N], key=lambda p: p["PR_tt"])
        pr = np.array([p["PR_tt"] for p in q]); w = np.array([p["mdot"] for p in q]) * np.sqrt(T0) / p0 * 1e3; e = np.array([p["eta_tt"] for p in q])
        # linear extrapolation outside the computed PR range is replaced by the edge value (choked flow is flat anyway)
        Wp[i] = np.interp(PRT_GRID, pr, w); E[i] = np.clip(np.interp(PRT_GRID, pr, e), 0.05, 1.0)
        cover.append((N, float(pr.min()), float(pr.max())))
    m = MapData()
    PR_d = tmap["design"]["check"]["PR_tt"]
    m.defaults = dict(alphaMap=1.0, NpMap=100.0, PRmap=float(PR_d))
    m.alphaMap = np.array([1.0, 2.0]); m.NpMap = np.array(Ns) * 100; m.PRmap = PRT_GRID
    m.WpMap = np.array([Wp, Wp]); m.effMap = np.array([E, E]); m.units = dict(NpMap="rpm", WpMap="lbm/s")
    m.param_data = [dict(name="alphaMap", values=m.alphaMap, default=1.0, units=None), dict(name="NpMap", values=m.NpMap, default=100.0, units="rpm"),
                    dict(name="PRmap", values=m.PRmap, default=float(PR_d), units=None)]
    m.output_data = [dict(name="WpMap", values=m.WpMap, default=float(np.mean(Wp)), units="lbm/s"), dict(name="effMap", values=m.effMap, default=float(np.mean(E)), units=None)]
    return m, cover
