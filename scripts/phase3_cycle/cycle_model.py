"""Phase 3 single-spool turbojet cycle model (NASA pyCycle 4.4.1.dev0 / OpenMDAO 3.45).

Stations: fc -> inlet (ram recovery) -> duct (intake-duct total-pressure loss) -> comp ->
burner -> turb -> [ab] -> nozz (convergent 'CV' or convergent-divergent 'CD') -> perf.
The afterburner 'ab' (Phase 7, option afterburner=True) is off by default; with it off the model
is bit-for-bit the Phase 3 / Phase 4 model.
Thermodynamics: pyCycle TABULAR air/Jet-A equilibrium tables (AIR_JETA_TAB_SPEC, generated
from CEA chemical equilibrium) -> real-gas cp(T, FAR) and gamma(T, FAR); cross-checked with
Cantera in phase3_cycle/cantera_check.py.
Combustion efficiency: pyCycle's Combustor burns FAR completely; a combustion efficiency eta_b
is applied in post-processing as Wf_actual = Wf / eta_b (the thermodynamic state corresponds to
the heat actually released; unburnt-fuel mass, ~0.1 % of flow, is neglected).

Design modes
  design_W='Fn'   : W balanced to hit Fn_target (engine sizing)
  design_W='fixed': W is an input (vendor-engine calibration)
Off-design modes (max throttle): 'T4' (FAR holds T4max) or 'N' (FAR holds 100 % mech. speed);
the lower thrust of the two is the thrust available (ECU limits whichever is reached first).
Maps: pyCycle scaled NPSS maps (AXI5 compressor, LPT2269 turbine) are used ONLY for off-design
and remain placeholders until Phase 4 generates the real compressor/turbine maps.
"""
import os
import numpy as np
import openmdao.api as om
import pycycle.api as pyc

os.environ.setdefault("OPENMDAO_REPORTS", "0")
N2LBF = 1.0 / 4.4482216152605
K2R = 1.8
AB_MN = 0.20        # Phase 7: afterburner-duct Mach at the design point (D7.2); sets the AB duct diameter and the Rayleigh loss


class Turbojet(pyc.Cycle):
    def initialize(self):
        super().initialize()
        self.options.declare('od_mode', default='T4', values=['T4', 'N', 'NT4'])   # NT4: speed AND T4 imposed, shaft power left unbalanced (transient excess power)
        self.options.declare('design_W', default='Fn', values=['Fn', 'fixed'])
        self.options.declare('nozz_type', default='CV', values=['CV', 'CD'])
        self.options.declare('comp_map', default=None)      # Phase 4: real maps (None = placeholder AXI5 / LPT2269)
        self.options.declare('turb_map', default=None)
        self.options.declare('comp_bleed', default=False)   # Phase 4: one overboard compressor bleed port 'sb' (start / handling bleed)
        self.options.declare('afterburner', default=False)  # Phase 7: second combustor 'ab' between the turbine and the nozzle
        self.options.declare('ab_mode', default='FAR', values=['FAR', 'T7'])  # AB throttle: added fuel-air ratio, or a balance holding the AB exit temperature

    def setup(self):
        self.options['thermo_method'] = 'TABULAR'
        self.options['thermo_data'] = pyc.AIR_JETA_TAB_SPEC
        design = self.options['design']
        self.add_subsystem('fc', pyc.FlightConditions())
        self.add_subsystem('inlet', pyc.Inlet())
        self.add_subsystem('duct', pyc.Duct())
        self.add_subsystem('comp', pyc.Compressor(map_data=self.options['comp_map'] or pyc.AXI5, map_extrap=True,
                                                  bleed_names=['sb'] if self.options['comp_bleed'] else []), promotes_inputs=['Nmech'])
        self.add_subsystem('burner', pyc.Combustor(fuel_type='FAR'))
        self.add_subsystem('turb', pyc.Turbine(map_data=self.options['turb_map'] or pyc.LPT2269, map_extrap=True), promotes_inputs=['Nmech'])
        ab = self.options['afterburner']
        if ab:
            self.add_subsystem('ab', pyc.Combustor(fuel_type='FAR'))
        self.add_subsystem('nozz', pyc.Nozzle(nozzType=self.options['nozz_type'], lossCoef='Cv'))
        self.add_subsystem('shaft', pyc.Shaft(num_ports=2), promotes_inputs=['Nmech'])
        self.add_subsystem('perf', pyc.Performance(num_nozzles=1, num_burners=2 if ab else 1))

        self.pyc_connect_flow('fc.Fl_O', 'inlet.Fl_I', connect_w=False)
        self.pyc_connect_flow('inlet.Fl_O', 'duct.Fl_I')
        self.pyc_connect_flow('duct.Fl_O', 'comp.Fl_I')
        self.pyc_connect_flow('comp.Fl_O', 'burner.Fl_I')
        self.pyc_connect_flow('burner.Fl_O', 'turb.Fl_I')
        if ab:
            self.pyc_connect_flow('turb.Fl_O', 'ab.Fl_I')
            self.pyc_connect_flow('ab.Fl_O', 'nozz.Fl_I')
        else:
            self.pyc_connect_flow('turb.Fl_O', 'nozz.Fl_I')
        self.connect('comp.trq', 'shaft.trq_0')
        self.connect('turb.trq', 'shaft.trq_1')
        self.connect('fc.Fl_O:stat:P', 'nozz.Ps_exhaust')
        self.connect('inlet.Fl_O:tot:P', 'perf.Pt2')
        self.connect('comp.Fl_O:tot:P', 'perf.Pt3')
        self.connect('burner.Wfuel', 'perf.Wfuel_0')
        if ab:
            self.connect('ab.Wfuel', 'perf.Wfuel_1')
        self.connect('inlet.F_ram', 'perf.ram_drag')
        self.connect('nozz.Fg', 'perf.Fg_0')

        bal = self.add_subsystem('balance', om.BalanceComp())
        if design:
            if self.options['design_W'] == 'Fn':
                bal.add_balance('W', units='lbm/s', eq_units='lbf', rhs_name='Fn_target', val=2.0, lower=0.05)
                self.connect('balance.W', 'inlet.Fl_I:stat:W')
                self.connect('perf.Fn', 'balance.lhs:W')
            bal.add_balance('FAR', eq_units='degR', lower=1e-4, val=.017, rhs_name='T4_target')
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')
            bal.add_balance('turb_PR', val=2.0, lower=1.001, upper=8, eq_units='hp', rhs_val=0.)
            self.connect('balance.turb_PR', 'turb.PR')
            self.connect('shaft.pwr_net', 'balance.lhs:turb_PR')
        else:
            if self.options['od_mode'] == 'NT4':
                bal.add_balance('FAR', eq_units='degR', lower=1e-4, val=.017, rhs_name='T4_target')
                self.connect('balance.FAR', 'burner.Fl_I:FAR')
                self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')
            elif self.options['od_mode'] == 'T4':
                bal.add_balance('FAR', eq_units='degR', lower=1e-4, val=.017, rhs_name='T4_target')
                self.connect('balance.FAR', 'burner.Fl_I:FAR')
                self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')
                bal.add_balance('Nmech', val=1e5, units='rpm', lower=5000., eq_units='hp', rhs_val=0.)
                self.connect('balance.Nmech', 'Nmech')
                self.connect('shaft.pwr_net', 'balance.lhs:Nmech')
            else:
                bal.add_balance('FAR', lower=1e-4, val=.017, eq_units='hp', rhs_val=0.)
                self.connect('balance.FAR', 'burner.Fl_I:FAR')
                self.connect('shaft.pwr_net', 'balance.lhs:FAR')
            bal.add_balance('W', val=2.0, units='lbm/s', eq_units='inch**2', lower=0.05)
            self.connect('balance.W', 'inlet.Fl_I:stat:W')
            # Phase 4: nozzle throat area scale (variable-area nozzle); A8 = A8_scale x design area (default 1)
            self.add_subsystem('a8s', om.ExecComp('A_eq = A / A8_scale', A_eq={'units': 'inch**2'}, A={'units': 'inch**2'}, A8_scale={'val': 1.0}))
            self.connect('nozz.Throat:stat:area', 'a8s.A')
            self.connect('a8s.A_eq', 'balance.lhs:W')

        # Phase 7: AB throttle. 'FAR' sets the added fuel-air ratio directly (ab.Fl_I:FAR is then an input);
        # 'T7' balances that ratio to hit an AB exit total temperature. The bound is the upper edge of pyCycle's
        # tabular thermo FAR axis (0.05) less the main-burner FAR -- see F7.1.
        if ab and self.options['ab_mode'] == 'T7':
            bal.add_balance('ab_FAR', eq_units='degR', lower=0.0, upper=0.05, val=0.01, rhs_name='T7_target')
            self.connect('balance.ab_FAR', 'ab.Fl_I:FAR')
            self.connect('ab.Fl_O:tot:T', 'balance.lhs:ab_FAR')

        newton = self.nonlinear_solver = om.NewtonSolver()
        for k, v in dict(atol=1e-7, rtol=1e-7, iprint=-1, maxiter=40, solve_subsystems=True, max_sub_solves=100,
                         reraise_child_analysiserror=False, err_on_non_converge=False).items():
            newton.options[k] = v
        ls = newton.linesearch = om.BoundsEnforceLS()
        ls.options['bound_enforcement'] = 'scalar'; ls.options['iprint'] = -1
        self.linear_solver = om.DirectSolver()
        super().setup()


class MPTurbojet(pyc.MPCycle):
    def initialize(self):
        super().initialize()
        self.options.declare('od_points', default=[])
        self.options.declare('od_mode', default='N')
        self.options.declare('design_W', default='Fn')
        self.options.declare('nozz_type', default='CV')
        self.options.declare('comp_map', default=None)
        self.options.declare('turb_map', default=None)
        self.options.declare('comp_bleed', default=False)
        self.options.declare('afterburner', default=False)
        self.options.declare('ab_mode', default='FAR', values=['FAR', 'T7'])
        # Phase 7: the core is always SIZED dry, so the design point can carry a different AB throttle
        # mode from the off-design points. None = same as ab_mode.
        self.options.declare('ab_mode_design', default=None, values=[None, 'FAR', 'T7'])

    def setup(self):
        o = self.options
        self.pyc_add_pnt('DESIGN', Turbojet(design_W=o['design_W'], nozz_type=o['nozz_type'], comp_map=o['comp_map'], turb_map=o['turb_map'], comp_bleed=o['comp_bleed'],
                                            afterburner=o['afterburner'], ab_mode=o['ab_mode_design'] or o['ab_mode']))
        self.set_input_defaults('DESIGN.Nmech', 1e5, units='rpm')
        if o['design_W'] == 'fixed':
            self.set_input_defaults('DESIGN.inlet.Fl_I:stat:W', 1.0, units='kg/s')
        self.set_input_defaults('DESIGN.inlet.MN', 0.45)
        self.set_input_defaults('DESIGN.duct.MN', 0.45)
        self.set_input_defaults('DESIGN.comp.MN', 0.30)
        self.set_input_defaults('DESIGN.burner.MN', 0.10)
        self.set_input_defaults('DESIGN.turb.MN', 0.45)
        if o['afterburner']:
            self.set_input_defaults('DESIGN.ab.MN', AB_MN)
        self.pyc_add_cycle_param('burner.dPqP', 0.05)
        self.pyc_add_cycle_param('nozz.Cv', 0.98)
        self.pyc_add_cycle_param('inlet.ram_recovery', 1.0)
        self.pyc_add_cycle_param('duct.dPqP', 0.0)
        self.od_names = []
        for i, (mn, alt) in enumerate(o['od_points']):
            pt = f'OD{i}'; self.od_names.append(pt)
            self.pyc_add_pnt(pt, Turbojet(design=False, od_mode=o['od_mode'], nozz_type=o['nozz_type'], comp_map=o['comp_map'], turb_map=o['turb_map'], comp_bleed=o['comp_bleed'],
                                          afterburner=o['afterburner'], ab_mode=o['ab_mode']))
            self.set_input_defaults(pt + '.fc.MN', val=max(mn, 1e-6))
            self.set_input_defaults(pt + '.fc.alt', alt, units='m')
            if o['od_mode'] in ('N', 'NT4'):
                self.set_input_defaults(pt + '.Nmech', 1e5, units='rpm')
        if self.od_names:
            self.pyc_use_default_des_od_conns()
            self.pyc_connect_des_od('nozz.Throat:stat:area', 'balance.rhs:W')
        super().setup()


def build(od_points=(), od_mode='N', design_W='Fn', nozz_type='CV', comp_map=None, turb_map=None, comp_bleed=False, afterburner=False, ab_mode='FAR',
          ab_mode_design=None):
    prob = om.Problem()
    mp = prob.model = MPTurbojet(od_points=list(od_points), od_mode=od_mode, design_W=design_W, nozz_type=nozz_type, comp_map=comp_map, turb_map=turb_map,
                                 comp_bleed=comp_bleed, afterburner=afterburner, ab_mode=ab_mode, ab_mode_design=ab_mode_design)
    prob.setup(check=False)
    return prob, mp


def set_design(prob, MN, alt_m, OPR, T4_K, eta_c, eta_t, Fn_N=None, W_kgps=None, burner_dPqP=0.05, duct_dPqP=0.0,
               ram_recovery=1.0, Cv=0.98, od_names=(), od_mode='N', T4_od_K=None, ab_dPqP=None, ab_FAR=None, T7_K=None):
    prob.set_val('DESIGN.fc.alt', alt_m, units='m'); prob.set_val('DESIGN.fc.MN', max(MN, 1e-6))
    if Fn_N is not None:
        prob.set_val('DESIGN.balance.Fn_target', Fn_N * N2LBF, units='lbf')
        prob['DESIGN.balance.W'] = 2.0
    if W_kgps is not None:
        prob.set_val('DESIGN.inlet.Fl_I:stat:W', W_kgps, units='kg/s')
    prob.set_val('DESIGN.balance.T4_target', T4_K * K2R, units='degR')
    prob.set_val('DESIGN.comp.PR', OPR); prob.set_val('DESIGN.comp.eff', eta_c); prob.set_val('DESIGN.turb.eff', eta_t)
    for pt in ['DESIGN'] + list(od_names):
        prob.set_val(pt + '.burner.dPqP', burner_dPqP); prob.set_val(pt + '.duct.dPqP', duct_dPqP)
        prob.set_val(pt + '.inlet.ram_recovery', ram_recovery); prob.set_val(pt + '.nozz.Cv', Cv)
        # A point built with ab_mode 'FAR' has no T7 balance and one built with 'T7' has no free
        # ab.Fl_I:FAR, so each AB setting is applied only where that point actually has it.
        if ab_dPqP is not None: prob.set_val(pt + '.ab.dPqP', ab_dPqP)
        for nm, val, u in (('.ab.Fl_I:FAR', ab_FAR, None), ('.balance.T7_target', T7_K * K2R if T7_K is not None else None, 'degR')):
            if val is None: continue
            try: prob.set_val(pt + nm, val, units=u)
            except (KeyError, RuntimeError): pass
    prob['DESIGN.balance.FAR'] = 0.018; prob['DESIGN.balance.turb_PR'] = 2.0
    prob['DESIGN.fc.balance.Pt'] = 14.696; prob['DESIGN.fc.balance.Tt'] = 518.67
    for pt in od_names:
        prob[pt + '.balance.W'] = 2.0; prob[pt + '.balance.FAR'] = 0.018; prob[pt + '.turb.PR'] = 2.0
        prob[pt + '.fc.balance.Pt'] = 14.696; prob[pt + '.fc.balance.Tt'] = 518.67
        if od_mode == 'T4':
            prob.set_val(pt + '.balance.T4_target', (T4_od_K or T4_K) * K2R, units='degR'); prob[pt + '.balance.Nmech'] = 1e5
        elif od_mode == 'NT4':
            prob.set_val(pt + '.balance.T4_target', (T4_od_K or T4_K) * K2R, units='degR')


def seed_od_from_design(prob, pt):
    """Phase 4A: set_design seeds every off-design point with W 2.0 lbm/s, FAR 0.018, turbine PR 2.0. That converged
    for the Phase 3/4 cycles but not for the refreshed axial (eta_c 0.709, W 3.0 lbm/s, turbine PR 2.64): Newton
    diverged and left every internal state (flow stations, map R-line, turbine map PR, nozzle PR) at garbage. This
    copies every implicit state of the off-design point from its design-point counterpart (map balances from the
    design map location) and re-solves. Call after a first run_model with the OD point at the design flight condition
    and speed. Not used by any Phase 3 / 4 script (their results are unchanged)."""
    import numpy as _np
    alias = {"comp.map.map_bal.RlineMap": "comp.map.RlineMap", "comp.map.map_bal.NcMap": "comp.map.NcMap",
             "turb.map.map_bal.NpMap": "turb.map.NpMap", "turb.map.map_bal.PRmap": "turb.map.PRmap", "nozz.PR_bal.PR": "nozz.PR",
             "comp.map.SMW_bal.NcMap": "comp.map.NcMap", "turb.PR": "balance.turb_PR"}
    for name, _ in prob.model.list_outputs(implicit=True, explicit=False, out_stream=None):
        if not name.startswith(pt + "."): continue
        rel = name[len(pt) + 1:]
        for cand in (alias.get(rel), rel):
            if cand is None: continue
            try: prob[name] = _np.ravel(prob.get_val("DESIGN." + cand)).copy(); break
            except Exception: continue
    prob.run_model()


def read(prob, pt, eta_b=1.0, eta_ab=None):
    """eta_ab: Phase 7. When given, the point is assumed to carry an afterburner and its fuel
    (debited by eta_ab, the same post-processing convention as eta_b) is added to Wf."""
    g = lambda n, u=None: float(np.ravel(prob.get_val(n, units=u))[0])
    Wf = g(pt + '.burner.Wfuel', 'kg/s') / eta_b
    Wf_ab = g(pt + '.ab.Wfuel', 'kg/s') / eta_ab if eta_ab is not None else 0.0
    Wf = Wf + Wf_ab
    Fn = g(pt + '.perf.Fn', 'N')
    d = dict(MN=g(pt + '.fc.Fl_O:stat:MN'), alt_m=g(pt + '.fc.alt', 'm'), Fn_N=Fn, Fg_N=g(pt + '.perf.Fg', 'N'),
             Fram_N=g(pt + '.inlet.F_ram', 'N'), W_kgps=g(pt + '.inlet.Fl_O:stat:W', 'kg/s'), Wf_kgps=Wf,
             TSFC_kgpNh=Wf * 3600 / Fn if Fn > 0 else np.nan, FAR=g(pt + '.balance.FAR') / 1.0,
             OPR=g(pt + '.perf.OPR'), comp_PR=g(pt + '.comp.PR'),
             Pt2_kPa=g(pt + '.duct.Fl_O:tot:P', 'kPa'), Tt2_K=g(pt + '.duct.Fl_O:tot:T', 'degK'),
             Pt3_kPa=g(pt + '.comp.Fl_O:tot:P', 'kPa'), Tt3_K=g(pt + '.comp.Fl_O:tot:T', 'degK'),
             Pt4_kPa=g(pt + '.burner.Fl_O:tot:P', 'kPa'), Tt4_K=g(pt + '.burner.Fl_O:tot:T', 'degK'),
             Pt5_kPa=g(pt + '.turb.Fl_O:tot:P', 'kPa'), Tt5_K=g(pt + '.turb.Fl_O:tot:T', 'degK'),
             turb_PR=g(pt + '.turb.PR'), comp_pwr_kW=-g(pt + '.comp.power', 'kW'),
             Wc2_kgps=g(pt + '.comp.Fl_I:stat:W', 'kg/s') * np.sqrt(g(pt + '.duct.Fl_O:tot:T', 'degK') / 288.15) / (g(pt + '.duct.Fl_O:tot:P', 'kPa') / 101.325),
             NPR=g(pt + '.nozz.PR'), Vj_mps=g(pt + '.nozz.Fl_O:stat:V', 'm/s'), A8_cm2=g(pt + '.nozz.Throat:stat:area', 'm**2') * 1e4,
             Nmech=g(pt + '.Nmech', 'rpm'), comp_eff=g(pt + '.comp.eff'), turb_eff=g(pt + '.turb.eff'),
             res=float(prob.model._get_subsystem(pt)._residuals.get_norm()))
    if eta_ab is not None:
        d.update(Wf_ab_kgps=Wf_ab, Wf_main_kgps=Wf - Wf_ab, FAR_ab=g(pt + '.ab.Fl_I:FAR'),
                 FAR_total=float(np.ravel(prob.get_val(pt + '.ab.Fl_O:tot:composition'))[0]),
                 Tt7_K=g(pt + '.ab.Fl_O:tot:T', 'degK'), Pt7_kPa=g(pt + '.ab.Fl_O:tot:P', 'kPa'),
                 ab_dPqP=g(pt + '.ab.dPqP'), ab_MN=g(pt + '.ab.Fl_O:stat:MN'),
                 ab_area_cm2=g(pt + '.ab.Fl_O:stat:area', 'm**2') * 1e4)
    # static state at compressor inlet / exit (for turbomachinery sizing)
    for st, name in (('duct.Fl_O', 'c_in'), ('comp.Fl_O', 'c_out'), ('burner.Fl_O', 't_in'), ('turb.Fl_O', 't_out')):
        try:
            d[name + '_gamma'] = g(f'{pt}.{st}:tot:gamma'); d[name + '_Cp'] = g(f'{pt}.{st}:tot:Cp', 'J/(kg*degK)')
        except Exception:
            pass
    return d
