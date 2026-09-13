"""Phase 0 smoke test: Cantera kerosene-surrogate combustion at micro-turbojet combustor conditions."""
import cantera as ct
print("cantera", ct.__version__)
g = ct.Solution("nDodecane_Reitz.yaml")          # n-dodecane = common Jet-A/kerosene surrogate, 100 species
g.TP = 470.0, 4e5                                 # ~OPR 4 combustor inlet (T3, P3)
g.set_equivalence_ratio(0.30, "c12h26", "O2:1.0, N2:3.76")
g.equilibrate("HP")
print(f"phi=0.30: T_ad={g.T:.1f} K  gamma_products={g.cp/g.cv:.4f}  cp={g.cp_mass:.1f} J/kg-K")
air = ct.Solution("air.yaml"); air.TP = 288.15, 101325
print(f"ISA SL air: cp={air.cp_mass:.1f} J/kg-K  gamma={air.cp/air.cv:.4f}")
assert 1150 < g.T < 1350
print("CANTERA SMOKE TEST: PASS")
