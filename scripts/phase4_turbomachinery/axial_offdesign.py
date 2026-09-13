"""Phase 4: off-design (part-speed) performance and stall of the committed 5-stage axial compressor
by mean-line stage stacking (row by row).

Why an own model: no approved tool gives axial-compressor maps (NASA turbo-design has no usable
axial loss model; TurboDesigner is design-only; TurboFlow has no axial compressor). This extends
the Phase 3 design model (axial_design.py: TurboDesigner triangles + Howell cascade losses, as in
Saravanamuttoo et al., Gas Turbine Theory 7th ed., ch. 5) to off-design with the classic
stage-stacking assumptions (e.g. Howell & Calvert 1978; Cumpsty, Compressor Aerodynamics ch. 11):

  * geometry frozen at the design: constant mean radius (TurboDesigner design), effective annulus
    areas calibrated so that the model reproduces the design axial velocity (200 m/s) at every
    station at the design point;
  * blade-row exit flow angles fixed at their design values (constant deviation);
  * the stage-1 inlet swirl is set by a FIXED inlet guide vane (the TurboDesigner 50 %-reaction
    design has alpha1 = 22 deg at the mean line, so an IGV is implied);
  * loss: relative total-pressure loss coefficient Y per row, calibrated at the design point so that
    each stage reproduces its Phase 3 stage efficiency (profile + annulus + secondary + tip
    clearance + stage-1 shock); off-design Y = Y* [1 + ((eps - eps_d)/(eps_s - eps*))^2] with the
    Reynolds correction of the design model on the profile part and the stage-1 normal-shock part
    recomputed from the tip relative Mach number;
  * STALL (Howell's definition, as given in Gas Turbine Theory ch. 5): the stalling deflection is
    where the cascade loss is twice its minimum, and the nominal deflection is 80 % of it,
    eps* = 0.8 eps_s, with Howell's nominal-deflection rule tan(in*) - tan(out*) = 1.55/(1 + 1.5 s/c).
    A row is stalled when its deflection reaches eps_s = eps*/0.8 (the loss parabola above gives
    exactly 2x the design loss there, consistent with the definition). The Lieblein diffusion factor
    is reported as a cross-check (DF > 0.6: separated, NASA SP-36).
  * CHOKE: no subsonic continuity solution at a station (sonic in the row frame), or the throat
    (o = s cos(in*)) reaching sonic mass flux.
Perfect gas gamma 1.4, R 287.05 (as the TurboDesigner design).
Usage: from axial_offdesign import Compressor; c = Compressor(); c.point(N_frac, W) -> dict
"""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
G, R = 1.4, 287.05
CP = G * R / (G - 1); KX = G / (G - 1)
d2r = np.radians

def howell_nominal_in(out_deg, s_c):
    return np.degrees(np.arctan(np.tan(d2r(out_deg)) + 1.55 / (1 + 1.5 * s_c)))

def normal_shock_pt_ratio(M):
    if M <= 1: return 1.0
    g = G
    return ((g + 1) * M * M / ((g - 1) * M * M + 2)) ** (g / (g - 1)) * ((g + 1) / (2 * g * M * M - (g - 1))) ** (1 / (g - 1))

class Choked(Exception):
    pass

def solve_cx(W, A, T0, P0, ang_deg):
    """subsonic axial velocity from continuity W = rho A Cx with total conditions (T0, P0) in the
    frame where the flow angle is ang (from axial)."""
    c = np.cos(d2r(ang_deg))
    def flux(cx):
        V = cx / c; T = T0 - V * V / (2 * CP)
        if T <= 0: return -1.0, T, 0.0
        P = P0 * (T / T0) ** KX
        return P / (R * T) * cx * A, T, P
    Vstar = np.sqrt(2 * G * R * T0 / (G + 1)); cx_max = Vstar * c
    fmax = flux(cx_max)[0]
    if W > fmax: raise Choked()
    lo, hi = 0.0, cx_max
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if flux(mid)[0] < W: lo = mid
        else: hi = mid
    cx = 0.5 * (lo + hi); _, T, P = flux(cx)
    return cx, T, P

class Compressor:
    def __init__(self, trade_file=os.path.join(ROOT, "data", "phase3", "trade_ax0_opr5_t1150_cap_blk_fielded.json"),
                 loss_mult=1.0, neg_width=1.0, comp=None):
        import axial_design as ad
        if comp is None:
            d = json.load(open(trade_file)); comp = d["case"]["comp"]
        p = comp["input"]
        self.p, self.comp = p, comp
        self.rpm_d, self.W_d, self.T01, self.P01, self.PR_d = p["rpm"], p["mdot"], p["T01"], p["P01"], p["PR"]
        tm = ad.build(p, comp["eta_is"])
        self.rm = float(np.ravel(tm.stages[0].rotor.flow_station.radius)[1])
        st0 = tm.stages[0]
        deg = lambda v: abs(float(np.degrees(np.ravel(v)[1])))           # TurboDesigner angles are in radians
        a1 = deg(st0.rotor.flow_station.flow_angle); b2 = deg(st0.rotor.next_flow_station.relative_flow_angle)
        a2 = deg(st0.rotor.next_flow_station.flow_angle); b1 = deg(st0.rotor.flow_station.relative_flow_angle)
        self.ang = dict(a1=a1, b1=b1, b2=b2, a2=a2)              # repeating mean-line triangles (verified identical per stage)
        self.N = len(comp["stages"]); self.s_c = float(p.get("s_c", 0.8))
        self.stages = comp["stages"]
        # Howell nominal / stalling deflections (rotor exit b2, stator exit a1)
        self.eps_nom_r = howell_nominal_in(b2, self.s_c) - b2; self.eps_nom_s = howell_nominal_in(a1, self.s_c) - a1
        self.eps_d_r = b1 - b2; self.eps_d_s = a2 - a1
        self.eps_st_r = self.eps_nom_r / 0.8; self.eps_st_s = self.eps_nom_s / 0.8
        self.loss_mult, self.neg_width = loss_mult, neg_width
        self._calibrate()

    # ---------- design calibration ----------
    def _calibrate(self):
        U = self.rpm_d * np.pi / 30 * self.rm; Cx = self.p["Cx"]; a = self.ang; self.U_d = U
        T0, P0 = self.T01, self.P01
        self.Y, self.Yshock, self.Aeff, self.Re_d, self.rho1_d, self.rho2_d = [], [], [], [], [], []
        g = lambda ang, T0_: T0_ - (Cx / np.cos(d2r(ang))) ** 2 / (2 * CP)
        for k, s in enumerate(self.stages):
            eta_p = s["eta_stage"]; dT0 = U * Cx * (np.tan(d2r(a["a2"])) - np.tan(d2r(a["a1"]))) / CP
            T03 = T0 + dT0; P03_target = P0 * (T03 / T0) ** (KX * eta_p)
            # split: shock part (stage 1 only) as a separate rotor loss, the rest equal Y on rotor and stator
            def run(Y, Ysh):
                T1 = g(a["a1"], T0); P1 = P0 * (T1 / T0) ** KX
                T0r = T1 + (Cx / np.cos(d2r(a["b1"]))) ** 2 / (2 * CP); P0r = P1 * (T0r / T1) ** KX
                P02r = P0r - (Y + Ysh) * (P0r - P1)
                T2 = T0r - (Cx / np.cos(d2r(a["b2"]))) ** 2 / (2 * CP); P2 = P02r * (T2 / T0r) ** KX
                T02 = T0 + dT0; P02 = P2 * (T02 / T2) ** KX
                P03 = P02 - Y * (P02 - P2)
                T3 = g(a["a1"], T02); P3 = P03 * (T3 / T02) ** KX
                return dict(T1=T1, P1=P1, T2=T2, P2=P2, T02=T02, P02=P02, P03=P03, T3=T3, P3=P3, P0r=P0r, T0r=T0r)
            # shock loss coefficient from the Phase 3 d_shock (efficiency points) -> equivalent rotor Y
            Ysh = 0.0
            if s["d_shock"] > 0:
                lo, hi = 0.0, 0.5
                for _ in range(60):
                    mid = 0.5 * (lo + hi); st = run(0.0, mid)
                    eta = (np.log(st["P03"] / P0) / KX) / np.log(T03 / T0)   # polytropic
                    if 1 - eta < s["d_shock"]: lo = mid
                    else: hi = mid
                Ysh = 0.5 * (lo + hi)
            lo, hi = 0.0, 0.5
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                if run(mid, Ysh)["P03"] > P03_target: lo = mid
                else: hi = mid
            Y = 0.5 * (lo + hi); st = run(Y, Ysh)
            rho1 = st["P1"] / (R * st["T1"]); rho2 = st["P2"] / (R * st["T2"]); rho3 = st["P3"] / (R * st["T3"])
            W = self.W_d
            self.Aeff.append((W / (rho1 * Cx), W / (rho2 * Cx), W / (rho3 * Cx))); self.rho1_d.append(rho1); self.rho2_d.append(rho2)
            Mt = s["M_rel_tip"]; self.Yshock.append((Ysh, Mt, 1 - normal_shock_pt_ratio(Mt)))
            self.Y.append(Y); self.Re_d.append((s["rotor"]["Re"], s["stator"]["Re"]))
            T0, P0 = T03, st["P03"]
        self.PR_model_d = P0 / self.P01
        self.Ageo = []
        for s in self.stages:
            Ar = np.pi * (s["rotor"]["r_tip"] ** 2 - s["rotor"]["r_hub"] ** 2); As = np.pi * (s["stator"]["r_tip"] ** 2 - s["stator"]["r_hub"] ** 2)
            self.Ageo.append((Ar, 0.5 * (Ar + As), As))

    # ---------- loss off-design ----------
    def _Y(self, k, row, eps, Re_ratio, Mtip):
        eps_d = self.eps_d_r if row == "r" else self.eps_d_s
        eps_nom = self.eps_nom_r if row == "r" else self.eps_nom_s
        width = eps_nom / 0.8 - eps_nom
        x = (eps - eps_d) / (width if eps >= eps_d else width * self.neg_width)
        re_f = float(np.clip(Re_ratio ** -0.2, 1.0, 1.5)) if Re_ratio < 1 else 1.0
        Y = self.Y[k] * self.loss_mult * (1 + x * x) * re_f
        if row == "r" and self.Yshock[k][0] > 0:
            Ysh_d, Mt_d, l_d = self.Yshock[k]
            Y += Ysh_d * (1 - normal_shock_pt_ratio(Mtip)) / l_d
        return Y

    # ---------- one operating point ----------
    def point(self, Nf, W, T01=None, P01=None, detail=False, igv=None, bleed=None):
        """Nf: mechanical speed / design; W: inlet mass flow [kg/s] at T01/P01 (default design inlet).
        igv: stage-1 inlet swirl angle [deg] (None = fixed IGV at the design value);
        bleed: (stage_index_after_which, fraction_of_inlet_flow) interstage bleed."""
        T0 = self.T01 if T01 is None else T01; P0 = self.P01 if P01 is None else P01
        omega = Nf * self.rpm_d * np.pi / 30; U = omega * self.rm; a = self.ang
        rows = []; alpha_in = a["a1"] if igv is None else igv
        T0in, P0in = T0, P0; W_in = W; work = 0.0
        for k, s in enumerate(self.stages):
            if bleed is not None and k == bleed[0]:
                W = W_in * (1 - bleed[1])
            A1, A2, A3 = self.Aeff[k]
            cx1, T1, P1 = solve_cx(W, A1, T0, P0, alpha_in)
            ct1 = cx1 * np.tan(d2r(alpha_in)); wt1 = U - ct1
            b1 = np.degrees(np.arctan2(wt1, cx1)); W1 = np.hypot(cx1, wt1)
            T0r = T1 + W1 * W1 / (2 * CP); P0r = P1 * (T0r / T1) ** KX
            # throat check (rotor): o = s cos(b1*)
            eps_r = b1 - a["b2"]
            Re_r = (P1 / (R * T1)) * W1 / (self.rho1_d[k] * self.p["Cx"] / np.cos(d2r(a["b1"])))  # Re ratio ~ rho W (same chord, viscosity ~const)
            Mt = (np.hypot(cx1, U * s["rotor"]["r_tip"] / self.rm - ct1)) / np.sqrt(G * R * T1)
            Yr = self._Y(k, "r", eps_r, Re_r, Mt)
            P02r = P0r - Yr * (P0r - P1)
            try:
                cx2, T2, P2 = solve_cx(W, A2, T0r, P02r, a["b2"])
            except Choked:
                raise Choked(f"rotor {k+1} exit")
            ct2 = U - cx2 * np.tan(d2r(a["b2"]))
            T02 = T2 + (cx2 ** 2 + ct2 ** 2) / (2 * CP); P02 = P2 * (T02 / T2) ** KX
            a2 = np.degrees(np.arctan2(ct2, cx2)); eps_s = a2 - a["a1"]
            V2 = np.hypot(cx2, ct2)
            Re_s = (P2 / (R * T2)) * V2 / (self.rho2_d[k] * self.p["Cx"] / np.cos(d2r(a["a2"])))
            Ys = self._Y(k, "s", eps_s, Re_s, 0.0)
            P03 = P02 - Ys * (P02 - P2)
            try:
                cx3, T3, P3 = solve_cx(W, A3, T02, P03, a["a1"])
            except Choked:
                raise Choked(f"stator {k+1} exit")
            W2 = np.hypot(cx2, U - ct2) if False else cx2 / np.cos(d2r(a["b2"]))
            V3 = cx3 / np.cos(d2r(a["a1"]))
            DFr = 1 - W2 / W1 + abs(wt1 - (U - ct2)) / (2 * W1) * self.s_c
            DFs = 1 - V3 / V2 + abs(ct2 - cx3 * np.tan(d2r(a["a1"]))) / (2 * V2) * self.s_c
            rows.append(dict(stage=k + 1, cx1=cx1, phi=cx1 / U, b1=b1, eps_r=eps_r, eps_s=eps_s, i_r=b1 - a["b1"], i_s=a2 - a["a2"],
                             stall_r=eps_r / self.eps_st_r, stall_s=eps_s / self.eps_st_s, DF_r=DFr, DF_s=DFs, Yr=Yr, Ys=Ys, M_tip=Mt,
                             PR=P03 / P0, dT0=T02 - T0, cx2=cx2, cx3=cx3))
            work += W * CP * (T02 - T0)
            T0, P0 = T02, P03; alpha_in = a["a1"]
        PR = P0 / P0in; TR = T0 / T0in
        eta = (PR ** (1 / KX) - 1) / (TR - 1) if TR > 1 else np.nan
        worst = max(max(r["stall_r"], r["stall_s"]) for r in rows)
        wrow = max(((r["stage"], "R", r["stall_r"]) for r in rows) + tuple((r["stage"], "S", r["stall_s"]) for r in rows), key=lambda x: x[2]) if False else None
        cand = [(r["stall_r"], f"R{r['stage']}") for r in rows] + [(r["stall_s"], f"S{r['stage']}") for r in rows]
        wv, wn = max(cand)
        out = dict(N=Nf, W=W_in, W_out=W, PR=PR, eta=eta, power=work, T0_out=T0, stall_index=wv, stall_row=wn, maxDF=max(max(r["DF_r"], r["DF_s"]) for r in rows),
                   Wc=W_in * np.sqrt(T0in / 288.15) / (P0in / 101325.0), Nc=Nf / np.sqrt(T0in / self.T01))
        if detail: out["rows"] = rows
        return out

    # ---------- a speed line ----------
    def choke_flow(self, Nf, **kw):
        lo, hi = 0.005, self.W_d * 1.6
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            try: self.point(Nf, mid, **kw); lo = mid
            except Choked: hi = mid
        return lo

    def speed_line(self, Nf, npts=300, **kw):
        """from choke down to 25 % of the choke flow (or until the characteristic has clearly peaked).
        Returns points (high W -> low W), the index of the first-row (Howell) stall and of the PR peak."""
        Wch = self.choke_flow(Nf, **kw)
        pts = []
        for W in Wch * (1 - np.linspace(0, 0.75, npts)):
            try: pt = self.point(Nf, W, **kw)
            except Choked: continue
            pts.append(pt)
        PR = np.array([q["PR"] for q in pts]); si = np.array([q["stall_index"] for q in pts])
        i_stall = int(np.argmax(si >= 1.0)) if np.any(si >= 1.0) else None
        i_peak = int(np.argmax(PR))
        return dict(N=Nf, W_choke=Wch, points=pts, i_stall=i_stall, i_peak=i_peak)

if __name__ == "__main__":
    c = Compressor()
    print(f"mean radius {c.rm*1e3:.2f} mm; design triangles {c.ang}")
    print(f"Howell nominal deflection rotor {c.eps_nom_r:.2f} deg / stator {c.eps_nom_s:.2f}; design deflection {c.eps_d_r:.2f} / {c.eps_d_s:.2f}; stalling {c.eps_st_r:.2f} / {c.eps_st_s:.2f}")
    print("calibrated Y per stage:", np.round(c.Y, 4), "shock", [round(v[0], 4) for v in c.Yshock])
    print("effective/geometric area:", [tuple(round(ae / ag, 3) for ae, ag in zip(A, Ag)) for A, Ag in zip(c.Aeff, c.Ageo)])
    dp = c.point(1.0, c.W_d, detail=True)
    print(f"DESIGN CHECK: PR {dp['PR']:.4f} (design {c.PR_d}), eta_is {dp['eta']:.4f} (Phase 3 {c.comp['eta_is']:.4f}), stall index {dp['stall_index']:.3f}")
    for r in dp["rows"]:
        print({k: round(v, 3) for k, v in r.items()})
