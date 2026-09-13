"""Sweep centrifugal-stage spool speed and diffuser radius ratio (calls centrifugal_design.py
in .venv-np1 for each case). Usage: python centrifugal_sweep.py mdot T01 P01 PR tag"""
import sys, os, json, subprocess, itertools
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NP1 = os.path.join(ROOT, ".venv-np1", "Scripts", "python.exe")
mdot, T01, P01, PR = [float(v) for v in sys.argv[1:5]]; tag = sys.argv[5]
RPMS = [int(v) for v in os.environ.get("CC_RPMS", "65000,75000,85000,95000").split(",")]
R4S = [float(v) for v in os.environ.get("CC_R4R2", "1.35,1.45").split(",")]
rows = []
for rpm, r4 in itertools.product(RPMS, R4S):
    fi = os.path.join(ROOT, "data", "phase3", f"cc_{tag}_{rpm}_{r4}_in.json"); fo = fi.replace("_in.json", "_out.json")
    json.dump(dict(mdot=mdot, T01=T01, P01=P01, PR=PR, rpm=rpm, beta2b_deg=-30, Z=12, tip_clearance=0.25e-3, R4R2=r4), open(fi, "w"))
    r = subprocess.run([NP1, os.path.join(ROOT, "scripts", "phase3_cycle", "centrifugal_design.py"), fi, fo], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(fo):
        print(rpm, r4, "FAILED", r.stderr[-400:]); continue
    o = json.load(open(fo)); t = o["turboflow"]
    rows.append(dict(rpm=rpm, R4R2=r4, eta_tt=t["eta"], PR=t["PR"], choked=t["choked"], ATR=o["area_throat_ratio"], M1s_rel=o["M1s_rel"],
                     U2=o["U2"], D2_mm=o["D_impeller_mm"], D4_mm=o["D_diffuser_mm"], M_vd_exit=t["M_out_vd"], b2_mm=o["geometry"]["impeller"]["width_out"] * 1e3,
                     r1s_mm=o["r1s"] * 1e3))
    print(rows[-1], flush=True)
json.dump(rows, open(os.path.join(ROOT, "data", "phase3", f"cc_sweep_{tag}.json"), "w"), indent=1)
