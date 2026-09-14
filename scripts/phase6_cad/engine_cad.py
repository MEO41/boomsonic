"""Phase 6: conceptual engine CAD from data/phase6/engine_params.json (run in .venv-cad; CadQuery 2.8 / OCCT 7.9).

Coordinates: x = engine axis, from the impeller nose (x = 0) rearward; y, z radial. Units mm in the CAD (the parameter
sheet is SI). Every dimension comes from the parameter sheet; construction rules that the analysis did not fix are
stated per part and are PROVISIONAL (shape only, not performance-validated):
  * vaned diffuser: vane camber with the flow angle from radial varying linearly with radius from the LE to the TE metal
    angle (log-spiral family), constant thickness; axial vanes across the channel width;
  * deswirl: 30 straight axial vanes in the annulus after the 90 deg bend (placeholder count);
  * combustor: outer / inner liners at 0.90 Ro / 1.25 Ri (engine_mass), a conical transition over the last 25 % of the
    liner into the NGV annulus, 8 axial vaporiser tubes from the dome;
  * NGV / rotor blades: TurboFlow radii, chords, blade counts and metal angles; each section is a camber with the angle
    from axial linear along the chord from the LE angle to the gauging (exit) angle, thickness to TurboFlow's maximum,
    lofted hub -> tip on cylinders;
  * turbine disc: the engine_mass constant-stress (Stodola) profile, IN-713LC, 300 MPa;
  * shaft: 32 x 25.6 mm tube with 12 mm journals over +-10 mm at the bearings (cc_rotor); bearings 12 x 28 x 8 mm;
    housings and damper cartridges are placeholders.
The impeller is built separately (impeller_cad.py, pyturbo-aero) and imported from cad/engine/impeller.step if present.
Outputs: cad/engine/<part>.step, cad/engine_assembly.step, data/phase6/engine_cad_mass.csv
"""
import os, sys, json, math, numpy as np, pandas as pd
import cadquery as cq
from OCP.TColgp import TColgp_Array1OfPnt
from OCP.gp import gp_Pnt
from OCP.GeomAPI import GeomAPI_PointsToBSpline
from OCP.GeomAbs import GeomAbs_Shape
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CAD = os.path.join(ROOT, "cad", "engine"); os.makedirs(CAD, exist_ok=True)
E = json.load(open(os.path.join(ROOT, "data", "phase6", "engine_params.json")))
v = lambda sec, k: E[sec][k]["value"]
MM = 1e3
RHO = dict(Ti=4430.0, Al=2760.0, SS=7900.0, IN625=8440.0, IN713=7910.0, steel=7850.0)

from cadlib import revolve, spline_wire, loft, pattern, section2d, periodic_wire, polygon_wire, blade_row, valid

parts = {}
# ---------------- compressor housing: inlet shroud, diffuser walls, vanes, bend + deswirl ----------------
r2, L, b2g, b2e = (v("impeller", k) * MM for k in ("r2", "axial_length", "b2_physical", "b2_effective"))
r1s = v("impeller", "r1_shroud") * MM; tc = v("impeller", "tip_clearance") * MM
r3, r4, bw = v("diffuser", "r3") * MM, v("diffuser", "r4") * MM, v("diffuser", "width") * MM
wall = 3.0; R_case = r4 + v("diffuser", "casing_wall") * MM
phi = np.linspace(0, math.pi / 2, 40)
shroud = [(0.0 + (L - b2g) * math.sin(p), r1s + (r2 - r1s) * (1 - math.cos(p))) for p in phi]   # (x, r)
off = [(x, r + tc) for (x, r) in shroud]                                     # shroud contour + tip clearance
inner = off + [(L - bw, r3), (L - bw, r4)]
outer = [(L - bw - wall, r4), (L - bw - wall, r3)] + [(x - wall * math.sin(p), r + wall * math.cos(p)) for (x, r), p in reversed(list(zip(off, phi)))]
inlet_lip = [(-30.0, r1s + tc), (-30.0, r1s + tc + 12.0)]
front = revolve(inlet_lip[:1] + inner + outer + inlet_lip[1:])
parts["compressor_front_shroud"] = (front, "Al")
parts["compressor_front_wall"] = (revolve([(-30.0, r1s + tc + 12.0), (-27.0, r1s + tc + 12.0), (-27.0, R_case - wall), (-30.0, R_case - wall)]), "Al")
ds = v("diffuser", "deswirl"); dr_in, dr_out, dlen, ndv = ds["r_in"] * MM, ds["r_out"] * MM, ds["axial_length"] * MM, ds["n_vanes"]
# hub-side diffuser wall: ends at the deswirl annulus inner radius so that the flow can turn 90 deg into the axial
# annulus INSIDE r4 (the engine_mass envelope puts the diffuser OD at r4 + 3 mm, so the bend must sit within r4)
back = revolve([(L, r2 + 1.0), (L, dr_in), (L + wall, dr_in), (L + wall, r2 + 1.0)])
parts["diffuser_back_plate"] = (back, "Al")
# vaned diffuser vanes (flow angle from radial linear in r, log-spiral family), extruded across the channel
a_le, a_te, nv, tv = v("diffuser", "vane_le_deg"), v("diffuser", "vane_te_deg"), int(v("diffuser", "n_vanes")), v("diffuser", "vane_thickness") * MM
rr = np.linspace(r3, r4, 60); al = np.radians(a_le + (a_te - a_le) * (rr - r3) / (r4 - r3))
th = np.concatenate([[0], np.cumsum(np.tan(al[:-1]) / rr[:-1] * np.diff(rr))])
cy, cz = rr * np.cos(th), rr * np.sin(th)
ty, tz = np.gradient(cy), np.gradient(cz); nrm = np.hypot(ty, tz); ny_, nz_ = -tz / nrm, ty / nrm
prof = np.vstack([np.c_[cy + 0.5 * tv * ny_, cz + 0.5 * tv * nz_], np.c_[cy - 0.5 * tv * ny_, cz - 0.5 * tv * nz_][::-1]])
vane = cq.Workplane("YZ").polyline([tuple(p) for p in prof]).close().extrude(bw).translate((L - bw, 0, 0)).val()
parts["diffuser_vanes"] = (pattern(vane, nv), "Al")
# 90 deg bend + axial deswirl annulus (dr_in .. r4)
x_ds0 = L + wall + 2.0; x_ds1 = x_ds0 + dlen
parts["deswirl_inner_wall"] = (revolve([(L + wall, dr_in - 1.5), (x_ds1, dr_in - 1.5), (x_ds1, dr_in), (L + wall, dr_in)]), "Al")
dv = cq.Workplane("XY").box(dlen, dr_out - dr_in, 1.5, centered=(False, False, True)).translate((x_ds0, dr_in, 0)).val()
parts["deswirl_vanes"] = (pattern(dv, ndv), "Al")
L_comp = v("stations", "x_compressor_section_end") * MM
parts["compressor_casing"] = (revolve([(-30.0, R_case - wall), (L_comp, R_case - wall), (L_comp, R_case), (-30.0, R_case)]), "Al")
# ---------------- combustor ----------------
Ro, Ri, Ll, Ls = (v("combustor", k) * MM for k in ("Ro", "Ri", "liner_length", "section_length"))
r_ol, r_il, tl = v("combustor", "outer_liner_r") * MM, v("combustor", "inner_liner_r") * MM, v("combustor", "liner_wall") * MM
x_t0 = v("stations", "x_combustor_end") * MM
tg = E["turbine"]; tv_ = lambda k: [x * MM if E["turbine"][k]["unit"] == "m" else x for x in E["turbine"][k]["value"]]
rh_in, rt_in, rh_out, rt_out = tv_("radius_hub_in"), tv_("radius_tip_in"), tv_("radius_hub_out"), tv_("radius_tip_out")
x_l0 = x_t0 - Ll; x_tr = x_t0 - 0.25 * Ll
ol = [(x_l0, r_ol), (x_tr, r_ol), (x_t0, rt_in[0] + 0.5)]; il = [(x_l0, r_il), (x_tr, r_il), (x_t0, rh_in[0] - 0.5)]
parts["liner_outer"] = (revolve(ol + [(p[0], p[1] - tl) for p in reversed(ol)]), "IN625")
parts["liner_inner"] = (revolve(il + [(p[0], p[1] + tl) for p in reversed(il)]), "IN625")
parts["liner_dome"] = (revolve([(x_l0 - tl, r_il), (x_l0, r_il), (x_l0, r_ol), (x_l0 - tl, r_ol)]), "IN625")
vp = v("combustor", "vaporisers"); rv = 0.5 * (r_ol + r_il)
tube = cq.Solid.makeCylinder(vp["d"] * MM / 2, vp["length_frac"] * Ll, cq.Vector(x_l0, rv, 0), cq.Vector(1, 0, 0)).cut(
    cq.Solid.makeCylinder(vp["d"] * MM / 2 - 0.3, vp["length_frac"] * Ll, cq.Vector(x_l0, rv, 0), cq.Vector(1, 0, 0)))
parts["vaporisers"] = (pattern(tube, vp["n"]), "IN625")
# ---------------- turbine ----------------
ch, ach = tv_("chord"), tv_("axial_chord"); tmax, tle = tv_("maximum_thickness"), tv_("leading_edge_diameter")
le, gau = E["turbine"]["leading_edge_angle"]["value"], E["turbine"]["gauging_angle"]["value"]
n_ngv, n_rot = int(v("turbine", "n_ngv")), int(v("turbine", "n_rotor"))
x_ngv = x_t0; x_rot_c = v("stations", "x_rotor_centre") * MM; x_rot = x_rot_c - 0.5 * ach[1]
parts["ngv_vanes"] = (blade_row(x_ngv, 0.5 * (rh_in[0] + rh_out[0]), 0.5 * (rt_in[0] + rt_out[0]), ch[0], le[0], gau[0], tmax[0], n_ngv)[0], "IN713")
parts["ngv_hub_ring"] = (revolve([(x_ngv - 1, rh_in[0] - 2.5), (x_ngv + ach[0] + 1, rh_out[0] - 2.5), (x_ngv + ach[0] + 1, rh_out[0]), (x_ngv - 1, rh_in[0])]), "IN713")
parts["ngv_shroud_ring"] = (revolve([(x_ngv - 1, rt_in[0]), (x_ngv + ach[0] + 1, rt_out[0]), (x_ngv + ach[0] + 1, rt_out[0] + 2.5), (x_ngv - 1, rt_in[0] + 2.5)]), "IN713")
tcl = tv_("tip_clearance")[1]
parts["turbine_blades"] = (blade_row(x_rot, rh_out[1], rt_out[1] - tcl, ch[1], le[1], gau[1], tmax[1], n_rot, embed_tip=0.0)[0], "IN713")
# constant-stress disc (engine_mass law)
om = v("impeller", "rpm") * math.pi / 30; r_rim = rh_out[1] / MM; h_bl = (rt_out[1] - rh_out[1]) / MM
m_bl = RHO["IN713"] * n_rot * 0.7 * (ch[1] / MM) * (tmax[1] / MM) * h_bl
F = m_bl * om ** 2 * (r_rim + 0.5 * h_bl); sig = 300e6
h_rim = max(F / (2 * math.pi * r_rim * sig), 0.004)
rd_ = np.linspace(0, r_rim, 30); hd = h_rim * np.exp(RHO["IN713"] * om ** 2 * (r_rim ** 2 - rd_ ** 2) / (2 * sig)) * MM
disc = [(x_rot_c - 0.5 * hh, r * MM) for r, hh in zip(rd_, hd)] + [(x_rot_c + 0.5 * hh, r * MM) for r, hh in zip(rd_[::-1], hd[::-1])]
disc = [(x, max(r, 1e-3)) for x, r in disc]
parts["turbine_disc"] = (revolve([(disc[0][0], 0.0)] + disc + [(disc[-1][0], 0.0)]), "IN713")
x_tex = x_rot + ach[1] + 3.0
parts["turbine_shroud"] = (revolve([(x_ngv + ach[0] + 1, rt_out[1] + tcl), (x_tex, rt_out[1] + tcl), (x_tex, rt_out[1] + tcl + 2.0), (x_ngv + ach[0] + 1, rt_out[1] + tcl + 2.0)]), "IN713")
# ---------------- hot casing and nozzle ----------------
r_cas = R_case; tcs = 0.6
x_noz = v("stations", "x_nozzle_exit") * MM; r8 = v("stations", "nozzle_r8") * MM
r_ce = rt_out[1] + tcl + 2.6                                                # casing radius over the turbine
hc = [(L_comp, r_cas - tcs), (x_t0, r_cas - tcs), (x_ngv + ach[0] + 1, r_ce), (x_tex, r_ce)]
parts["hot_casing"] = (revolve(hc + [(p[0], p[1] + tcs) for p in reversed(hc)]), "SS")
parts["nozzle_outer_cone"] = (revolve([(x_tex, r_ce), (x_noz, r8), (x_noz, r8 + 0.5), (x_tex, r_ce + 0.5)]), "SS")
parts["tail_cone"] = (revolve([(x_tex, rh_out[1] - 1.0), (x_tex, rh_out[1] - 0.5), (x_noz - 5.0, 0.5), (x_noz - 6.0, 0.5)]), "SS")
# ---------------- shaft, bearings, tunnel ----------------
so, si, jd, jl = (v("rotor", k) * MM for k in ("shaft_od", "shaft_id", "journal_d", "journal_len"))
xf, xr = v("rotor", "x_front_bearing") * MM, v("rotor", "x_rear_bearing") * MM
bp = v("impeller", "back_face"); x_back = L + bp["t_rim"] * MM + bp["boss_A_over_r2"] * r2
sh = [(x_back, 0.5 * jd), (xf + jl / 2, 0.5 * jd), (xf + jl / 2, 0.5 * so), (xr - jl / 2, 0.5 * so), (xr - jl / 2, 0.5 * jd), (x_rot_c, 0.5 * jd)]
shaft = revolve(sh + [(x_rot_c, 0.25 * jd), (xr - jl / 2, 0.25 * jd), (xr - jl / 2, 0.5 * si), (xf + jl / 2, 0.5 * si), (xf + jl / 2, 0.25 * jd), (x_back, 0.25 * jd)])
parts["shaft"] = (shaft, "steel")
bg = v("rotor", "bearing")
for nm, xb in (("bearing_front", xf), ("bearing_rear", xr)):
    parts[nm] = (revolve([(xb - bg["width"] * MM / 2, bg["bore"] * MM / 2), (xb + bg["width"] * MM / 2, bg["bore"] * MM / 2), (xb + bg["width"] * MM / 2, bg["od"] * MM / 2), (xb - bg["width"] * MM / 2, bg["od"] * MM / 2)]), "steel")
    parts[nm.replace("bearing", "housing")] = (revolve([(xb - 8, bg["od"] * MM / 2), (xb + 8, bg["od"] * MM / 2), (xb + 8, bg["od"] * MM / 2 + 6), (xb - 8, bg["od"] * MM / 2 + 6)]), "SS")
rt_ = v("rotor", "tunnel_r") * MM
parts["shaft_tunnel"] = (revolve([(xf + 8, rt_), (xr - 8, rt_), (xr - 8, rt_ + 1.0), (xf + 8, rt_ + 1.0)]), "SS")
imp_file = os.path.join(CAD, "impeller.step")
if os.path.exists(imp_file):
    parts["impeller"] = (cq.importers.importStep(imp_file).val(), "Ti")

# ---------------- export, mass table, checks ----------------
rows = []; asm = cq.Assembly(name="boomsonic_engine")
colors = dict(Ti=(0.62, 0.64, 0.68), Al=(0.69, 0.77, 0.87), SS=(0.72, 0.53, 0.04), IN625=(1.0, 0.55, 0.0), IN713=(0.70, 0.13, 0.13), steel=(0.35, 0.35, 0.35))
for nm, (shp, mat) in parts.items():
    cq.exporters.export(cq.Workplane().add(shp), os.path.join(CAD, f"{nm}.step"))
    vol = shp.Volume(); rows.append(dict(part=nm, material=mat, volume_cm3=vol / 1e3, mass_kg=vol * 1e-9 * RHO[mat], valid=valid(shp)))
    asm.add(shp, name=nm, color=cq.Color(*colors[mat]))
asm.save(os.path.join(ROOT, "cad", "engine_assembly.step"))
df = pd.DataFrame(rows); df.to_csv(os.path.join(ROOT, "data", "phase6", "engine_cad_mass.csv"), index=False)
bb = cq.Compound.makeCompound([s for s, _ in parts.values()]).BoundingBox()
pd.set_option("display.width", 200); print(df.round(4).to_string(index=False))
print(f"total CAD mass {df.mass_kg.sum():.3f} kg; bounding box x {bb.xmin:.1f} .. {bb.xmax:.1f} mm (length {bb.xlen:.1f}), diameter {max(bb.ylen, bb.zlen):.1f} mm")
