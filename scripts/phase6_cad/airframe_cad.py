"""Phase 6: conceptual airframe CAD and engine integration (run in .venv-cad; CadQuery 2.8).

From data/phase6/airframe_params.json (Phase 2 configuration C1 at the Phase 4 engine; capture and nozzle areas updated):
  * fuselage: body of revolution from airframe_model.body_radius (cosine-area forebody, cubic boattail) WITH the D2.6
    area-rule waist (0.5 x the wing cross-section area removed, as the drag model does), 1.5 mm skin shell;
  * nose pitot inlet: lip at the capture radius, subsonic duct (1 mm wall) straight to the engine inlet lip;
  * wing, horizontal tail: exposed panels from the local body radius to the tip, parabolic (biconvex) sections
    t = 4 tc c xi (1 - xi) (the Phase 2 area-rule model's section), trapezoidal planform, LE sweep as Phase 2;
    vertical tail: sections from the body top upward;
  * engine: cad/engine_assembly.step parts, impeller eye (engine x = 0) at the Phase 2 engine face x = 1.315 m;
    the calibrated envelope (OD 186.6 x 426 mm) as a reserved volume;
  * jetpipe: from the turbine exit at constant radius to where the boattail forces it inward, then following the body
    (3 mm gap) down to the convergent nozzle throat A8 at the tail; the engine's own nozzle cone is not installed.
Checks: clearances (engine envelope to the waisted skin, jetpipe to the boattail), internal volume available for the
2.98 kg (3.7 L) of fuel around the intake duct, jetpipe length / Mach / friction loss estimate (not in the cycle).
Not modelled: landing gear, chute canister, systems, structure detail.
Outputs: cad/airframe/*.step, cad/aircraft_assembly.step, data/phase6/airframe_cad_checks.json
"""
import os, sys, json, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import cadquery as cq
import cadlib as cl
A = json.load(open(os.path.join(ROOT, "data", "phase6", "airframe_params.json")))
E = json.load(open(os.path.join(ROOT, "data", "phase6", "engine_params.json")))
MM = 1e3; OUTD = os.path.join(ROOT, "cad", "airframe"); os.makedirs(OUTD, exist_ok=True)
x = np.array(A["body_x"]) * MM; r = np.array(A["body_r"]) * MM; rw = np.array(A["body_r_waisted"]) * MM
SKIN = 1.5
parts = {}; chk = {}
# ---- fuselage skin (waisted OML, 1.5 mm shell) ----
prof_out = list(zip(x, rw)); prof_in = [(xx, max(rr - SKIN, 0.5)) for xx, rr in zip(x, rw)]
parts["fuselage_skin"] = cl.revolve(prof_out + prof_in[::-1])
# ---- inlet lip + duct ----
r_cap = math.sqrt(A["A_capture"] / math.pi) * MM
x_face = A["engine_face_x"] * MM; x_lip_eng = x_face - 30.0
r1s = E["impeller"]["r1_shroud"]["value"] * MM + E["impeller"]["tip_clearance"]["value"] * MM
duct = [(0.0, r_cap), (x_lip_eng, r1s)]
parts["intake_duct"] = cl.revolve(duct + [(x_lip_eng, r1s + 1.0), (0.0, r_cap + 1.0)])
chk["intake"] = dict(capture_r_mm=r_cap, capture_area_cm2=A["A_capture"] * 1e4, duct_length_mm=x_lip_eng, face_r_mm=r1s,
                     area_ratio=(r1s / r_cap) ** 2, equivalent_cone_half_angle_deg=math.degrees(math.atan((r1s - r_cap) / x_lip_eng)))
# ---- lifting surfaces ----
def panel(sf, key):
    """exposed panel(s): sections at the body side (or top) and at the tip; biconvex; returns list of solids."""
    x0, hb, cr, lam, sw, tc = sf["x_root_le"] * MM, sf["half_span"] * MM, sf["c_root"] * MM, sf["taper"], sf["sweep_le_deg"], sf["tc"]
    ch = lambda s: cr * (1 - (1 - lam) * s / hb); xle = lambda s: x0 + s * math.tan(math.radians(sw))
    def sec(s):
        c = ch(s); xi = 0.5 * (1 - np.cos(np.linspace(0, math.pi, 41))); zt = 2 * tc * c * xi * (1 - xi)
        up = np.c_[xle(s) + xi * c, zt]; lo = np.c_[xle(s) + xi[::-1] * c, -zt[::-1]]
        return np.vstack([up, lo[1:-1]]), c
    if sf["vertical"]:
        s0 = float(np.interp(x0 + 0.3 * cr, x, rw)) - 2.0                    # root inside the body top
        ws = []
        for s in (s0, hb):
            p, _ = sec(s); ws.append(cl.polygon_wire(np.c_[p[:, 0], p[:, 1], np.full(len(p), s)]))
        return [cl.loft(ws, ruled=True)]
    s0 = float(np.interp(x0 + 0.5 * cr, x, rw)) - 2.0                         # root inside the body side
    ws = []
    for s in (s0, hb):
        p, _ = sec(s); ws.append(cl.polygon_wire(np.c_[p[:, 0], np.full(len(p), s), p[:, 1]]))
    right = cl.loft(ws, ruled=True)
    left = right.mirror("XZ")
    return [right, left]
for key, sf in A["surfaces"].items():
    for i, s in enumerate(panel(sf, key)):
        parts[f"{key}_{'right' if i == 0 else 'left'}" if not sf["vertical"] else key] = s
# ---- engine (parts from the engine assembly) + reserved calibrated envelope ----
asm = cq.importers.importStep(os.path.join(ROOT, "cad", "engine_assembly.step"))
eng = asm.val().translate((x_face, 0, 0))
Re = E["envelope"]["OD_model"]["value"] * MM / 2; Le = E["envelope"]["length_calibrated"]["value"] * MM
envelope = cq.Solid.makeCylinder(Re, Le, cq.Vector(x_face, 0, 0), cq.Vector(1, 0, 0))
m = (x >= x_face) & (x <= x_face + Le)
chk["engine_clearance"] = dict(min_waisted_skin_inner_r_mm=float((rw[m] - SKIN).min()), at_x_mm=float(x[m][np.argmin(rw[m])]), envelope_r_mm=Re,
                               radial_gap_mm=float((rw[m] - SKIN).min() - Re), envelope_x_mm=(x_face, x_face + Le))
# ---- jetpipe to the tail nozzle ----
x_tex = x_face + (E["stations"]["x_rotor_centre"]["value"] * MM + 0.5 * E["turbine"]["axial_chord"]["value"][1] * MM + 3.0)
r_jp = E["turbine"]["radius_tip_out"]["value"][1] * MM + 3.0; r8 = E["stations"]["nozzle_r8"]["value"] * MM
xs_j = np.linspace(x_tex, x[-1], 120); r_in_body = np.interp(xs_j, x, r) - SKIN - 3.0
r_j = np.minimum(r_jp, r_in_body); r_j[-1] = r8
parts["jetpipe"] = cl.revolve(list(zip(xs_j, r_j)) + list(zip(xs_j[::-1], (r_j + 1.0)[::-1])))
x_conv = float(xs_j[np.argmax(r_in_body < r_jp)]) if np.any(r_in_body < r_jp) else x[-1]
# friction / Mach estimate in the constant-radius part (turbine-exit gas, dash)
cyc = json.load(open(os.path.join(ROOT, "data", "phase3r", "cct_ce75000_opr4_t1150_b15_cap.json")))["levels"]["fielded"]["eval"]["cycle"]
Wg = cyc["W_kgps"] + cyc["Wf_kgps"]; Tt5 = cyc["Tt5_K"]; Pt5 = cyc["Pt5_kPa"] * 1e3; gam, Rg = 1.33, 287.0
Aj = math.pi * (r_jp / MM) ** 2; Mj = 0.2
for _ in range(60):
    T = Tt5 / (1 + 0.5 * (gam - 1) * Mj ** 2); P = Pt5 * (T / Tt5) ** (gam / (gam - 1))
    Mj = Wg / (P / (Rg * T) * Aj * math.sqrt(gam * Rg * T))
mu = 1.458e-6 * T ** 1.5 / (T + 110.4); V = Mj * math.sqrt(gam * Rg * T); Re_ = P / (Rg * T) * V * 2 * r_jp / MM / mu
f = (-1.8 * math.log10(6.9 / Re_)) ** -2; Lj = (x_conv - x_tex) / MM
qP = 0.5 * gam * Mj ** 2 / (1 + 0.5 * (gam - 1) * Mj ** 2) ** (gam / (gam - 1))
chk["jetpipe"] = dict(x_start_mm=x_tex, x_convergence_start_mm=x_conv, length_constant_part_m=Lj, total_length_m=(x[-1] - x_tex) / MM, radius_mm=r_jp,
                      Mach=Mj, Re=Re_, f_Haaland=f, dPt_over_Pt_friction=f * Lj / (2 * r_jp / MM) * qP, residual_swirl_deg=None,
                      note="not in the cycle (nozzle Cv 0.98 only); the turbine exit swirl (TurboFlow exit flow angle) is not recovered either")
tt = json.load(open(os.path.join(ROOT, "data", "phase3r", "ce75000_opr4_t1150_b15_cap_ttf70_out.json")))
chk["jetpipe"]["residual_swirl_deg"] = tt["overall"].get("exit_flow_angle")
chk["jetpipe"]["min_gap_to_boattail_mm"] = float(np.min(np.interp(xs_j, x, r) - SKIN - (r_j + 1.0)))
# ---- fuel volume available around the duct (forebody annulus between the duct and the skin, ahead of the engine) ----
xx = np.linspace(300.0, x_lip_eng - 20.0, 400)
r_duct = np.interp(xx, [0.0, x_lip_eng], [r_cap + 1.0, r1s + 1.0]) + 5.0            # duct + 5 mm tank wall / clearance
r_sk = np.interp(xx, x, rw) - SKIN - 5.0
Vann = float(np.trapezoid(np.pi * np.maximum(r_sk ** 2 - r_duct ** 2, 0), xx)) * 1e-6    # litres
fuel = 2.98 / 0.80
chk["fuel_volume"] = dict(annulus_x_mm=(300.0, float(xx[-1])), annulus_volume_L=Vann, fuel_required_L=fuel, fraction_used=fuel / Vann,
                          note="gross annulus; systems (avionics 0.3 kg, batteries 0.35 kg, instrumentation) also need space here")
# ---- export ----
colors = dict(fuselage_skin=(0.85, 0.85, 0.88), intake_duct=(0.6, 0.8, 0.6), jetpipe=(0.72, 0.53, 0.04))
air = cq.Assembly(name="boomsonic_aircraft")
for nm, s in parts.items():
    cq.exporters.export(cq.Workplane().add(s), os.path.join(OUTD, f"{nm}.step"))
    air.add(s, name=nm, color=cq.Color(*colors.get(nm, (0.5, 0.6, 0.75))))
air.add(eng, name="engine", color=cq.Color(0.7, 0.2, 0.2))
air.add(envelope, name="engine_envelope_reserved_calibrated", color=cq.Color(1.0, 0.9, 0.2, 0.25))
air.save(os.path.join(ROOT, "cad", "aircraft_assembly.step"))
chk["parts"] = {nm: dict(valid=cl.valid(s), volume_cm3=s.Volume() / 1e3) for nm, s in parts.items()}
json.dump(chk, open(os.path.join(ROOT, "data", "phase6", "airframe_cad_checks.json"), "w"), indent=1, default=float)
print(json.dumps(chk, indent=1, default=lambda o: round(float(o), 4)))
