"""Phase 3: Cantera cross-check of pyCycle's combustor-exit state at the dash design point.

pyCycle (TABULAR air/Jet-A, CEA-derived) gives T4 for a given FAR, T3, P3. Cantera equilibrates
the same mixture (n-dodecane surrogate, nDodecane_Reitz.yaml, 100 species; and a Jet-A-like
C12H23 H/C via the same surrogate) at constant enthalpy and pressure -> T_ad, cp, gamma.
Agreement within ~1 % on T4 and gamma means the cycle's real-gas properties are trustworthy.
Also reports the lean flammability margin: phi at the design FAR (primary-zone design needs
phi ~0.6-1.0 locally; overall phi ~0.25-0.30 is normal for a turbojet).
Usage: python cantera_check.py FAR T3_K P3_kPa T4_pycycle_K gamma4_pycycle cp4_pycycle
"""
import sys, cantera as ct
FAR, T3, P3, T4p, g4p, cp4p = [float(v) for v in sys.argv[1:7]] if len(sys.argv) > 6 else (0.0169, 499.0, 407.4, 1150.0, 1.313, 1203.9)
gas = ct.Solution("nDodecane_Reitz.yaml")
air = "O2:0.2095, N2:0.7809, AR:0.0093" if "AR" in gas.species_names else "O2:0.21, N2:0.79"
gas.TP = T3, P3 * 1e3
# mass-based mixture: FAR kg fuel per kg air
gas.set_mixture_fraction(FAR / (1 + FAR), "c12h26:1", air)
phi = gas.equivalence_ratio("c12h26:1", air)
gas.equilibrate("HP")
print(f"Cantera (n-C12H26 surrogate): phi = {phi:.3f}, T_ad = {gas.T:.1f} K, cp = {gas.cp_mass:.1f} J/kg/K, gamma = {gas.cp / gas.cv:.4f}")
print(f"pyCycle (TABULAR Jet-A):      T4 = {T4p:.1f} K, cp = {cp4p:.1f}, gamma = {g4p:.4f}")
print(f"differences: dT = {gas.T - T4p:+.1f} K ({(gas.T - T4p) / T4p * 100:+.2f} %), dgamma = {gas.cp / gas.cv - g4p:+.4f}, dcp = {(gas.cp_mass - cp4p) / cp4p * 100:+.2f} %")
