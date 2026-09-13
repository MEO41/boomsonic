"""Regenerate every Phase 2 output in dependency order (run with any Python; calls both venvs).

  python scripts/phase2_airframe/run_phase2.py
"""
import os, subprocess, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NP2 = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
NP1 = os.path.join(ROOT, ".venv-np1", "Scripts", "python.exe")
STEPS = [(NP2, "verify_aero_tools.py"), (NP2, "engine_database_fit.py"), (NP2, "drag_table.py"),
         (NP2, "mission_drag_polar.py"), (NP2, "mass_budget.py"), (NP2, "flutter_screening.py"),
         (NP2, "design_point_report.py"), (NP1, "constraint_diagram.py")]
for py, script in STEPS:
    t = time.time()
    r = subprocess.run([py, os.path.join(ROOT, "scripts", "phase2_airframe", script)], cwd=ROOT, capture_output=True, text=True)
    print(f"{script:28s} exit {r.returncode}  {time.time() - t:6.1f} s")
    if r.returncode != 0:
        print(r.stderr[-3000:]); sys.exit(1)
