"""Phase 0 smoke test: TurboFlow (turbo-sim) centrifugal-compressor meanline performance.
Run with the NumPy-1 env:  .venv-np1/Scripts/python scripts/phase0_tools/smoke_turboflow.py
Uses the upstream example (Zhang et al. compressor: 0.45 kg/s, 52 krpm, 143 mm impeller)."""
import os, turboflow as tf
HERE = os.path.dirname(os.path.abspath(__file__))
cfg = tf.load_config(os.path.join(HERE, "vendor", "turboflow_examples", "compressor_config.yaml"))
solvers = tf.centrifugal_compressor.compute_performance(cfg, cfg["operation_points"], export_results=False)
r = solvers[0].problem.results["overall"]
print(f"eta_tt={r['efficiency_tt']:.2f} %  PR_tt={r['PR_tt']:.3f}  choked={solvers[0].problem.results['impeller']['throat_plane']['choked']}")
assert 2.5 < r["PR_tt"] < 2.8
print("TURBOFLOW SMOKE TEST: PASS")
