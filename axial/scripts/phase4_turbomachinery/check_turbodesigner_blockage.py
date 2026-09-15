"""Evidence for the Phase 3 blockage-input error: TurboDesigner 2.0.0 FlowStation.physical_area =
flow_area * (1 + blockage) (flow_station.py), and its README example uses blockage 0.0. Phase 3 passed
0.98 / 0.96 (meant as effective/physical area ratios), which nearly doubled every annulus area.
Prints the inlet annulus and continuity check for both inputs at the Phase 3 design inputs."""
import os, sys, json, numpy as np
AXROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
import axial_design as ad
p = dict(mdot=1.052167931905524, T01=308.90466137184205, P01=101701.5430887929, PR=5.0, rpm=65000, N=5, hub_tip=0.4, Cx=200, clearance=0.25e-3)
for blk in ((0.98, 0.96), (0.02, 0.04)):
    q = dict(p, blk_in=blk[0], blk_out=blk[1]); tm = ad.build(q, 0.841)
    rt, rh = tm.inlet_tip_radius, tm.inlet_hub_radius; A = np.pi * (rt ** 2 - rh ** 2)
    T1 = p["T01"] - (200 / np.cos(np.radians(22.04))) ** 2 / (2 * 1004.7); P1 = p["P01"] * (T1 / p["T01"]) ** 3.5; rho = P1 / (287.05 * T1)
    print(f"blockage input {blk}: inlet r_tip {rt*1e3:.1f} mm, r_hub {rh*1e3:.1f} mm, annulus {A*1e4:.1f} cm2; "
          f"continuity at Cx 200 m/s needs {p['mdot']/(rho*200)*1e4:.1f} cm2 -> effective/physical {p['mdot']/(rho*200)/A:.3f}")
