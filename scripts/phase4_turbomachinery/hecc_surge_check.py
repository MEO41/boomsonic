"""Phase 4: how well does the peak-PR surge surrogate locate surge on a REAL vaned-diffuser centrifugal stage?

NASA HECC (NASA/CR-2014-218114/REV1; data vendored in scripts/phase0_tools/vendor/data/hecc/map_vaned.csv): the measured
100 % speed line runs from choke (5.24 kg/s) to the last stable point before surge. turbo-design (validated on this stage
at the design point) is swept along the same line with the upstream fixture geometry (no tuning); its peak-PR flow (the
surrogate used in Phase 3R) is compared with NASA's last stable flow. The measured design-point surge margin
SMN = (PR/W)_surge / (PR/W)_design - 1 is also reported.
Usage: python hecc_surge_check.py     output data/phase4r_hecc_surge_check.json
"""
import os, sys, json, warnings, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase0_tools", "vendor", "turbodesign_tests", "fixtures"))
import hecc_stage as h
from turbodesign.centrifugal import InletState

meas = np.array(sorted(h.nasa_speedline()))                      # (mdot, PR, eta_poly), increasing mdot
W_s, PR_s = meas[0, 0], meas[0, 1]; W_d, PR_d = h.MDOT_DESIGN, h.NASA["PR_tt"]
smn_meas = (PR_s / W_s) / (PR_d / W_d) - 1
stage = h.build(h.BACKSWEEP); pts = []
for m in np.arange(3.0, 5.95, 0.05):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore"); op = stage.solve(mdot=float(m), rpm=h.RPM, inlet=InletState(P0=h.P01, T0=h.T01))
        pts.append((float(m), float(op.stage_PR)))
    except Exception:
        continue
pts = np.array(pts); i = int(np.argmax(pts[:, 1])); PRd_td = float(np.interp(W_d, pts[:, 0], pts[:, 1]))
# vaned-diffuser leading-edge incidence (flow angle at the vaneless-space exit minus the vane LE metal angle, both from
# radial) at the design flow and at NASA's last stable flow -> an empirical diffuser-stall incidence for this stage
BLE = 79.64
def alpha3(m):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore"); op = stage.solve(mdot=float(m), rpm=h.RPM, inlet=InletState(P0=h.P01, T0=h.T01))
    return float(op.stage_states[0].alpha_deg)
a_d, a_s = alpha3(W_d), alpha3(W_s)
diff_inc = dict(beta_le_deg=BLE, alpha3_design=a_d, alpha3_surge=a_s, incidence_design=a_d - BLE, incidence_surge=a_s - BLE, d_alpha3_design_to_surge=a_s - a_d)
print(f"HECC vaned-diffuser LE (turbo-design): alpha3 {a_d:.2f} deg at design, {a_s:.2f} at the measured surge flow -> incidence "
      f"{a_d-BLE:+.2f} / {a_s-BLE:+.2f} deg (change {a_s-a_d:+.2f} deg)")
smn_td = (pts[i, 1] / pts[i, 0]) / (PRd_td / W_d) - 1
out = dict(measured=dict(W_last_stable=W_s, PR_last_stable=PR_s, W_design=W_d, PR_design=PR_d, SMN_design=smn_meas, W_surge_over_Wd=W_s / W_d,
                         slope_at_surge=float((meas[1, 1] - meas[0, 1]) / (meas[1, 0] - meas[0, 0]))),
           turbodesign=dict(W_peak=float(pts[i, 0]), PR_peak=float(pts[i, 1]), W_peak_over_Wd=float(pts[i, 0] / W_d), SMN_peak=smn_td, PR_design=PRd_td,
                            lowest_converged_W=float(pts[0, 0]), line=pts.tolist()), diffuser_incidence=diff_inc)
json.dump(out, open(os.path.join(ROOT, "data", "phase4r_hecc_surge_check.json"), "w"), indent=1)
print(f"NASA measured: last stable {W_s:.3f} kg/s (W/Wd {W_s/W_d:.3f}) PR {PR_s:.3f}; design {W_d:.3f} PR {PR_d:.3f} -> SMN {100*smn_meas:.1f} %; "
      f"dPR/dW at the last points {out['measured']['slope_at_surge']:.3f} per kg/s (negative = still rising toward surge)")
print(f"turbo-design: peak PR {pts[i,1]:.3f} at {pts[i,0]:.3f} kg/s (W/Wd {pts[i,0]/W_d:.3f}) -> peak-surrogate SMN {100*smn_td:.1f} %; lowest converged {pts[0,0]:.2f} kg/s")
