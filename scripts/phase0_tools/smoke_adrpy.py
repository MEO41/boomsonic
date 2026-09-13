"""Phase 0 smoke test: ADRpy constraint analysis for a small turbojet (bpr=0) concept.
Placeholder numbers only - proves the jet branch of ADRpy runs at 25 kg scale.
Real requirements are set in Phase 1/2."""
import numpy as np
from ADRpy import constraintanalysis as ca
from ADRpy import atmospheres as at
from ADRpy import unitconversions as co

designbrief = {'rwyelevation_m': 0, 'groundrun_m': 60,           # take-off
               'stloadfactor': 2.0, 'turnalt_m': 300, 'turnspeed_ktas': 120,  # turn
               'climbalt_m': 0, 'climbspeed_kias': 90, 'climbrate_fpm': 1500,  # climb
               'cruisealt_m': 1000, 'cruisespeed_ktas': 150, 'cruisethrustfact': 0.85,  # cruise
               'servceil_m': 4000, 'secclimbspd_kias': 80,          # service ceiling
               'vstallclean_kcas': 45}
designdef = {'aspectratio': 6.0, 'sweep_le_deg': 5, 'sweep_mt_deg': 0, 'bpr': 0,
             'tr': 1.05, 'weightfractions': {'turn': 0.95, 'climb': 0.98, 'cruise': 0.9, 'servceil': 0.9}}
designperf = {'CDTO': 0.045, 'CLTO': 0.8, 'CLmaxTO': 1.4, 'CLmaxclean': 1.2, 'mu_R': 0.05,
              'CDminclean': 0.030, 'etaprop': {'take-off': 0.0, 'climb': 0.0, 'cruise': 0.0, 'turn': 0.0, 'servceil': 0.0}}
concept = ca.AircraftConcept(designbrief, designdef, designperf, at.Atmosphere(), None)
ws_pa = np.linspace(150, 800, 14)
tw = concept.twrequired(ws_pa, map2sl=True)
print("W/S [Pa]:", np.round(ws_pa, 0))
for k in ['take-off', 'turn', 'climb', 'cruise', 'servceil']:
    print(f"T/W {k:9s}:", np.round(tw[k], 3))
print("min clean stall W/S [Pa]:", concept.wsmaxcleanstall_pa())
mtow_n = 25 * 9.80665
print(f"For MTOW 25 kg ({mtow_n:.0f} N), 500 N thrust => T/W = {500/mtow_n:.2f}")
print("ADRPY SMOKE TEST: PASS")
