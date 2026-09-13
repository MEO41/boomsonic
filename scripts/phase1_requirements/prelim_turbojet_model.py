"""Phase 1 preliminary single-spool turbojet model (pyCycle) for thrust-available lapse.

Purpose: quantify what a 500 N SLS-rated turbojet delivers at Mach 1 across altitude so the
mission profile can be chosen on numbers. This is NOT the Phase 3 cycle model: component
efficiencies, OPR and T4 are placeholders typical of the 100-1000 N micro-turbojet class,
and the compressor/turbine maps are pyCycle's scaled NPSS maps (AXI5 / LPT2269), flagged as
placeholders in tools_survey.md section 3.

Off-design "max throttle" is modelled two ways and the lower thrust is taken per point:
  mode 'T4': FAR balanced to hold T4 = T4max (temperature-limited, hot/low-altitude side)
  mode 'N' : FAR balanced to hold Nmech = 100 % design speed (speed-limited, cold/high side)
This mimics a real ECU that limits whichever of EGT or RPM is reached first.
"""
import os
import numpy as np
import openmdao.api as om
import pycycle.api as pyc

os.environ.setdefault("OPENMDAO_REPORTS", "0")

# ---- placeholder engine parameters (Phase 3 trades these) --------------------------------
# Sources for the ranges: Kamps, "Model Jet Engines" (3rd ed.) ch. 2-3 (KJ66-class: PR 2.5-3.2,
# T4 ~ 1000-1150 K, eta_c ~ 0.72-0.78); JetCat / AMT published data (P300-P550 / Titan class:
# PR 3.5-4.5, EGT 900-1000 K -> T4 ~ 1150-1250 K). Chosen mid-range values:
ENGINE = dict(
    Fn_SLS_N=500.0,     # rating: uninstalled net thrust, SLS ISA (assumption A0.1)
    OPR=4.0,            # compressor pressure ratio (placeholder)
    T4_K=1150.0,        # turbine entry total temperature (placeholder)
    eta_c=0.78,         # compressor adiabatic efficiency (placeholder)
    eta_t=0.85,         # turbine adiabatic efficiency (placeholder)
    Nmech_rpm=100000.0, # only sets map speed scaling; not a physical result here
    burner_dPqP=0.05,   # combustor total pressure loss fraction
    nozz_Cv=0.98,       # convergent nozzle velocity coefficient
    inlet_MN=0.45,
)

N2LBF = 1.0 / 4.4482216152605
K2R = 1.8


class Turbojet(pyc.Cycle):
    def initialize(self):
        super().initialize()
        self.options.declare('od_mode', default='T4', values=['T4', 'N'])

    def setup(self):
        self.options['thermo_method'] = 'TABULAR'
        self.options['thermo_data'] = pyc.AIR_JETA_TAB_SPEC
        design = self.options['design']

        self.add_subsystem('fc', pyc.FlightConditions())
        self.add_subsystem('inlet', pyc.Inlet())
        self.add_subsystem('comp', pyc.Compressor(map_data=pyc.AXI5, map_extrap=True), promotes_inputs=['Nmech'])
        self.add_subsystem('burner', pyc.Combustor(fuel_type='FAR'))
        self.add_subsystem('turb', pyc.Turbine(map_data=pyc.LPT2269, map_extrap=True), promotes_inputs=['Nmech'])
        self.add_subsystem('nozz', pyc.Nozzle(nozzType='CV', lossCoef='Cv'))   # convergent nozzle (micro-turbojet practice)
        self.add_subsystem('shaft', pyc.Shaft(num_ports=2), promotes_inputs=['Nmech'])
        self.add_subsystem('perf', pyc.Performance(num_nozzles=1, num_burners=1))

        self.pyc_connect_flow('fc.Fl_O', 'inlet.Fl_I', connect_w=False)
        self.pyc_connect_flow('inlet.Fl_O', 'comp.Fl_I')
        self.pyc_connect_flow('comp.Fl_O', 'burner.Fl_I')
        self.pyc_connect_flow('burner.Fl_O', 'turb.Fl_I')
        self.pyc_connect_flow('turb.Fl_O', 'nozz.Fl_I')
        self.connect('comp.trq', 'shaft.trq_0')
        self.connect('turb.trq', 'shaft.trq_1')
        self.connect('fc.Fl_O:stat:P', 'nozz.Ps_exhaust')
        self.connect('inlet.Fl_O:tot:P', 'perf.Pt2')
        self.connect('comp.Fl_O:tot:P', 'perf.Pt3')
        self.connect('burner.Wfuel', 'perf.Wfuel_0')
        self.connect('inlet.F_ram', 'perf.ram_drag')
        self.connect('nozz.Fg', 'perf.Fg_0')

        balance = self.add_subsystem('balance', om.BalanceComp())
        if design:
            balance.add_balance('W', units='lbm/s', eq_units='lbf', rhs_name='Fn_target', val=2.0, lower=0.1)
            self.connect('balance.W', 'inlet.Fl_I:stat:W')
            self.connect('perf.Fn', 'balance.lhs:W')
            balance.add_balance('FAR', eq_units='degR', lower=1e-4, val=.017, rhs_name='T4_target')
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')
            balance.add_balance('turb_PR', val=2.0, lower=1.001, upper=8, eq_units='hp', rhs_val=0.)
            self.connect('balance.turb_PR', 'turb.PR')
            self.connect('shaft.pwr_net', 'balance.lhs:turb_PR')
        else:
            if self.options['od_mode'] == 'T4':
                balance.add_balance('FAR', eq_units='degR', lower=1e-4, val=.017, rhs_name='T4_target')
                self.connect('balance.FAR', 'burner.Fl_I:FAR')
                self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')
                balance.add_balance('Nmech', val=100000., units='rpm', lower=5000., eq_units='hp', rhs_val=0.)
                self.connect('balance.Nmech', 'Nmech')
                self.connect('shaft.pwr_net', 'balance.lhs:Nmech')
            else:  # 'N': hold mechanical speed at N_target; FAR found from the shaft power balance
                balance.add_balance('FAR', lower=1e-4, val=.017, eq_units='hp', rhs_val=0.)
                self.connect('balance.FAR', 'burner.Fl_I:FAR')
                self.connect('shaft.pwr_net', 'balance.lhs:FAR')
            balance.add_balance('W', val=2.0, units='lbm/s', eq_units='inch**2', lower=0.1)
            self.connect('balance.W', 'inlet.Fl_I:stat:W')
            self.connect('nozz.Throat:stat:area', 'balance.lhs:W')

        newton = self.nonlinear_solver = om.NewtonSolver()
        newton.options['atol'] = 1e-6
        newton.options['rtol'] = 1e-6
        newton.options['iprint'] = -1
        newton.options['maxiter'] = 40
        newton.options['solve_subsystems'] = True
        newton.options['max_sub_solves'] = 100
        newton.options['reraise_child_analysiserror'] = False
        newton.options['err_on_non_converge'] = False
        ls = newton.linesearch = om.BoundsEnforceLS()
        ls.options['bound_enforcement'] = 'scalar'
        ls.options['iprint'] = -1
        self.linear_solver = om.DirectSolver()
        super().setup()


class MPTurbojet(pyc.MPCycle):
    """Design point + a list of off-design (MN, alt_m) points, all at max throttle in one mode."""
    def initialize(self):
        super().initialize()
        self.options.declare('od_points', default=[])   # list of (MN, alt_m)
        self.options.declare('od_mode', default='T4')

    def setup(self):
        E = ENGINE
        self.pyc_add_pnt('DESIGN', Turbojet())
        self.set_input_defaults('DESIGN.Nmech', E['Nmech_rpm'], units='rpm')
        self.set_input_defaults('DESIGN.inlet.MN', E['inlet_MN'])
        self.set_input_defaults('DESIGN.comp.MN', 0.30)
        self.set_input_defaults('DESIGN.burner.MN', 0.10)
        self.set_input_defaults('DESIGN.turb.MN', 0.45)
        self.pyc_add_cycle_param('burner.dPqP', E['burner_dPqP'])
        self.pyc_add_cycle_param('nozz.Cv', E['nozz_Cv'])
        self.pyc_add_cycle_param('inlet.ram_recovery', 0.98)

        self.od_names = []
        for i, (mn, alt) in enumerate(self.options['od_points']):
            pt = f'OD{i}'
            self.od_names.append(pt)
            self.pyc_add_pnt(pt, Turbojet(design=False, od_mode=self.options['od_mode']))
            self.set_input_defaults(pt + '.fc.MN', val=max(mn, 1e-6))
            self.set_input_defaults(pt + '.fc.alt', alt, units='m')
            if self.options['od_mode'] == 'T4':
                self.set_input_defaults(pt + '.balance.T4_target', E['T4_K'] * K2R, units='degR')
            else:
                self.set_input_defaults(pt + '.Nmech', E['Nmech_rpm'], units='rpm')

        self.pyc_use_default_des_od_conns()
        self.pyc_connect_des_od('nozz.Throat:stat:area', 'balance.rhs:W')
        super().setup()


def build_and_run(od_points, od_mode='T4', verbose=False, des_MN=1e-6, des_alt_m=0.0, Fn_des_N=None):
    """Return (prob, mp) with DESIGN at Fn_des_N (default ENGINE Fn_SLS_N) at (des_MN, des_alt_m) and all od_points solved at max throttle."""
    E = ENGINE
    prob = om.Problem()
    mp = prob.model = MPTurbojet(od_points=od_points, od_mode=od_mode)
    prob.setup(check=False)
    prob.set_val('DESIGN.fc.alt', des_alt_m, units='m')
    prob.set_val('DESIGN.fc.MN', max(des_MN, 1e-6))
    prob.set_val('DESIGN.balance.Fn_target', (Fn_des_N or E['Fn_SLS_N']) * N2LBF, units='lbf')
    prob.set_val('DESIGN.balance.T4_target', E['T4_K'] * K2R, units='degR')
    prob.set_val('DESIGN.comp.PR', E['OPR'])
    prob.set_val('DESIGN.comp.eff', E['eta_c'])
    prob.set_val('DESIGN.turb.eff', E['eta_t'])
    prob['DESIGN.balance.FAR'] = 0.018
    prob['DESIGN.balance.W'] = 2.0
    prob['DESIGN.balance.turb_PR'] = 2.0
    prob['DESIGN.fc.balance.Pt'] = 14.696
    prob['DESIGN.fc.balance.Tt'] = 518.67
    for pt in mp.od_names:
        prob[pt + '.balance.W'] = 2.0
        prob[pt + '.balance.FAR'] = 0.018
        if od_mode == 'T4':
            prob[pt + '.balance.Nmech'] = E['Nmech_rpm']
        prob[pt + '.turb.PR'] = 2.0
        prob[pt + '.fc.balance.Pt'] = 14.696
        prob[pt + '.fc.balance.Tt'] = 518.67
    prob.run_model()
    return prob, mp


def read_point(prob, pt):
    g = lambda n, u=None: float(np.ravel(prob.get_val(n, units=u))[0])
    return dict(
        MN=g(pt + '.fc.Fl_O:stat:MN'), alt_m=g(pt + '.fc.alt', 'm'),
        Fn_N=g(pt + '.perf.Fn', 'N'), Fg_N=g(pt + '.perf.Fg', 'N'), Fram_N=g(pt + '.inlet.F_ram', 'N'),
        W_kgps=g(pt + '.inlet.Fl_O:stat:W', 'kg/s'), Wf_kgps=g(pt + '.burner.Wfuel', 'kg/s'),
        TSFC_kgpNh=g(pt + '.perf.TSFC', 'lbm/(h*lbf)') * 0.45359237 / 4.4482216,
        OPR=g(pt + '.perf.OPR'), T4_K=g(pt + '.burner.Fl_O:tot:T', 'degK'),
        T2_K=g(pt + '.inlet.Fl_O:tot:T', 'degK'), Nmech=g(pt + '.Nmech', 'rpm'),
        NcPct=g(pt + '.comp.map.NcMap') * 100.0 if pt != 'DESIGN' else 100.0,
        comp_PR=g(pt + '.comp.PR'), comp_eff=g(pt + '.comp.eff'), turb_eff=g(pt + '.turb.eff'),
        NPR=g(pt + '.nozz.PR'), Vj_mps=g(pt + '.nozz.Fl_O:stat:V', 'm/s'),
        resid=float(np.abs(prob.model._get_subsystem(pt)._residuals.asarray()).max()) if hasattr(prob.model._get_subsystem(pt), '_residuals') else np.nan,
    )
