"""Phase 3 axial compressor design: TurboDesigner 2.0.0 geometry + own verified meanline loss model.

Why not a tool-only efficiency: none of the approved tools predicts axial-compressor efficiency
(NASA turbo-design: Lieblein module empty, OTAC models are zero-returning placeholders,
DiffusionLoss is an ad-hoc ramp; TurboDesigner takes efficiency as an INPUT; TurboFlow has no
axial compressor). So TurboDesigner supplies the geometry and velocity triangles (free vortex,
equal stage temperature rise, 50 % reaction) and the loss is computed with the Howell
cascade method as given in Saravanamuttoo, Rogers, Cohen, Straznicky & Nix, "Gas Turbine
Theory" (7th ed.), ch. 5 (stage performance from cascade drag coefficients):
    CL  = 2 (s/c) cos(a_m) (tan a1 - tan a2) - CD tan(a_m),  tan a_m = (tan a1 + tan a2)/2
    CD  = CDp + CDa + CDs,  CDp = 0.018 (Howell design-incidence profile drag) x Re factor,
          CDa = 0.020 s/h (annulus), CDs = 0.018 CL^2 (secondary)
    eta_row = 1 - 2 CD / (CL sin 2 a_m)            (50 % reaction: stage eta ~ row eta)
Small-scale penalties added explicitly:
    Reynolds: CDp x (Re_c / 3e5)^-0.2 for Re_c < 3e5 (cascade data base Re ~3e5), capped at 1.5x
    tip clearance (rotors): -2.0 efficiency points per 1 % clearance/blade height (Freeman 1985,
          as reported in Cumpsty, Compressor Aerodynamics, ch. 9); stators assumed shrouded (no loss)
    transonic rotor tip: normal-shock relative total-pressure loss at the tip relative Mach,
          applied to the annulus fraction with M_rel > 1 (Miller, Lewis & Hartmann 1961 approach)
TurboDesigner's own rotor diffusion factor is WRONG (uses absolute velocities: ~0.03 vs the
stator's 0.40 in a 50 %-reaction stage), so DF is recomputed here from the relative triangles.
Iterates TurboDesigner's efficiency input until it equals the loss-model efficiency.
Usage: python axial_design.py <in.json> <out.json>
"""
import sys, json, numpy as np
from turbodesigner.turbomachinery import Turbomachinery
from turbodesigner.stage import StageBladeProperty

R_AIR = 287.05

def normal_shock_pt_ratio(M, g=1.4):
    if M <= 1: return 1.0
    return ((g + 1) * M * M / ((g - 1) * M * M + 2)) ** (g / (g - 1)) * ((g + 1) / (2 * g * M * M - (g - 1))) ** (1 / (g - 1))

def build(p, eta):
    return Turbomachinery(gamma=1.4, axial_velocity=p["Cx"], rpm=p["rpm"], gas_constant=R_AIR, mass_flow_rate=p["mdot"],
        pressure_ratio=p["PR"], inlet_total_pressure=p["P01"], inlet_total_temperature=p["T01"], isentropic_efficiency=eta,
        num_stages=p["N"], inlet_blockage=0.98, outlet_blockage=0.96, hub_to_tip_ratio=p["hub_tip"], num_streams=3,
        stage_temperature_rise="equal", stage_reaction=0.5, row_gap_to_chord=0.25, stage_gap_to_chord=0.25,
        aspect_ratio=StageBladeProperty(rotor=p.get("AR", 1.5), stator=p.get("AR", 1.5)),
        spacing_to_chord=StageBladeProperty(rotor=p.get("s_c", 0.8), stator=p.get("s_c", 0.8)),
        max_thickness_to_chord=StageBladeProperty(rotor=0.07, stator=0.07))

def row_loss(a1, a2, s_c, h, Re):
    t1, t2 = np.tan(a1), np.tan(a2)
    am = np.arctan(0.5 * (t1 + t2))
    re_f = float(np.clip((Re / 3e5) ** -0.2, 1.0, 1.5)) if Re < 3e5 else 1.0
    CDp = 0.018 * re_f
    CL = 2 * s_c * np.cos(am) * (t1 - t2)
    for _ in range(5):
        CD = CDp + 0.020 * s_c * CHORD[0] / h + 0.018 * CL * CL
        CL = 2 * s_c * np.cos(am) * (t1 - t2) - CD * np.tan(am)
    eta = 1 - 2 * CD / (CL * np.sin(2 * am))
    return float(eta), dict(CL=float(CL), CD=float(CD), CDp=float(CDp), am_deg=float(np.degrees(am)), re_f=re_f)

CHORD = [0.02]

def evaluate(p, eta_in):
    tm = build(p, eta_in)
    stages, rows = [], []
    for k, s in enumerate(tm.stages):
        r, st = s.rotor, s.stator
        fs_in = r.flow_station
        fs_mid = r.next_flow_station if True else None
        # relative triangle through the rotor (mean stream index 1)
        b1 = abs(float(fs_in.relative_flow_angle[1])); b2 = abs(float(fs_mid.relative_flow_angle[1]))
        W1 = float(fs_in.relative_velocity[1]); W2 = float(fs_mid.relative_velocity[1])
        a2 = abs(float(fs_mid.flow_angle[1]))
        try:
            fs_out = st.next_flow_station; a3 = abs(float(fs_out.flow_angle[1]))
        except AssertionError:
            a3 = abs(float(fs_in.flow_angle[1]))          # last stator: repeating-stage exit angle = stage inlet angle
        V2 = float(fs_mid.absolute_velocity[1])
        V3 = V2 * np.cos(a2) / np.cos(a3)
        s_c_r = float(r.spacing_to_chord); s_c_s = float(st.spacing_to_chord)
        hr, hs = float(r.height), float(st.height)
        CHORD[0] = float(r.chord); er, dr = row_loss(b1, b2, s_c_r, hr, float(r.reynolds_number))
        CHORD[0] = float(st.chord); es, ds = row_loss(a2, a3, s_c_s, hs, float(st.reynolds_number))
        DF_r = 1 - W2 / W1 + abs(W1 * np.sin(b1) - W2 * np.sin(b2)) / (2 * W1) * s_c_r
        DF_s = 1 - V3 / V2 + abs(V2 * np.sin(a2) - V3 * np.sin(a3)) / (2 * V2) * s_c_s
        # tip clearance and shock
        tau = p.get("clearance", 0.25e-3)
        d_tip = 2.0 * (tau / hr)                            # 2 points per 1 %
        T_in = np.asarray(fs_in.static_temperature, float); Wr = np.asarray(fs_in.relative_velocity, float)
        Mrel = Wr / np.sqrt(1.4 * R_AIR * T_in)
        Mt = float(Mrel[-1])
        frac = float(np.clip((Mt - 1) / max(Mt - float(Mrel[1]), 1e-6), 0, 1)) * 0.5 if Mt > 1 else 0.0   # outer annulus share with M_rel > 1
        pr = normal_shock_pt_ratio(Mt)
        dh_stage = float(s.enthalpy_rise)
        T_out = float(np.mean(fs_mid.static_temperature))
        d_shock = T_out * (-R_AIR * np.log(pr)) * frac / dh_stage if pr < 1 else 0.0
        eta_st = 0.5 * (er + es) - d_tip - d_shock
        stages.append(dict(stage=k + 1, eta_rotor=er, eta_stator=es, d_tip=d_tip, d_shock=d_shock, eta_stage=eta_st, PR=float(s.pressure_ratio),
                           DF_rotor=float(DF_r), DF_stator=float(DF_s), deHaller_r=W2 / W1, M_rel_tip=Mt, U_mean=float(s.blade_velocity),
                           rotor=dict(r_hub=float(r.hub_radius), r_tip=float(r.tip_radius), h=hr, chord=float(r.chord), Z=int(r.num_blades),
                                      tc=0.07, disk_h=float(r.disk_height), Re=float(r.reynolds_number), CL=dr["CL"], CD=dr["CD"]),
                           stator=dict(r_hub=float(st.hub_radius), r_tip=float(st.tip_radius), h=hs, chord=float(st.chord), Z=int(st.num_blades),
                                       tc=0.07, Re=float(st.reynolds_number), CL=ds["CL"], CD=ds["CD"])))
    eta_poly = float(np.mean([s_["eta_stage"] for s_ in stages]))
    g = 1.4; PR = p["PR"]
    eta_is = (PR ** ((g - 1) / g) - 1) / (PR ** ((g - 1) / (g * eta_poly)) - 1)
    length = sum(s_["rotor"]["chord"] * 1.25 + s_["stator"]["chord"] * 1.25 for s_ in stages)
    return dict(eta_poly=eta_poly, eta_is=float(eta_is), stages=stages, r_tip_max=float(max(max(s_["rotor"]["r_tip"], s_["stator"]["r_tip"]) for s_ in stages)),
                r_tip_in=float(tm.inlet_tip_radius), r_hub_in=float(tm.inlet_hub_radius), inlet_M=float(tm.inlet_mach_number), length=float(length),
                n_blades=int(sum(s_["rotor"]["Z"] + s_["stator"]["Z"] for s_ in stages)))

if __name__ == "__main__":
    p = json.load(open(sys.argv[1]))
    eta = 0.80
    for it in range(12):
        res = evaluate(p, eta)
        if abs(res["eta_is"] - eta) < 5e-4: break
        eta = 0.5 * eta + 0.5 * res["eta_is"]
    res.update(input=p, iterations=it + 1, eta_input_final=eta,
               D_casing_mm=2e3 * (res["r_tip_max"] + p.get("clearance", 0.25e-3) + 0.0025),
               max_DF_rotor=max(s["DF_rotor"] for s in res["stages"]), max_DF_stator=max(s["DF_stator"] for s in res["stages"]),
               min_deHaller=min(s["deHaller_r"] for s in res["stages"]), M_rel_tip_1=res["stages"][0]["M_rel_tip"],
               h_last_mm=1e3 * res["stages"][-1]["stator"]["h"])
    json.dump(res, open(sys.argv[2], "w"), indent=1)
    print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items() if k not in ("stages", "input")}))
