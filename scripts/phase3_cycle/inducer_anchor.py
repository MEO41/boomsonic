"""Phase 3R: inducer relative Mach number of FIELDED micro-turbojets, as the evidence for the spool-speed limit.

The Oh loss set in TurboFlow has no shock loss, so its efficiency at high inducer relative Mach is not trustworthy, and
the Phase 3 fielded-level scaling (geometry x sqrt(W ratio) at fixed speed) raises the eye relative Mach above the
tool-level value. Instead of assuming a limit, the same optimum-inducer rule used by centrifugal_design.py (axial
inflow, eye hub/tip 0.35, shroud radius minimising W1s) is applied to every database engine with a published maximum
speed and airflow (SLS, ISA) -> the range of inducer shroud relative Mach that fielded engines of this class run at.
Then the same rule at the Phase 3R dash compressor-inlet state and FIELDED airflow for a grid of spool speeds.
Output: data/phase3r_inducer_anchor.csv
"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
R, G = 287.05, 1.4

def m1s_rel(mdot, T01, P01, rpm, k_hub=0.35):
    om = rpm * np.pi / 30; best = (np.inf, None)
    for r1s in np.linspace(0.015, 0.14, 1200):
        A = np.pi * r1s ** 2 * (1 - k_hub ** 2)
        def flux(M):
            T = T01 / (1 + 0.2 * M * M); P = P01 * (T / T01) ** 3.5
            return P / (R * T) * M * np.sqrt(G * R * T) * A
        if flux(1.0) <= mdot: continue
        lo, hi = 1e-4, 1.0
        for _ in range(50):
            mid = 0.5 * (lo + hi); lo, hi = (mid, hi) if flux(mid) < mdot else (lo, mid)
        M = 0.5 * (lo + hi); T = T01 / (1 + 0.2 * M * M); C = M * np.sqrt(G * R * T); W = np.hypot(C, om * r1s)
        if W < best[0]: best = (W, W / np.sqrt(G * R * T), r1s)
    return best[1], best[2]

if __name__ == "__main__":
    db = pd.read_csv(os.path.join(ROOT, "data", "microturbojet_database.csv")).dropna(subset=["max_rpm", "mass_flow_kgps"])
    rows = []
    for _, e in db.iterrows():
        M, r = m1s_rel(e.mass_flow_kgps, 288.15, 101325.0, e.max_rpm)
        rows.append(dict(kind="database", model=f"{e.manufacturer} {e.model}", rpm=e.max_rpm, W=e.mass_flow_kgps, M1s_rel=M, r1s_mm=r * 1e3, D_engine_mm=e.diameter_mm))
    # Phase 3R dash compressor inlet (dash_cycle: Tt2 308.9 K, Pt2 ~101.8 kPa) at the fielded airflow of each OPR
    for opr, W in ((3.5, 1.309), (4.0, 1.326), (4.5, 1.350)):
        for rpm in (70000, 72500, 75000, 77500, 80000, 85000, 95000):
            M, r = m1s_rel(W, 308.9, 101757.0, rpm)
            rows.append(dict(kind=f"Phase 3R fielded OPR {opr:g}", model="", rpm=rpm, W=W, M1s_rel=M, r1s_mm=r * 1e3))
    df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "data", "phase3r_inducer_anchor.csv"), index=False)
    pd.set_option("display.width", 200); print(df.round(3).to_string(index=False))
    d = df[df.kind == "database"]
    print(f"\ndatabase: M1s_rel {d.M1s_rel.min():.3f} - {d.M1s_rel.max():.3f} (max: {d.loc[d.M1s_rel.idxmax(), 'model']})")
