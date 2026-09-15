"""Phase 6A (EXPLORATORY): the three variable-geometry mechanisms as real mechanical assemblies
(run in .venv-cad). Resolves open risk 4.4 of docs/design_freeze_axial.md as far as geometry and mass can.

This is the part of Phase 6A that the freeze could not do on paper: the VIGV, the stage-3 bleed valve and the
variable nozzle are built as actuator + linkage + housing, with the actuator sized to a REAL off-the-shelf part
(data/phase6a/actuators.json, transcribed from manufacturer datasheets) instead of the freeze's placeholder
3 x 75 g hobby servos.

RULE FOLLOWED HERE: every part is placed where its own design requires it. Nothing is moved, shrunk or
re-sized to fit inside the 142.45 mm engine OD. Where a part does not fit, it is drawn clashing and
ax_clash.py reports it.

Mechanism rules (ALL PROVISIONAL - no analysis tool designed this hardware):
  * VIGV: one row of Z_igv vanes ahead of rotor 1, spaced by the compressor's own 0.25-chord gap rule, on radial
    spindles through casing bosses, crank arms at 6 mm radius onto a unison ring at r_tip + 12 mm (ax_closure's
    dimensions), driven by a 5 mm servo arm through a pushrod. Drawn at both stops (22.4 and 28.7 deg swirl);
  * bleed: manifold ring at the stage-3 stator tip + 4 mm with 8 ports of the computed choked area, a rotating
    band valve over them, and ONE collector duct of the full port area running radially out to the engine OD
    (the discharge path beyond the engine OD is out of scope - user decision);
  * nozzle: 12 flaps hinged on a ring at the outer-cone start, drawn at A8 x1.0 and x2.0, a sync ring at
    r8_max + 10 mm (ax_closure's dimension) and 12 pushrods, with the actuator on a heat-shield standoff.
Outputs: cad/axial/vg_<part>.step, cad/axial_vg_assembly.step, data/phase6a/vg_cad_mass.csv
"""
import os, sys, json, math, numpy as np, pandas as pd
import cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase6_cad")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase6_cad"))
from cadlib import revolve, pattern, valid
CAD = os.path.join(AXROOT, "cad", "parts"); os.makedirs(CAD, exist_ok=True)
OUT = os.path.join(AXROOT, "data", "phase6a")
E = json.load(open(os.path.join(OUT, "axial_params.json")))
A = json.load(open(os.path.join(OUT, "actuators.json")))
v = lambda sec, k: E[sec][k]["value"]
vg = lambda sys_, k: E["vg_loads"][sys_][k]["value"]
MM = 1e3
RHO = E["materials"]["rho"]
parts, notes = {}, {}
def add(name, shape, material, note, mass_override=None):
    parts[name] = (shape, material, mass_override); notes[name] = note

def tube(x0, x1, r_in, r_out):
    return revolve([(x0, r_in), (x1, r_in), (x1, r_out), (x0, r_out)])

def box_at(L, W, H, x, r, ang_deg, tag=""):
    """box of L (axial) x W (tangential) x H (radial), inner face at radius r, centred at angle ang."""
    b = cq.Workplane("XY").box(L, W, H, centered=(True, True, False)).val()
    b = b.located(cq.Location(cq.Vector(0, 0, 0)))
    b = b.moved(cq.Location(cq.Vector(x, 0, r)))                      # radial = +z at angle 0
    return b.rotate((0, 0, 0), (1, 0, 0), ang_deg)

def rod(x0, r0, x1, r1, d, ang_deg):
    """round rod between two (x, r) points in the meridional plane at angle ang."""
    p0 = np.array([x0, 0.0, r0]); p1 = np.array([x1, 0.0, r1]); dr = p1 - p0; L = float(np.linalg.norm(dr))
    w = cq.Workplane("XY").circle(0.5 * d).extrude(L).val()
    zax = np.array([0.0, 0.0, 1.0]); u = dr / L
    ax = np.cross(zax, u); s = float(np.linalg.norm(ax))
    if s > 1e-9:
        angle = math.degrees(math.atan2(s, float(np.dot(zax, u))))
        w = w.rotate((0, 0, 0), tuple(ax / s), angle)
    return w.moved(cq.Location(cq.Vector(*p0))).rotate((0, 0, 0), (1, 0, 0), ang_deg)

st = E["compressor"]["stages"]
r_eng = v("envelope", "OD") / 2 * MM
tipclr = v("compressor", "tip_clearance") * MM; wall = v("compressor", "casing_wall") * MM

# =============================================================== 1. VIGV
s1 = st[0]; ro1 = s1["rotor"]
Z_igv = int(vg("vigv", "Z")); c_igv = vg("vigv", "chord") * MM; h_igv = vg("vigv", "span") * MM
r_h_igv, r_t_igv = ro1["r_hub"] * MM, ro1["r_tip"] * MM
# the compressor's own stack rule (0.25-chord gap) put ahead of rotor 1 -> the row starts BEFORE the front face
x_igv_le = ro1["x_le"] * MM - 0.25 * c_igv - c_igv
t_igv = 0.07 * c_igv
one = cq.Workplane("XY").box(c_igv, t_igv, h_igv, centered=(True, True, False)).val() \
    .moved(cq.Location(cq.Vector(x_igv_le + 0.5 * c_igv, 0, r_h_igv)))
add("vg_vigv_vanes", pattern(one, Z_igv), "Ti", f"{Z_igv} vanes, chord {c_igv:.2f} mm, span {h_igv:.2f} mm, t/c 0.07")
r_case_igv = r_t_igv + tipclr + wall
sp = None
for i in range(Z_igv):                                                # 3 mm radial spindles through the casing
    s_ = rod(x_igv_le + 0.3 * c_igv, r_t_igv, x_igv_le + 0.3 * c_igv, r_t_igv + 20.0, 3.0, 360.0 * i / Z_igv)
    sp = s_ if sp is None else sp.fuse(s_)
add("vg_vigv_spindles", sp, "steel", f"{Z_igv} x 3 mm spindles, 20 mm long, at 0.30 chord (ax_closure)")
R_CRANK = 6.0
cr = None
for i in range(Z_igv):
    c_ = box_at(4.0, 1.5, R_CRANK + 2.0, x_igv_le + 0.3 * c_igv, r_t_igv + 18.0, 360.0 * i / Z_igv)
    cr = c_ if cr is None else cr.fuse(c_)
add("vg_vigv_cranks", cr, "steel", f"{Z_igv} crank arms, {R_CRANK:.0f} mm effective radius (12 x 4 x 1.5 mm)")
r_ring = r_t_igv + 12.0
add("vg_vigv_unison_ring", tube(x_igv_le + 0.3 * c_igv - 3.0, x_igv_le + 0.3 * c_igv + 3.0, r_ring, r_ring + 2.0),
    "steel", f"unison ring 6 x 2 mm at r {r_ring:.2f} mm (ax_closure dimensions)")

act_v = A["actuators"][A["selection"]["vigv"]["part"]]
Lb, Wb, Hb = act_v["installed_envelope_mm"]
x_act_v = x_igv_le + 0.3 * c_igv
add("vg_vigv_actuator", box_at(Lb, Wb, Hb, x_act_v, r_case_igv, 0.0), "Al",
    f"{act_v['model']} installed envelope {Lb} x {Wb} x {Hb} mm, {act_v['mass_kg'] * 1e3:.0f} g, inner face on the casing OD",
    mass_override=act_v["mass_kg"])
add("vg_vigv_actuator_bracket", box_at(Lb, Wb + 8.0, 3.0, x_act_v, r_case_igv - 3.0, 0.0), "Al",
    "3 mm mounting bracket under the actuator (provisional)")
add("vg_vigv_pushrod", rod(x_act_v, r_case_igv + 5.0, x_act_v, r_ring + 2.0, 3.0, 0.0), "steel",
    "3 mm pushrod, 5 mm servo arm to a ring lug (provisional)")

# =============================================================== 2. stage-3 bleed
s3 = st[2]; r_c = s3["stator"]["r_tip"] * MM + 4.0
x_bleed = (s3["stator"]["x_le"] + s3["stator"]["chord"]) * MM + 2.0
A_port = vg("bleed", "port_area") * 1e6                               # mm^2
n_port = int(vg("bleed", "n_ports")); d_port = 2 * math.sqrt(A_port / n_port / math.pi)
add("vg_bleed_manifold", tube(x_bleed - 12.5, x_bleed + 12.5, r_c, r_c + 1.0), "Al",
    f"manifold ring 25 x 1 mm at r {r_c:.2f} mm (ax_closure dimensions)")
add("vg_bleed_band_valve", tube(x_bleed - 10.0, x_bleed + 10.0, r_c + 1.0, r_c + 1.5), "SS",
    "rotating band valve 20 x 0.5 mm over the ports (ax_closure dimensions)")
r_case_3 = s3["stator"]["r_tip"] * MM + tipclr + wall
pr = None
for i in range(n_port):
    p_ = rod(x_bleed, r_case_3 - 3.0, x_bleed, r_c, d_port, 360.0 * i / n_port)
    pr = p_ if pr is None else pr.fuse(p_)
add("vg_bleed_ports", pr, "Al", f"{n_port} ports of {d_port:.2f} mm dia = {A_port:.1f} mm2 total (choked area)")
d_duct = 2 * math.sqrt(A_port / math.pi)
add("vg_bleed_duct", rod(x_bleed, r_c + 1.5, x_bleed, r_eng, d_duct, 0.0), "Al",
    f"collector duct {d_duct:.1f} mm dia (full port area) radially out to the engine OD; path beyond is out of scope")
act_b = A["actuators"][A["selection"]["bleed"]["part"]]
Lb2, Wb2, Hb2 = act_b["installed_envelope_mm"]
add("vg_bleed_actuator", box_at(Lb2, Wb2, Hb2, x_bleed, r_case_3, 180.0), "Al",
    f"{act_b['model']} installed envelope, {act_b['mass_kg'] * 1e3:.0f} g, inner face on the casing OD, opposite the duct",
    mass_override=act_b["mass_kg"])
add("vg_bleed_actuator_bracket", box_at(Lb2, Wb2 + 8.0, 3.0, x_bleed, r_case_3 - 3.0, 180.0), "Al",
    "3 mm bracket (provisional)")
add("vg_bleed_pushrod", rod(x_bleed, r_case_3 + 5.0, x_bleed, r_c + 1.5, 3.0, 180.0), "steel",
    "3 mm pushrod, 2:1 crank pair to the band (provisional)")

# =============================================================== 3. variable nozzle
rt_t = v("turbine", "r_tip") * MM
xe = v("nozzle", "x_exit") * MM
x_hinge = xe - 0.9 * rt_t
r8, r8m = v("nozzle", "r8_design") * MM, v("nozzle", "r8_max") * MM
L_fl = vg("nozzle", "flap_length") * MM; w_fl = vg("nozzle", "flap_width") * MM
n_fl = int(vg("nozzle", "n_flaps")); t_fl = 0.6
add("vg_nozzle_hinge_ring", tube(x_hinge - 2.0, x_hinge + 2.0, rt_t, rt_t + 3.0), "SS",
    "hinge ring at the outer-cone start (provisional)")
for tag, r_exit in (("closed", r8), ("open", r8m)):
    th = math.degrees(math.asin((rt_t - r_exit) / L_fl))              # + = converging
    fl = cq.Workplane("XY").box(L_fl, w_fl, t_fl, centered=(False, True, False)).val()
    fl = fl.rotate((0, 0, 0), (0, 1, 0), th).moved(cq.Location(cq.Vector(x_hinge, 0, rt_t)))
    add(f"vg_nozzle_flaps_{tag}", pattern(fl, n_fl), "SS",
        f"{n_fl} flaps {L_fl:.1f} x {w_fl:.1f} x {t_fl} mm at A8 x{1.0 if tag == 'closed' else v('nozzle', 'a8_max'):.1f} "
        f"({th:+.2f} deg to the axis); the two positions are the SAME hardware drawn twice")
r_sync = r8m + 10.0
x_sync = x_hinge + 0.8 * L_fl
add("vg_nozzle_sync_ring", tube(x_sync - 4.0, x_sync + 4.0, r_sync, r_sync + 2.0), "SS",
    f"sync ring 8 x 2 mm at r {r_sync:.2f} mm (ax_closure dimension r8_max + 10 mm)")
pr2 = None
for i in range(n_fl):
    p_ = rod(x_sync, r_sync, x_hinge + 0.8 * L_fl, rt_t + 3.0, 3.0, 360.0 * i / n_fl)
    pr2 = p_ if pr2 is None else pr2.fuse(p_)
add("vg_nozzle_pushrods", pr2, "steel", f"{n_fl} x 3 mm pushrods, sync ring to flap at 0.8 of its length")
act_n = A["actuators"][A["selection"]["nozzle"]["part"]]
Ln, Wn, Hn = act_n["installed_envelope_mm"]
STANDOFF = 20.0
add("vg_nozzle_heat_shield", tube(x_sync - 0.5 * Ln, x_sync + 0.5 * Ln, r_eng - 1.0, r_eng), "SS",
    f"{STANDOFF:.0f} mm heat-shield standoff under the nozzle actuator (provisional; no thermal analysis)")
add("vg_nozzle_actuator", box_at(Ln, Wn, Hn, x_sync, r_sync + 2.0 + STANDOFF, 0.0), "Al",
    f"{act_n['model']} installed envelope {Ln} x {Wn} x {Hn} mm, {act_n['mass_kg'] * 1e3:.0f} g, on the standoff",
    mass_override=act_n["mass_kg"])
add("vg_nozzle_reduction", box_at(40.0, 30.0, 25.0, x_sync - 0.5 * Ln - 20.0, r_sync + 2.0, 0.0), "Al",
    "22.5:1 screwjack / gear stage the actuator needs to hold 27.0 N m (NOT in the freeze's 0.279 kg estimate)")

# =============================================================== export + mass
rows, asm = [], []
for nm, (shp, mat, mo) in parts.items():
    cq.exporters.export(cq.Workplane().add(shp), os.path.join(CAD, f"{nm}.step"))
    vol = shp.Volume()
    m = mo if mo is not None else vol * 1e-9 * RHO[mat]
    sysname = "VIGV" if "vigv" in nm else ("bleed" if "bleed" in nm else "nozzle")
    rows.append(dict(system=sysname, part=nm, material=("datasheet" if mo is not None else mat),
                     volume_cm3=vol / 1e3, mass_kg=m, from_datasheet=mo is not None, valid=valid(shp), note=notes[nm]))
    if not nm.endswith("_open"): asm.append(shp)
df = pd.DataFrame(rows)
df.to_csv(os.path.join(OUT, "vg_cad_mass.csv"), index=False)
comp = cq.Compound.makeCompound(asm)
cq.exporters.export(cq.Workplane().add(comp), os.path.join(AXROOT, "cad", "axial_vg_assembly.step"))
print(df[["system", "part", "mass_kg", "from_datasheet", "valid"]].to_string(index=False))
print(f"\nVG CAD mass by system (the 'open' flap copy excluded):")
sel = df[~df.part.str.endswith("_open")]
for s_, g in sel.groupby("system"):
    print(f"  {s_:<7} {g.mass_kg.sum() * 1e3:7.1f} g")
print(f"  TOTAL   {sel.mass_kg.sum() * 1e3:7.1f} g   (freeze allowance {v('vg_mass_allowance', 'total') * 1e3:.1f} g)")
print(f"invalid solids: {(~df.valid).sum()}")
print(f"\nVIGV row starts at x = {x_igv_le:+.2f} mm (engine front face is x = 0): "
      f"{'AHEAD of the front face by %.2f mm' % -x_igv_le if x_igv_le < 0 else 'inside the front allowance'}")
print(f"nozzle flaps reach x = {x_hinge + L_fl * math.cos(math.radians(0)):.1f} mm vs the raw engine length {xe:.1f} mm")
