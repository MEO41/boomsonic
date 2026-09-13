"""Phase 3 centrifugal compressor stage design (run in .venv-np1: TurboFlow 0.1.18 + CoolProp).

  .venv-np1/Scripts/python scripts/phase3_cycle/centrifugal_design.py <in.json> <out.json>

1. Meanline pre-sizing (Dixon & Hall, Fluid Mechanics and Thermodynamics of Turbomachinery,
   7th ed., ch. 7; Aungier, Centrifugal Compressors, 2000):
   - inducer: axial inflow, hub/tip ratio 0.35 at the eye, shroud radius chosen to MINIMISE the
     inducer shroud relative Mach number (Dixon & Hall sec. 7.x optimum inducer);
   - exit: backswept blade beta2b, Wiesner slip sigma = 1 - sqrt(cos beta2b)/Z^0.7, exit flow
     coefficient phi2 = Cm2/U2; U2 from the Euler work for the target pressure ratio;
   - b2 from continuity at the exit static state; axial length 0.65 r2 (TurboFlow example ratio);
   - vaneless space to r3 = 1.06 r2; radial vaned diffuser r3 -> r4 = R4R2 * r2 (vane LE angle =
     flow angle at r3, TE 34 deg as in TurboFlow's NASA-derived example), then axial deswirl.
2. TurboFlow centrifugal performance (Oh loss set, Wiesner slip, algebraic vaneless model,
   'custom' vaned-diffuser loss, throat choking check) at the design (mdot, omega).
3. Secant iteration on r2 (i.e. tip speed) until TurboFlow's PR_tt equals the target.
Outputs geometry, eta_tt, PR, tip speed, inducer relative Mach, diffuser exit Mach, choke flag.
"""
import sys, json, copy, numpy as np
import CoolProp.CoolProp as CP
import turboflow as tf

inp = json.load(open(sys.argv[1]))
mdot, T01, P01, PR_t = inp["mdot"], inp["T01"], inp["P01"], inp["PR"]
omega = inp["rpm"] * np.pi / 30
beta2b = inp.get("beta2b_deg", -30.0); Z = inp.get("Z", 12); tip_cl = inp.get("tip_clearance", 0.25e-3)
R4R2 = inp.get("R4R2", 1.45); k_hub = inp.get("hub_tip_eye", 0.35); phi2 = inp.get("phi2", 0.28)
R, g, cp = 287.05, 1.4, 1004.5

# ---- inducer: minimise W1s ----
def inducer(r1s):
    """axial inflow through the eye annulus: subsonic Mach from continuity (bisection); inf if choked."""
    A = np.pi * r1s ** 2 * (1 - k_hub ** 2)
    def flux(M):
        T = T01 / (1 + 0.2 * M * M); P = P01 * (T / T01) ** (g / (g - 1))
        return P / (R * T) * M * np.sqrt(g * R * T) * A
    if flux(1.0) <= mdot: return np.inf, np.nan, np.nan
    lo, hi = 1e-4, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if flux(mid) < mdot: lo = mid
        else: hi = mid
    M = 0.5 * (lo + hi); T = T01 / (1 + 0.2 * M * M); C = M * np.sqrt(g * R * T)
    return float(np.hypot(C, omega * r1s)), float(C), float(T)
rs = np.linspace(0.02, 0.12, 400)
Ws = [inducer(r)[0] for r in rs]
r1s = float(rs[int(np.argmin(Ws))]); W1s, C1, T1 = inducer(r1s)
r1h = k_hub * r1s; r1rms = np.sqrt(0.5 * (r1s ** 2 + r1h ** 2))
M1s_rel = W1s / np.sqrt(g * R * T1)
beta1b = float(np.degrees(np.arctan(omega * r1rms / C1)))

ATR = [inp.get('area_throat_ratio', 0.5)]

def geometry(r2):
    U2 = omega * r2
    sigma = 1 - np.sqrt(np.cos(np.radians(abs(beta2b)))) / Z ** 0.7
    Ct2 = U2 * (sigma - phi2 * np.tan(np.radians(abs(beta2b)))); Cm2 = phi2 * U2
    dh0 = U2 * Ct2
    T02 = T01 + dh0 / cp; C2 = np.hypot(Ct2, Cm2); T2 = T02 - C2 ** 2 / (2 * cp)
    P02 = P01 * (1 + 0.92 * dh0 / (cp * T01)) ** (g / (g - 1))
    P2 = P02 * (T2 / T02) ** (g / (g - 1)); rho2 = P2 / (R * T2)
    b2 = mdot / (2 * np.pi * r2 * rho2 * Cm2 * 0.95)
    r3 = 1.06 * r2; r4 = R4R2 * r2
    alpha3 = float(np.degrees(np.arctan2(Ct2 * r2 / r3, Cm2 * r2 / r3)))    # free vortex + continuity in vaneless space
    geo = dict(
        impeller=dict(radius_hub_in=r1h, radius_tip_in=r1s, radius_out=r2, width_out=b2, leading_edge_angle=beta1b,
                      trailing_edge_angle=beta2b, number_of_blades=Z, length_axial=0.65 * r2, length_meridional=0.70 * r2,
                      tip_clearance=tip_cl, area_throat_ratio=ATR[0]),
        vaneless_diffuser=dict(width_out=b2, radius_out=r3, radius_in=r2, width_in=b2),
        vaned_diffuser=dict(radius_out=r4, radius_in=r3, width_in=b2, width_out=b2, leading_edge_angle=alpha3,
                            trailing_edge_angle=34.0, number_of_vanes=inp.get("Z_vd", 19), opening=2 * np.pi * r4,
                            throat_location_factor=1.0, area_throat_ratio=0.5))
    return geo, dict(U2=U2, dh0_euler=dh0, T02_est=T02, Ct2=Ct2, Cm2=Cm2, sigma=sigma, alpha3=alpha3)

base = dict(turbomachinery="centrifugal_compressor",
            operation_points=dict(fluid_name="air", T0_in=T01, p0_in=P01, mass_flow_rate=mdot, omega=omega, alpha_in=0.0),
            simulation_options=dict(slip_model="wiesner",
                                    loss_model=dict(impeller=dict(model="oh", loss_coefficient="static_enthalpy_loss"),
                                                    vaneless_diffuser=dict(model="oh", loss_coefficient="static_enthalpy_loss"),
                                                    vaned_diffuser=dict(model="custom", loss_coefficient="static_enthalpy_loss")),
                                    vaneless_diffuser_model="algebraic", rel_step_fd=1e-4,
                                    factors=dict(skin_friction=0.02, wall_heat_flux=0.0, wake_width=0.366),
                                    choking_criterion="evaluate_throat"),
            performance_analysis=dict(performance_map=dict(fluid_name="air", T0_in=T01, p0_in=P01, mass_flow_rate=mdot, omega=omega, alpha_in=0.0),
                                      solver_options=dict(method="hybr", tolerance=1e-8, max_iterations=100, derivative_method="2-point",
                                                          derivative_abs_step=1e-6, plot_convergence=False, print_convergence=False),
                                      initial_guess=dict(efficiency_impeller=[0.70, 0.95], phi_impeller=[0.15, 0.45], Ma_vaned_diffuser=[0.10, 0.50], n_samples=30)))

def run(r2):
    geo, mean = geometry(r2)
    cfg = copy.deepcopy(base); cfg["geometry"] = geo
    cfg = tf.convert_configuration_options(cfg) if hasattr(tf, "convert_configuration_options") else cfg
    solvers = tf.centrifugal_compressor.compute_performance(cfg, cfg["operation_points"], export_results=False, stop_on_failure=True)
    s = solvers[0]; r = s.problem.results
    ok = bool(getattr(s, "success", True))
    return dict(PR=float(r["overall"]["PR_tt"]), eta=float(r["overall"]["efficiency_tt"]) / 100, power=float(r["overall"]["power"]),
                choked=bool(r["impeller"]["throat_plane"]["choked"]) if "choked" in r["impeller"]["throat_plane"] else None,
                M_out_vd=float(r["vaned_diffuser"]["exit_plane"]["Ma"]) if "Ma" in r["vaned_diffuser"]["exit_plane"] else np.nan,
                M_rel_in=float(r["impeller"]["inlet_plane"]["Ma_rel"]) if "Ma_rel" in r["impeller"]["inlet_plane"] else np.nan,
                success=ok), geo, mean

# initial r2 from Euler work at eta 0.80
dh_req = cp * T01 * (PR_t ** ((g - 1) / g) - 1) / 0.80
sig = 1 - np.sqrt(np.cos(np.radians(abs(beta2b)))) / Z ** 0.7
r2 = np.sqrt(dh_req / (sig - phi2 * np.tan(np.radians(abs(beta2b))))) / omega
hist = []
x0, f0 = None, None
for it in range(10):
    try:
        res, geo, mean = run(r2)
        while res["choked"] and ATR[0] < 0.85:          # open the inducer throat until the design point is not choked
            ATR[0] = round(ATR[0] + 0.05, 3); res, geo, mean = run(r2)
    except Exception as e:
        hist.append(dict(r2=r2, error=str(e)[:200])); r2 *= 0.97; continue
    f = res["PR"] - PR_t
    hist.append(dict(r2=r2, **res))
    if abs(f) < 0.005 * PR_t: break
    if x0 is None:
        x1 = r2 * (1 + 0.5 * (PR_t / res["PR"] - 1) * 0.5)
    else:
        x1 = r2 - f * (r2 - x0) / (f - f0) if f != f0 else r2 * 1.01
    x0, f0, r2 = r2, f, float(np.clip(x1, 0.7 * r2, 1.3 * r2))
out = dict(input=inp, area_throat_ratio=ATR[0], r1s=r1s, r1h=r1h, beta1b=beta1b, M1s_rel=M1s_rel, C1=C1, r2=r2, U2=omega * r2, geometry=geo, meanline=mean,
           turboflow=res, history=hist, D_impeller_mm=2e3 * r2, D_diffuser_mm=2e3 * geo["vaned_diffuser"]["radius_out"])
json.dump(out, open(sys.argv[2], "w"), indent=1, default=float)
print(json.dumps({k: v for k, v in out.items() if k not in ("geometry", "history", "input")}, default=float, indent=0))
