"""Phase 6A (EXPLORATORY): conceptual CAD of the 6-stage axial core, from data/phase6a/axial_params.json
(run in .venv-cad; CadQuery 2.8 / OCCT 7.9).

PACKAGING AND MASS ONLY. Not a build release, not an architecture decision, no manufacturing intent.
Coordinates: x = engine axis, x = 0 at the compressor front face; units mm in the CAD (the sheet is SI).

Fidelity, stated per part:
  * casings, discs, drum, shaft, tunnel, liners, cones: real solids at the frozen radii and stations;
  * BLADES ARE ENVELOPES, NOT AERO SURFACES (out of scope): each row is Z untwisted prisms with a NACA
    thickness form at the row's real chord, maximum thickness and height, giving the same 0.685 c t h section
    area the mass model uses (engine_mass uses 0.7 c t h). Stagger is zero: the row's axial extent is therefore
    its chord, which is what the packaging check needs;
  * discs follow engine_mass's constant-stress (Stodola) profile h(r) = h_rim exp(rho w^2 (r_rim^2 - r^2)/(2 sigma));
  * bearing housings, the tunnel and the NGV/turbine blade shapes are provisional.
Every boolean is checked by volume (a silent OCCT boolean failure returns a plausible-looking shape).
Outputs: cad/axial/<part>.step, cad/axial_core_assembly.step, data/phase6a/engine_cad_mass.csv
"""
import os, sys, json, math, numpy as np, pandas as pd
import cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase6_cad")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase6_cad"))
from cadlib import revolve, loft, pattern, section2d, polygon_wire, valid
CAD = os.path.join(AXROOT, "cad", "parts"); os.makedirs(CAD, exist_ok=True)
OUT = os.path.join(AXROOT, "data", "phase6a")
E = json.load(open(os.path.join(OUT, "axial_params.json")))
v = lambda sec, k: E[sec][k]["value"]
MM = 1e3
RHO = E["materials"]["rho"]
SIG_TI, SIG_IN713 = 450e6, 300e6                     # engine_mass.SIG
parts, notes = {}, {}

def add(name, shape, material, note):
    parts[name] = (shape, material); notes[name] = note

def tube(x0, x1, r_in, r_out):
    return revolve([(x0, r_in), (x1, r_in), (x1, r_out), (x0, r_out)])

def stodola(r_rim_m, omega, rho, sigma, F_rim, x_c):
    """engine_mass's constant-stress disc, revolved as a solid of revolution about x. Returns (shape, h_rim_mm)."""
    h_rim = max(F_rim / (2 * math.pi * r_rim_m * sigma), 0.004)
    r = np.linspace(0, r_rim_m, 120)
    h = h_rim * np.exp(rho * omega ** 2 * (r_rim_m ** 2 - r ** 2) / (2 * sigma))
    up = [((x_c + 0.5 * hh) * MM, rr * MM) for rr, hh in zip(r, h)]
    dn = [((x_c - 0.5 * hh) * MM, rr * MM) for rr, hh in zip(r, h)][::-1]
    return revolve(up + dn), h_rim * MM

def blades(x_le, r_hub, r_tip, chord, t_max, Z, embed=0.0):
    """Z untwisted prisms, NACA thickness form, zero camber and zero stagger. ENVELOPE ONLY (see header)."""
    wires = []
    for r in (r_hub - embed, r_tip):
        p2 = section2d(chord, 0.0, 0.0, t_max, n=28)
        p2[:, 0] -= p2[:, 0].min(); p2[:, 1] -= p2[:, 1].mean()
        wires.append(polygon_wire(np.c_[x_le + p2[:, 0], p2[:, 1], np.full(len(p2), r)]))
    one = loft(wires, ruled=True)
    return pattern(one, Z), one

rpm = v("cycle", "rpm"); omega = rpm * math.pi / 30
r_case_eng = v("envelope", "OD") / 2 * MM

# ------------------------------------------------------------------ compressor: stepped casing, discs, blades
st = E["compressor"]["stages"]
tipclr = v("compressor", "tip_clearance") * MM
wall = v("compressor", "casing_wall") * MM
prof_in, prof_out = [], []
x_c0, x_c1 = 0.0, v("compressor", "section_length") * MM
for i, s in enumerate(st):                                   # inner line follows the real per-stage tip radii
    for b in (s["rotor"], s["stator"]):
        x0 = b["x_le"] * MM; x1 = x0 + b["chord"] * MM; ri = b["r_tip"] * MM + tipclr
        prof_in += [(x0, ri), (x1, ri)]
prof_in = [(x_c0, prof_in[0][1])] + prof_in + [(x_c1, prof_in[-1][1])]
casing = revolve(prof_in + [(x, r + wall) for x, r in prof_in][::-1])
add("compressor_casing", casing, "Al", "2.5 mm wall stepped to the real per-stage tip line + 0.25 mm clearance")

m_blades_chk = 0.0
for s in st:
    ro = s["rotor"]
    F = ro["m_blades_kg"] * omega ** 2 * (ro["r_hub"] + 0.5 * ro["h"])
    d, hrim = stodola(ro["disc_r_rim"], omega, RHO["Ti"], SIG_TI, F, ro["disc_x"])
    add(f"disc_stage{s['stage']}", d, "Ti", f"constant-stress disc, rim {hrim:.2f} mm, at x {ro['disc_x'] * MM:.1f} mm")
    bl, one = blades(ro["x_le"] * MM, ro["r_hub"] * MM, ro["r_tip"] * MM, ro["chord"] * MM, ro["t_max"] * MM, ro["Z"])
    add(f"rotor_blades_stage{s['stage']}", bl, "Ti", f"{ro['Z']} envelope prisms, chord {ro['chord'] * MM:.2f} mm")
    sa = s["stator"]
    bl2, _ = blades(sa["x_le"] * MM, sa["r_hub"] * MM, sa["r_tip"] * MM, sa["chord"] * MM, sa["t_max"] * MM, sa["Z"])
    add(f"stator_vanes_stage{s['stage']}", bl2, "Al", f"{sa['Z']} envelope prisms, chord {sa['chord'] * MM:.2f} mm")
    band = tube(sa["x_le"] * MM, (sa["x_le"] + sa["chord"]) * MM, sa["r_hub"] * MM - 2.0, sa["r_hub"] * MM)
    add(f"stator_band_stage{s['stage']}", band, "Al", "2 mm inner shroud band (engine_mass)")

# drum between the disc rims
add("rotor_drum", tube(st[0]["rotor"]["disc_x"] * MM, st[-1]["rotor"]["disc_x"] * MM,
                       v("rotor", "drum_r_mean") * MM - 0.5 * v("rotor", "drum_t") * MM,
                       v("rotor", "drum_r_mean") * MM + 0.5 * v("rotor", "drum_t") * MM), "Ti",
    f"2 mm Ti shell at r {v('rotor', 'drum_r_mean') * MM:.2f} mm (ax_closure / ax_rotor)")

# ------------------------------------------------------------------ shaft, journals, bearings, tunnel
od, idd = v("rotor", "shaft_od") * MM, v("rotor", "shaft_id") * MM
jo, jl = v("rotor", "journal_od") * MM, v("rotor", "journal_len") * MM
xf, xr = v("rotor", "x_bearing_front") * MM, v("rotor", "x_bearing_rear") * MM
x_sh0, x_sh1 = 0.0, v("turbine", "disc_x") * MM
seg = []                                                  # journal OD ahead of disc 1 and around the rear bearing
xd1 = st[0]["rotor"]["disc_x"] * MM
seg.append((x_sh0, xd1, jo))                              # front stub at journal OD (rotor_model rule)
seg.append((xd1, xr - 0.5 * jl, od))
seg.append((xr - 0.5 * jl, xr + 0.5 * jl, jo))
seg.append((xr + 0.5 * jl, x_sh1, od))
shaft = None                                              # seg carries DIAMETERS; tube() takes radii
for a, b, o in seg:
    if b <= a: continue
    piece = tube(a, b, 0.5 * min(idd, 0.6 * o), 0.5 * o)
    shaft = piece if shaft is None else shaft.fuse(piece)
v_expect = sum(math.pi / 4 * (o ** 2 - min(idd, 0.6 * o) ** 2) * (b - a) for a, b, o in seg if b > a)
assert abs(shaft.Volume() - v_expect) / v_expect < 1e-6, f"shaft fuse lost volume: {shaft.Volume():.1f} vs {v_expect:.1f}"
add("shaft", shaft, "steel", f"{od:.0f} / {idd:.0f} mm 4340 tube, {jo:.0f} mm journals over {jl:.0f} mm at both bearings")

b_od, b_w = v("rotor", "bearing_od") * MM, v("rotor", "bearing_width") * MM
for nm, xb in (("bearing_front", xf), ("bearing_rear", xr)):
    add(nm, tube(xb - 0.5 * b_w, xb + 0.5 * b_w, 0.5 * jo, 0.5 * b_od), "steel", "12 x 28 x 8 hybrid ball bearing envelope (provisional)")
tr = v("rotor", "tunnel_r") * MM
add("shaft_tunnel", tube(st[-1]["rotor"]["disc_x"] * MM, xr - 0.5 * b_w, tr - 1.0, tr), "SS",
    "1 mm tunnel from the last compressor disc to the rear bearing (provisional)")
for nm, xb in (("housing_front", xf), ("housing_rear", xr)):
    add(nm, tube(xb - 0.5 * b_w - 3.0, xb + 0.5 * b_w + 3.0, 0.5 * b_od, 0.5 * b_od + 3.0), "Al",
        "bearing housing / damper cartridge envelope (provisional, 3 mm wall)")

# ------------------------------------------------------------------ combustor
xb0 = v("combustor", "x_start") * MM; Lc = v("combustor", "section_length") * MM
Ll = v("combustor", "L_liner") * MM; tl = v("combustor", "t_liner") * MM
ro_l, ri_l = v("combustor", "r_liner_outer") * MM, v("combustor", "r_liner_inner") * MM
xl0 = xb0 + 0.5 * (Lc - Ll)
add("liner_outer", tube(xl0, xl0 + Ll, ro_l - tl, ro_l), "IN625", "outer liner at 0.90 Ro (engine_mass)")
add("liner_inner", tube(xl0, xl0 + Ll, ri_l, ri_l + tl), "IN625", "inner liner at 1.25 Ri (engine_mass)")
add("liner_dome", revolve([(xl0, ri_l), (xl0 + tl, ri_l), (xl0 + tl, ro_l), (xl0, ro_l)]), "IN625", "dome, 0.5 mm")
vap = None
r_vap = 0.5 * (ro_l + ri_l)
for i in range(int(v("combustor", "n_vaporisers"))):
    a = 2 * math.pi * i / v("combustor", "n_vaporisers")
    t = (cq.Workplane("YZ").workplane(offset=xl0 + tl).center(r_vap * math.cos(a), r_vap * math.sin(a))
         .circle(2.0).circle(1.7).extrude(0.6 * Ll).val())
    vap = t if vap is None else vap.fuse(t)
add("vaporisers", vap, "IN625", "8 x 4 mm OD x 0.3 mm tubes, 0.6 L_liner (engine_mass)")
add("hot_casing", tube(xb0, v("nozzle", "x_exit") * MM - 0.9 * v("turbine", "r_tip") * MM, r_case_eng - 0.6, r_case_eng),
    "SS", "0.6 mm AISI 321 over the hot section: this IS the 142.45 mm engine OD (engine_mass)")

# ------------------------------------------------------------------ turbine
rt_h, rt_t = v("turbine", "r_hub") * MM, v("turbine", "r_tip") * MM
xn, xtr = v("turbine", "x_ngv_le") * MM, v("turbine", "x_rotor_le") * MM
cn, cr_ = v("turbine", "c_ngv") * MM, v("turbine", "c_rotor") * MM
ngv, _ = blades(xn, rt_h, rt_t, cn, v("turbine", "t_max_ngv") * MM, int(round(v("turbine", "Z_ngv"))))
add("ngv_vanes", ngv, "IN713", f"{int(round(v('turbine', 'Z_ngv')))} envelope prisms (aero surfaces out of scope)")
tb, _ = blades(xtr, rt_h, rt_t, cr_, v("turbine", "t_max_rotor") * MM, int(round(v("turbine", "Z_rotor"))))
add("turbine_blades", tb, "IN713", f"{int(round(v('turbine', 'Z_rotor')))} envelope prisms")
add("ngv_hub_ring", tube(xn, xn + cn, rt_h - 2.5, rt_h), "IN713", "2.5 mm NGV hub ring (engine_mass)")
add("ngv_shroud_ring", tube(xn, xn + cn, rt_t, rt_t + 2.5), "IN713", "2.5 mm NGV shroud ring")
F_t = v("turbine", "m_blades_kg") * omega ** 2 * (v("turbine", "disc_r_rim") + 0.5 * (rt_t - rt_h) / MM)
td, thr = stodola(v("turbine", "disc_r_rim"), omega, RHO["IN713"], SIG_IN713, F_t, v("turbine", "disc_x"))
add("turbine_disc", td, "IN713", f"constant-stress IN-713LC disc, rim {thr:.2f} mm")
add("turbine_shroud", tube(xn, xtr + cr_, rt_t + 0.3, rt_t + 0.3 + v("turbine", "shroud_t") * MM), "IN713",
    "2 mm shroud ring over 1.4 x the summed chords (engine_mass)")

# ------------------------------------------------------------------ nozzle cones (fixed part; the flaps are in ax_vg_cad)
r8 = v("nozzle", "r8_design") * MM; xe = v("nozzle", "x_exit") * MM
x_cone0 = xe - 0.9 * rt_t
add("nozzle_outer_cone", revolve([(x_cone0, rt_t), (xe, r8), (xe, r8 + 0.5), (x_cone0, rt_t + 0.5)]), "SS",
    "0.5 mm convergent outer cone, turbine tip -> r8 (engine_mass); the VARIABLE flaps replace its aft part")
add("tail_cone", revolve([(x_cone0, 0.6 * rt_t), (xe, 0.0), (x_cone0, 0.6 * rt_t - 0.5)]), "SS",
    "0.5 mm inner tail cone, 0.6 r_tip over 0.9 r_tip (engine_mass)")

# ------------------------------------------------------------------ export + mass table
rows, asm = [], []
for nm, (shp, mat) in parts.items():
    ok = valid(shp)
    cq.exporters.export(cq.Workplane().add(shp), os.path.join(CAD, f"{nm}.step"))
    vol = shp.Volume()
    rows.append(dict(part=nm, material=mat, volume_cm3=vol / 1e3, mass_kg=vol * 1e-9 * RHO[mat], valid=ok, note=notes[nm]))
    asm.append(shp)
df = pd.DataFrame(rows).sort_values("mass_kg", ascending=False)
df.to_csv(os.path.join(OUT, "engine_cad_mass.csv"), index=False)
comp = cq.Compound.makeCompound(asm)
cq.exporters.export(cq.Workplane().add(comp), os.path.join(AXROOT, "cad", "axial_core_assembly.step"))
bb = comp.BoundingBox()
print(df[["part", "material", "mass_kg", "valid"]].to_string(index=False))
print(f"\ncore CAD mass {df.mass_kg.sum():.3f} kg; invalid solids: {(~df.valid).sum()}")
print(f"bounding box: x {bb.xmin:.1f} .. {bb.xmax:.1f} mm (length {bb.xlen:.1f}), diameter {max(bb.ylen, bb.zlen):.1f} mm "
      f"(engine OD {2 * r_case_eng:.1f} mm, raw length {v('envelope', 'L_raw') * MM:.1f} mm)")
