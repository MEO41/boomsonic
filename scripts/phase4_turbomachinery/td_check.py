"""Phase 4 (centrifugal baseline): independent check of the Phase 3R compressor stages with NASA turbo-design
(turbodesign.centrifugal, GitHub main 23c2b0b; Phase 0 primary tool, validated on the NASA HECC stage: PR +2.0 %,
eta_poly -0.2 %, psi +0.3 %; Oh loss set with Aungier head-loss correction, Wiesner slip on Z_eff).

The same stage as the TurboFlow tool-level design (data/phase3r/<tag>_cc_out.json) is rebuilt from its meanline
geometry (no tuning):
  * flow path: turbodesign.centrifugal.flowpath_builder.build_flowpath(r1h, r1s, r2, b2_geo, Lz = axial length);
  * impeller: 12 main + 12 splitter blades (splitter LE at half the main-blade meridional length), exit backsweep, tip
    clearance 0.25 mm, exit metal blockage B2 from the Phase 3R stress-sized blades (tool level) so that the effective exit
    area equals TurboFlow's; inducer metal angle = the design RMS flow angle (zero incidence); LE thickness 0.8 mm;
    inducer throat between main blades Z (s_rms cos beta1b - t_le)(r1s - r1h);
  * vaneless space to 1.06 r2 and vaned diffuser to 1.35 r2 (19 vanes, LE angle = TurboFlow's, TE 34 deg), channel width =
    the effective exit width (as in the TurboFlow model); no deswirl row (TurboFlow has none either).
Outputs: design-point PR / isentropic eta_tt (constant-cp, as TurboFlow's comparison basis) and the 100 % speed line, whose
peak-PR flow is compared with TurboFlow's (the surge surrogate behind the Phase 3R backsweep choice).
Caveats (from the code review): the vaned-diffuser loss is a Lieblein cascade correlation beyond its fitted range; no
shock loss; diffusion stall not modelled.
Usage: python td_check.py      output data/phase4r_td_check.json, plots/phase4r_td_check.png
"""
import os, sys, json, warnings, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
from turbodesign.centrifugal import Air, Impeller, InletState, MeridionalPath, OhLossSet, Stage, WiesnerSlip
from turbodesign.centrifugal.geometry import _Curve
from turbodesign.centrifugal.diffusion import VanelessSpace, VanedDiffuser
from turbodesign.centrifugal.flowpath_builder import build_flowpath, meridional_length
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
TAGS = {0: "ce75000_opr4_t1150_b0_cap", 15: "ce75000_opr4_t1150_b15_cap", 20: "ce75000_opr4_t1150_b20_cap"}
T_LE = 0.8e-3
G = 1.4003

def stage_for(tag):
    cc = json.load(open(os.path.join(ROOT, "data", "phase3r", f"{tag}_cc_out.json")))
    cct = json.load(open(os.path.join(ROOT, "data", "phase3r", f"cct_{tag}.json")))
    s = cct["levels"]["tool"]["stress"]["blade"]; B2 = s["B2"]
    g = cc["geometry"]; im, vd = g["impeller"], g["vaned_diffuser"]
    r1h, r1s, r2, b2e, Lz = im["radius_hub_in"], im["radius_tip_in"], im["radius_out"], im["width_out"], im["length_axial"]
    b2g = b2e / (1 - B2)
    hub, shr = build_flowpath(r1h, r1s, r2, b2g, Lz, r_exit=r2, inlet_duct_len=0.0)
    path = MeridionalPath(_Curve(hub[:, 0], hub[:, 1]), _Curve(shr[:, 0], shr[:, 1]))
    lm = float(meridional_length(hub, shr))
    mid = 0.5 * (hub + shr); sarc = np.concatenate([[0], np.cumsum(np.hypot(np.diff(mid[:, 0]), np.diff(mid[:, 1])))])
    r_spl = float(np.interp(0.5 * sarc[-1], sarc, mid[:, 1]))
    b1b = cc["beta1b"]; r1rms = np.sqrt(0.5 * (r1s ** 2 + r1h ** 2)); Z = cc["input"]["Z"]
    # inducer throat = the design's (TurboFlow area_throat_ratio x eye area, sized for a 10 % choke margin in Phase 3R);
    # the blade-angle estimate Z (s_rms cos beta1b - t)(r1s - r1h) gives 0.63 x eye and chokes 2 % above design flow
    A_th = im["area_throat_ratio"] * np.pi * (r1s ** 2 - r1h ** 2)
    imp = Impeller(n_blades=int(Z), backsweep_deg=float(im["trailing_edge_angle"]), r_te=r2, blockage=B2, x_le=1e-6,   # just inside the path (strict bracket)
                   n_splitters=int(cc["input"]["Z_split"]), splitter_le_r=r_spl, tip_clearance=im["tip_clearance"],
                   l_main_m=lm, l_splitter_m=0.5 * lm, inducer_blade_angle_deg=float(b1b), le_blade_thickness=T_LE, throat_area=float(A_th))
    comps = [VanelessSpace(r3=g["vaneless_diffuser"]["radius_out"], b3=b2e),
             VanedDiffuser(r3=vd["radius_in"], r4=vd["radius_out"], b=b2e, n_vanes=int(vd["number_of_vanes"]),
                           beta_le_deg=abs(float(vd["leading_edge_angle"])), beta_te_deg=float(vd["trailing_edge_angle"]))]
    st = Stage(path=path, impeller=imp, slip=WiesnerSlip(), losses=OhLossSet(), fluid=Air(), components=comps)
    geo = dict(r1h=r1h, r1s=r1s, r2=r2, b2_geo=b2g, B2=B2, Lz=Lz, l_main=lm, r_splitter_le=r_spl, throat_area=A_th, A_eye=np.pi * (r1s ** 2 - r1h ** 2))
    return st, cc, geo

def eta_is(op, T01):
    return (op.stage_PR ** ((G - 1) / G) - 1) / (op.stage_exit.T0 / T01 - 1)

if __name__ == "__main__":
    out = {}
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    for b, tag in TAGS.items():
        st, cc, geo = stage_for(tag); inp = cc["input"]; Wd = inp["mdot"]; inlet = InletState(P0=inp["P01"], T0=inp["T01"])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore"); op = st.solve(mdot=Wd, rpm=inp["rpm"], inlet=inlet)
        dp = dict(PR_stage=op.stage_PR, PR_impeller=op.PR, eta_is_stage=eta_is(op, inp["T01"]), eta_poly_realgas=op.stage_eta_poly_realgas,
                  psi=op.psi, impeller_eta_is=op.impeller_eta_is, work_euler=op.work_euler, work_actual=op.work_actual,
                  M2=op.stage_states[0].mach(Air()) if op.stage_states else np.nan,
                  internal=dict(op.losses.internal), parasitic=dict(op.losses.parasitic),
                  TF_PR=cc["turboflow"]["PR"], TF_eta=cc["turboflow"]["eta"])
        # 100 % speed line (and 90 %)
        lines = {}
        for N in (1.0, 0.9, 0.8):
            pts = []
            for f in np.arange(0.30, 1.40, 0.02):
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore"); q = st.solve(mdot=Wd * f * N, rpm=inp["rpm"] * N, inlet=inlet)
                    if q.stage_PR and q.stage_PR > 1: pts.append((float(Wd * f * N), float(q.stage_PR), float(eta_is(q, inp["T01"]))))
                except Exception:
                    continue
            pts = np.array(pts); lines[N] = pts
        L1 = lines[1.0]; i = int(np.argmax(L1[:, 1])); PRd = float(np.interp(Wd, L1[:, 0], L1[:, 1]))
        smn = (L1[i, 1] / L1[i, 0]) / (PRd / Wd) - 1
        # TurboFlow 100 % line for comparison
        m = json.load(open(os.path.join(ROOT, "data", "phase3r", "maps", f"centrifugal_map_{tag}.json")))
        q = sorted([p for p in m["points"] if p.get("success") and abs(p["N"] - 1.0) < 1e-6 and not p.get("choked")], key=lambda p: p["mdot"])
        Wt = np.array([p["mdot"] for p in q]); Pt = np.array([p["PR"] for p in q]); j = int(np.argmax(Pt))
        smn_tf = (Pt[j] / Wt[j]) / (np.interp(Wd, Wt, Pt) / Wd) - 1
        out[b] = dict(tag=tag, geometry=geo, design=dp, peak_W_over_Wd=float(L1[i, 0] / Wd), SMN_design=float(smn), choke_W_over_Wd=float(L1[-1, 0] / Wd),
                      TF_peak_W_over_Wd=float(Wt[j] / Wd), TF_SMN=float(smn_tf), lines={str(k): v.tolist() for k, v in lines.items()})
        print(f"b{b}: turbo-design PR {dp['PR_stage']:.3f} eta_is {dp['eta_is_stage']:.4f} (TurboFlow PR {dp['TF_PR']:.3f} eta {dp['TF_eta']:.4f}); "
              f"impeller PR {dp['PR_impeller']:.3f} psi {dp['psi']:.3f}; 100 % peak at W/Wd {L1[i,0]/Wd:.2f} (TurboFlow {Wt[j]/Wd:.2f}), "
              f"SMN {100*smn:.1f} % (TurboFlow {100*smn_tf:.1f} %), choke at {L1[-1,0]/Wd:.2f} Wd", flush=True)
        c = {0: "tab:grey", 15: "tab:green", 20: "tab:blue"}[b]
        ax[0].plot(L1[:, 0] / Wd, L1[:, 1], "-", c=c, label=f"{b} deg, turbo-design"); ax[0].plot(Wt / Wd, Pt, "--", c=c, label=f"{b} deg, TurboFlow")
        ax[0].plot(L1[i, 0] / Wd, L1[i, 1], "*", c=c, ms=12); ax[0].plot(Wt[j] / Wd, Pt[j], "o", mfc="none", c=c, ms=9)
        ax[1].plot(L1[:, 0] / Wd, L1[:, 2], "-", c=c, label=f"{b} deg, turbo-design")
        et = np.array([p["eta"] for p in q]); ax[1].plot(Wt / Wd, et, "--", c=c, label=f"{b} deg, TurboFlow")
    ax[0].axvline(1, c="k", lw=.8, ls=":"); ax[0].set_xlabel("W / W_design (100 % speed)"); ax[0].set_ylabel("stage PR_tt (to vaned-diffuser exit)")
    ax[0].set_title("100 % speed lines; star / circle = peak (surge surrogate)", fontsize=9); ax[0].legend(fontsize=7); ax[0].grid(alpha=.3)
    ax[1].set_xlabel("W / W_design"); ax[1].set_ylabel("eta_tt (isentropic)"); ax[1].set_ylim(0.5, 0.9); ax[1].legend(fontsize=7); ax[1].grid(alpha=.3)
    fig.suptitle("Phase 4: NASA turbo-design vs TurboFlow on the Phase 3R impellers (OPR 4, 75 000 rpm, tool-level geometry)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase4r_td_check.png"), dpi=130)
    json.dump(out, open(os.path.join(ROOT, "data", "phase4r_td_check.json"), "w"), indent=1, default=float)
