"""Phase 4: off-design map of the designed single-stage turbine with TurboFlow's own performance
analysis (run in .venv-np1). Replaces pyCycle's placeholder LPT2269 map shape.

  .venv-np1/Scripts/python scripts/phase4_turbomachinery/turbine_map.py <tt_out.json> <map_out.json>

Geometry = the TurboFlow design-optimisation result of Phase 3 (turbine_design.py output), same
simulation options as the design (Benner loss model, Aungier deviation, critical-Mach choking,
CoolProp air). Inlet T0/p0 fixed at the design values; the map is swept in exit static pressure
(PR_ts) and rotational speed; outputs PR_tt, eta_tt, mass flow, so it can be written as a pyCycle
turbine map (corrected speed, PR_tt -> corrected flow, eta_tt).
Verification: the design point (design omega, design p_out) must reproduce the design-optimisation
mass flow and efficiency.
"""
import sys, os, json, numpy as np
import turboflow as tf
import turboflow.axial_turbine.performance_analysis as _pa
# TurboFlow 0.1.18 defect: with stop_on_failure=False a failed point leaves None in the timing list and
# print_simulation_summary() crashes (np.mean over None) after the sweep; the summary is cosmetic -> disabled.
_pa.print_simulation_summary = lambda *a, **k: None

tt = json.load(open(sys.argv[1])); out_file = sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "phase0_tools", "vendor", "turboflow_examples", "one-stage_config.yaml")
cfg = tf.load_config(EX, print_summary=False)
g = tt["geometry"]
keys = ["radius_hub_in", "radius_hub_out", "radius_tip_in", "radius_tip_out", "pitch", "chord", "stagger_angle", "opening",
        "leading_edge_angle", "leading_edge_wedge_angle", "leading_edge_diameter", "trailing_edge_thickness", "maximum_thickness",
        "tip_clearance", "throat_location_fraction"]
for k in keys: cfg["geometry"][k] = np.asarray(g[k], float)      # replace in place (keeps TurboFlow's own cascade_type object)
inp = tt["input"]; omega_d = inp["rpm"] * np.pi / 30; T0, p0, pout_d = inp["T04"], inp["P04"], inp["p_out"]

def run(omega, pouts, guess=None):
    op = dict(fluid_name="air", T0_in=float(T0), p0_in=float(p0), p_out=np.asarray(pouts, float), omega=float(omega), alpha_in=0.0)
    sols = tf.compute_performance(op, cfg, export_results=False, stop_on_failure=False)
    res = []
    for s in sols:
        try:
            ov = s.problem.results["overall"]
            ok = bool(getattr(s, "success", True))
            res.append(dict(omega=omega, N_frac=omega / omega_d, p_out=float(p0 / np.ravel(ov["PR_ts"])[0]),
                            PR_ts=float(np.ravel(ov["PR_ts"])[0]), PR_tt=float(np.ravel(ov["PR_tt"])[0]), eta_tt=float(np.ravel(ov["efficiency_tt"])[0]) / 100,
                            eta_ts=float(np.ravel(ov["efficiency_ts"])[0]) / 100, mdot=float(np.ravel(ov["mass_flow_rate"])[0]), success=ok))
        except Exception as e:
            res.append(dict(omega=omega, success=False, err=str(e)[:200]))
    return res

# verification at the design point
dp = run(omega_d, [pout_d])[0]
print("DESIGN CHECK:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in dp.items()},
      "design-opt mdot", round(tt["overall"]["mass_flow_rate"], 4), "eta_tt", round(tt["overall"]["efficiency_tt"] / 100, 4), flush=True)
PR_ts_d = p0 / pout_d
prs = np.unique(np.concatenate([np.linspace(1.15, PR_ts_d * 1.35, 22), [PR_ts_d]]))
rows = []
Ns = [float(v) for v in sys.argv[3].split(",")] if len(sys.argv) > 3 else (1.0, 1.1, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3)
def dump():
    json.dump(dict(design=dict(omega=omega_d, T0=T0, p0=p0, p_out=pout_d, PR_ts=PR_ts_d, check=dp,
                           opt_mdot=tt["overall"]["mass_flow_rate"], opt_eta_tt=tt["overall"]["efficiency_tt"] / 100, opt_PR_tt=tt["overall"]["PR_tt"]),
               points=rows), open(out_file, "w"), indent=1, default=float)
# TurboFlow continues each point from the previous solution; once a point fails, every later point fails
# ('list' object has no attribute 'keys'). So each speed line is swept outward from the design PR in two
# calls (up and down) and each branch stops being useful at its first failure.
i_d = int(np.argmin(abs(prs - PR_ts_d)))
for Nf in Ns:                                   # one speed line per call, file rewritten after each (a crash keeps what was done)
    r = run(omega_d * Nf, p0 / prs[i_d:]) + run(omega_d * Nf, p0 / prs[:i_d][::-1])
    ok = [x for x in r if x.get("success")]
    print(f"N {Nf:.1f}: {len(ok)}/{len(r)} converged; mdot range {min(x['mdot'] for x in ok) if ok else 0:.3f}-{max(x['mdot'] for x in ok) if ok else 0:.3f}", flush=True)
    rows += r
    dump()
