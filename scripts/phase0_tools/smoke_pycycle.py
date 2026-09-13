"""Phase 0 smoke test: NASA pyCycle simple single-spool turbojet (design + off-design).

Uses the upstream example_cycles/simple_turbojet.py model definition (vendored copy in
scripts/phase0_tools/vendor/) with the NumPy-2-incompatible print viewer bypassed.
Purpose: prove pyCycle installs, converges, and returns Fn/TSFC/W for a turbojet.
"""
import os, sys, numpy as np
import openmdao.api as om
import pycycle.api as pyc

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "vendor"))
os.environ["OPENMDAO_REPORTS"] = "0"
import simple_turbojet as st  # noqa: E402

prob = om.Problem()
prob.model = st.MPTurbojet()
prob.setup(check=False)

prob.set_val('DESIGN.fc.alt', 0, units='ft'); prob.set_val('DESIGN.fc.MN', 0.000001)
prob.set_val('DESIGN.balance.Fn_target', 11800.0, units='lbf')
prob.set_val('DESIGN.balance.T4_target', 2370.0, units='degR')
prob.set_val('DESIGN.comp.PR', 13.5); prob.set_val('DESIGN.comp.eff', 0.83)
prob.set_val('DESIGN.turb.eff', 0.86); prob.set_val('DESIGN.Nmech', 8070.0, units='rpm')
prob['DESIGN.balance.FAR'] = 0.0175506; prob['DESIGN.balance.W'] = 168.453135
prob['DESIGN.balance.turb_PR'] = 4.46138725; prob['DESIGN.fc.balance.Pt'] = 14.6955113
prob['DESIGN.fc.balance.Tt'] = 518.665288
for pt in ['OD0', 'OD1']:
    prob.set_val(pt + '.fc.alt', 0, units='ft'); prob.set_val(pt + '.fc.MN', 0.000001)
    prob.set_val(pt + '.balance.Fn_target', 11000., units='lbf')
    prob[pt + '.balance.W'] = 166.073; prob[pt + '.balance.FAR'] = 0.01680
    prob[pt + '.balance.Nmech'] = 8197.38; prob[pt + '.fc.balance.Pt'] = 15.703
    prob[pt + '.fc.balance.Tt'] = 558.31; prob[pt + '.turb.PR'] = 4.6690

prob.run_model()
g = lambda n, u=None: float(np.ravel(prob.get_val(n, units=u))[0])
print(f"DESIGN: Fn={g('DESIGN.perf.Fn','lbf'):.1f} lbf  W={g('DESIGN.inlet.Fl_O:stat:W','lbm/s'):.2f} lbm/s  "
      f"TSFC={g('DESIGN.perf.TSFC'):.4f} lbm/hr/lbf  OPR={g('DESIGN.perf.OPR'):.2f}  "
      f"T4={g('DESIGN.burner.Fl_O:tot:T','degR'):.0f} R")
for pt in ['OD0', 'OD1']:
    print(f"{pt}: Fn={g(pt+'.perf.Fn','lbf'):.1f} lbf  TSFC={g(pt+'.perf.TSFC'):.4f}  Nmech={g(pt+'.balance.Nmech'):.0f} rpm")
assert abs(g('DESIGN.perf.Fn', 'lbf') - 11800) < 1.0, "design balance did not converge"
print("PYCYCLE SMOKE TEST: PASS")
