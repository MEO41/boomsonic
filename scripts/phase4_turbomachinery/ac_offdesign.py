"""Option B check 2: off-design model of the axial-centrifugal compressor (1-2 axial stages + 1 centrifugal, one shaft).

* Axial stage(s): the Phase 4 stage-stacking model (axial_offdesign.Compressor, Howell stall criterion), built on the
  Phase 3 TurboDesigner design of the AC front stage(s).
* Centrifugal stage: the TurboFlow off-design map of the Phase 3 AC impeller + diffuser (centrifugal_map.py), in
  corrected terms at the eye (N/sqrt(T0_eye), W sqrt(T0_eye)/P0_eye). Each speed line is parametrised by
  beta = (W - W_low)/(W_choke - W_low) between its lowest converged flow and its last unchoked flow;
  beta > 1 -> choked; beta < 0 -> beyond the lowest flow TurboFlow converged at (treated as unreachable).
* Coupling: axial exit total state = eye state (the last axial stator is assumed to deswirl, as in Phase 3b;
  the transition-duct loss is not modelled, as in Phase 3b).
Surge surrogate of the combined machine: the peak of the overall pressure-ratio characteristic, or the low-flow end
of the centrifugal map if the characteristic has not peaked there (flagged: then the true surge flow is lower).
The class exposes speed_line() in the format used by axial_map.build_compressor_lines / compressor_mapdata.
"""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import axial_offdesign as ao
G = 1.4; KX = G / (G - 1)

class CentrifugalMap:
    def __init__(self, fn):
        m = json.load(open(fn)); self.T01, self.P01, self.W_d = m["design"]["T01"], m["design"]["P01"], m["design"]["mdot"]
        pts = [p for p in m["points"] if p.get("success") and np.isfinite(p.get("PR", np.nan)) and p.get("eta", 0) > 0]
        self.lines = []
        for N in sorted(set(round(p["N"], 3) for p in pts)):
            q = sorted([p for p in pts if round(p["N"], 3) == N], key=lambda p: p["mdot"])
            unch = [p for p in q if not p.get("choked")]
            if len(unch) < 3: continue
            W = np.array([p["mdot"] for p in unch]); PR = np.array([p["PR"] for p in unch]); E = np.array([p["eta"] for p in unch])
            self.lines.append(dict(N=N, W=W, PR=PR, eta=E, W_low=W[0], W_choke=W[-1], PR_peak=PR.max(), W_peak=W[np.argmax(PR)],
                                   peaked=bool(np.argmax(PR) > 0)))
        self.Ns = np.array([l["N"] for l in self.lines])

    def __call__(self, Nc, Wc):
        """Nc: corrected speed fraction; Wc: flow at the map's inlet conditions [kg/s]. Returns PR, eta, beta."""
        Ns = self.Ns
        if Nc < Ns[0] or Nc > Ns[-1]:
            raise ao.Choked(f"centrifugal map speed {Nc:.3f} outside {Ns[0]}-{Ns[-1]}")
        j = int(np.clip(np.searchsorted(Ns, Nc) - 1, 0, len(Ns) - 2)); a, b = self.lines[j], self.lines[j + 1]
        t = (Nc - a["N"]) / (b["N"] - a["N"])
        Wl = a["W_low"] + t * (b["W_low"] - a["W_low"]); Wh = a["W_choke"] + t * (b["W_choke"] - a["W_choke"])
        beta = (Wc - Wl) / (Wh - Wl)
        if beta > 1: raise ao.Choked("centrifugal choked")
        if beta < 0: raise ao.Choked("centrifugal below lowest converged flow")
        f = lambda L, k: float(np.interp(L["W_low"] + beta * (L["W_choke"] - L["W_low"]), L["W"], L[k]))
        return f(a, "PR") * (1 - t) + f(b, "PR") * t, f(a, "eta") * (1 - t) + f(b, "eta") * t, beta

class ACCompressor:
    def __init__(self, tag, neg_width=1.0, cc_map=None):
        d = json.load(open(os.path.join(ROOT, "data", "phase3", f"trade_{tag}_fielded.json")))
        self.comp = d["case"]["comp"]
        self.ax = ao.Compressor(comp=self.comp["axial"], neg_width=neg_width)
        self.cc = CentrifugalMap(cc_map or os.path.join(ROOT, "data", "phase4", f"centrifugal_map_{tag}.json"))
        self.W_d, self.T01, self.P01 = self.ax.W_d, self.ax.T01, self.ax.P01
        self.rpm_d = self.ax.rpm_d; self.ang = self.ax.ang

    def point(self, Nf, W, detail=False, igv=None, bleed=None):
        q = self.ax.point(Nf, W, detail=True, igv=igv)
        T0e, P0e = q["T0_out"], self.P01 * q["PR"]
        Nc_c = Nf * np.sqrt(self.cc.T01 / T0e)
        W_map = W * np.sqrt(T0e / self.cc.T01) * (self.cc.P01 / P0e)
        PRc, etac, beta = self.cc(Nc_c, W_map)
        T0out = T0e * (1 + (PRc ** (1 / KX) - 1) / etac)
        PR = q["PR"] * PRc
        eta = (PR ** (1 / KX) - 1) / (T0out / self.T01 - 1)
        out = dict(N=Nf, W=W, PR=PR, eta=eta, PR_ax=q["PR"], PR_cc=PRc, eta_cc=etac, beta_cc=beta, Nc_cc=Nc_c,
                   stall_index=q["stall_index"], stall_row=q["stall_row"], maxDF=q["maxDF"], T0_out=T0out)
        if detail: out["rows"] = q["rows"]
        return out

    def speed_line(self, Nf, npts=240, **kw):
        lo, hi = 0.005, self.W_d * 1.6
        for _ in range(60):                                   # choke flow (axial or centrifugal)
            mid = 0.5 * (lo + hi)
            try: self.point(Nf, mid, **kw); lo = mid
            except ao.Choked as e:
                if "below lowest" in str(e): lo = mid          # low-flow side: go up
                else: hi = mid
        Wch = lo
        pts = []
        for W in Wch * (1 - np.linspace(0, 0.8, npts)):
            try: pts.append(self.point(Nf, W, **kw))
            except ao.Choked: continue
        if not pts: raise RuntimeError(f"no valid points at N {Nf}")
        PR = np.array([p["PR"] for p in pts]); si = np.array([p["stall_index"] for p in pts])
        i_peak = int(np.argmax(PR))
        return dict(N=Nf, W_choke=Wch, points=pts, i_stall=int(np.argmax(si >= 1)) if np.any(si >= 1) else None, i_peak=i_peak,
                    peak_is_map_end=bool(i_peak == len(pts) - 1))

class PureCC:
    """single centrifugal stage (engine inlet = map inlet), same interface as ACCompressor (method benchmark)."""
    def __init__(self, map_file):
        self.cc = CentrifugalMap(map_file); self.W_d, self.T01, self.P01 = self.cc.W_d, self.cc.T01, self.cc.P01
        self.ang = {"a1": 0.0}

    def point(self, Nf, W, detail=False, igv=None, bleed=None):
        PR, eta, beta = self.cc(Nf, W)
        return dict(N=Nf, W=W, PR=PR, eta=eta, beta_cc=beta, stall_index=0.0, stall_row="-", maxDF=0.0)

    speed_line = ACCompressor.speed_line
