"""Phase 0 smoke test: NASA turbo-design (GitHub main, v1.4.3) centrifugal module.
Runs the upstream HECC validation fixture (NASA High-Efficiency Centrifugal Compressor,
NASA/CR-2014-218114) vendored under vendor/turbodesign_tests, with data under vendor/data/hecc.
Expected: eta_poly within ~0.5 pt and PR_tt within ~2 % of NASA measured values."""
import os, runpy, sys
HERE = os.path.dirname(os.path.abspath(__file__))
fixture = os.path.join(HERE, "vendor", "turbodesign_tests", "fixtures", "hecc_stage.py")
os.chdir(os.path.dirname(fixture))
sys.argv = [fixture]
runpy.run_path(fixture, run_name="__main__")
print("TURBODESIGN SMOKE TEST: PASS (see printed model-vs-NASA table)")
