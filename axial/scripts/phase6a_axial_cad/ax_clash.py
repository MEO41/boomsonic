"""Phase 6A (EXPLORATORY): packaging / interference check of the axial engine as drawn (run in .venv-cad).

This is the question Phase 6A exists to answer: do the shaft, bearings, bleed ducting and VIGV actuation ring
physically fit inside the 142.45 mm engine OD, and does anything interfere?

Checks:
  1. ENVELOPE. Every part's maximum radius against the 142.45 mm engine OD, and its axial extent against the
     raw engine length. Confirmed by a boolean containment test (part minus the OD cylinder must be empty).
  2. INTERFERENCE. Pairwise solid intersection over every pair whose bounding boxes overlap, reported by the
     volume of the common solid. Booleans are volume-checked (an OCCT boolean that silently fails returns a
     plausible shape, tools_survey section 9).
  3. CLEARANCES. Minimum distance (BRepExtrema) for the specific pairs the freeze leaves open: shaft/tunnel,
     tunnel/inner liner, front bearing/inlet hub, nozzle flaps at both stops against the tail cone and casing.
NOTHING IS MOVED OR RESIZED TO MAKE IT FIT. A clash is reported, not corrected.
Output: data/phase6a/clash_report.json
"""
import os, sys, json, math, itertools, numpy as np, pandas as pd
import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
CAD = os.path.join(AXROOT, "cad", "parts"); OUT = os.path.join(AXROOT, "data", "phase6a")
E = json.load(open(os.path.join(OUT, "axial_params.json")))
v = lambda sec, k: E[sec][k]["value"]
MM = 1e3
R_ENG = v("envelope", "OD") / 2 * MM
L_RAW = v("envelope", "L_raw") * MM
V_TOL = 1.0                                                   # mm^3: below this an "intersection" is numerical noise

shapes = {}
for f in sorted(os.listdir(CAD)):
    if f.endswith(".step"):
        shapes[f[:-5]] = cq.importers.importStep(os.path.join(CAD, f)).val()
print(f"loaded {len(shapes)} parts from cad/axial/")

def max_radius(s):
    return max(math.hypot(vx.Y, vx.Z) for vx in s.Vertices())

def dist(a, b):
    d = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped); d.Perform()
    return float(d.Value())

# ---------------------------------------------------------------- 1. envelope
env = []
for nm, s in shapes.items():
    bb = s.BoundingBox(); rmax = max_radius(s)
    env.append(dict(part=nm, r_max_mm=rmax, over_OD_mm=rmax - R_ENG, x_min=bb.xmin, x_max=bb.xmax,
                    fwd_of_face_mm=max(0.0, -bb.xmin), aft_of_L_raw_mm=max(0.0, bb.xmax - L_RAW)))
env = pd.DataFrame(env).sort_values("r_max_mm", ascending=False)
out_of_env = env[env.over_OD_mm > 1e-6]

# boolean confirmation for the offenders (and the three largest that pass)
cyl = cq.Workplane("XY").circle(R_ENG).extrude(L_RAW + 200.0).val().moved(cq.Location(cq.Vector(0, 0, -50.0)))
cyl = cyl.rotate((0, 0, 0), (0, 1, 0), 90.0)                  # axis along +x
conf = {}
for nm in list(out_of_env.part) + list(env.head(3).part):
    s = shapes[nm]
    try:
        outside = s.cut(cyl)
        conf[nm] = float(outside.Volume()) if outside.Solids() else 0.0
    except Exception as ex:
        conf[nm] = f"boolean failed: {ex}"

# ---------------------------------------------------------------- 2. pairwise interference
names = list(shapes)
bbs = {n: shapes[n].BoundingBox() for n in names}
rad = {n: max_radius(shapes[n]) for n in names}
rmin = {}
for n in names:                                               # inner radius: min vertex radius
    rmin[n] = min(math.hypot(vx.Y, vx.Z) for vx in shapes[n].Vertices())

def skip(a, b):
    # the two nozzle-flap positions are the same hardware drawn twice; a flap never coexists with its other stop
    if "flaps_closed" in a and "flaps_open" in b: return True
    if "flaps_open" in a and "flaps_closed" in b: return True
    return False

pairs, checked = [], 0
for a, b in itertools.combinations(names, 2):
    if skip(a, b): continue
    A_, B_ = bbs[a], bbs[b]
    if A_.xmax < B_.xmin - 1e-9 or B_.xmax < A_.xmin - 1e-9: continue        # no axial overlap
    if rad[a] < rmin[b] - 1e-9 or rad[b] < rmin[a] - 1e-9: continue          # no radial overlap
    checked += 1
    try:
        c = shapes[a].intersect(shapes[b])
        vol = float(c.Volume()) if c.Solids() else 0.0
    except Exception:
        vol = float("nan")
    if not (vol == vol) or vol > V_TOL:
        pairs.append(dict(part_a=a, part_b=b, common_volume_mm3=vol))
print(f"pairwise: {checked} candidate pairs tested after bounding-box filtering, {len(pairs)} interferences")

# ---------------------------------------------------------------- 3. targeted clearances
targets = [
    ("shaft", "shaft_tunnel", "shaft OD to tunnel ID"),
    ("shaft_tunnel", "liner_inner", "tunnel OD to the combustor inner liner"),
    ("bearing_front", "compressor_casing", "front bearing to the compressor casing"),
    ("housing_front", "disc_stage1", "front bearing housing to the stage-1 disc"),
    ("vg_vigv_unison_ring", "compressor_casing", "VIGV unison ring to the casing"),
    ("vg_vigv_actuator", "compressor_casing", "VIGV actuator to the casing"),
    ("vg_bleed_duct", "vg_bleed_actuator", "bleed duct to its actuator"),
    ("vg_nozzle_flaps_closed", "tail_cone", "nozzle flaps (closed) to the tail cone"),
    ("vg_nozzle_flaps_open", "tail_cone", "nozzle flaps (open) to the tail cone"),
    ("vg_nozzle_flaps_open", "hot_casing", "nozzle flaps (open) to the hot casing"),
    ("vg_nozzle_sync_ring", "hot_casing", "nozzle sync ring to the hot casing"),
]
clear = []
for a, b, what in targets:
    if a in shapes and b in shapes:
        d = dist(shapes[a], shapes[b])
        clear.append(dict(pair=f"{a} / {b}", what=what, min_distance_mm=d, touching_or_clashing=bool(d < 1e-6)))

# front bearing vs the stage-1 inlet hub radius (a radius comparison, not a solid pair)
r_hub_in = E["compressor"]["stages"][0]["rotor"]["r_hub"] * MM
r_brg_out = 0.5 * v("rotor", "bearing_od") * MM
r_hsg_out = r_brg_out + 3.0
clear.append(dict(pair="bearing_front / stage-1 inlet hub line", what="bearing OD inside the inlet hub radius",
                  min_distance_mm=r_hub_in - r_brg_out, touching_or_clashing=bool(r_brg_out > r_hub_in)))
clear.append(dict(pair="housing_front / stage-1 inlet hub line", what="bearing housing OD inside the inlet hub radius",
                  min_distance_mm=r_hub_in - r_hsg_out, touching_or_clashing=bool(r_hsg_out > r_hub_in)))

# ---------------------------------------------------------------- 3b. classify: joint by design vs real clash
JOINTS = [                                                    # (pattern a, pattern b, why this contact is by design)
    ("disc_stage", "shaft", "disc bore on the shaft"),
    ("disc_stage", "rotor_drum", "drum lands on the disc rims"),
    ("shaft", "turbine_disc", "turbine disc on the shaft"),
    ("rotor_blades_stage", "rotor_drum", "blade roots into the drum"),
    ("liner_dome", "liner_", "dome welded to the liners"),
    ("vg_bleed_ports", "compressor_casing", "ports pass through the casing"),
    ("vg_bleed_ports", "vg_bleed_manifold", "ports open into the manifold"),
    ("vg_vigv_spindles", "compressor_casing", "spindles pass through casing bosses"),
    ("vg_vigv_spindles", "vg_vigv_cranks", "crank clamped on the spindle"),
    ("vg_vigv_spindles", "vg_vigv_unison_ring", "crank pin into the ring"),
    ("vg_vigv_pushrod", "vg_vigv_unison_ring", "pushrod pinned to the ring"),
    ("vg_vigv_pushrod", "vg_vigv_actuator", "pushrod on the servo arm"),
    ("vg_nozzle_pushrods", "vg_nozzle_sync_ring", "pushrods pinned to the sync ring"),
    ("vg_nozzle_flaps", "vg_nozzle_hinge_ring", "flaps hinged on the ring"),
    ("nozzle_outer_cone", "vg_nozzle_flaps", "the flaps replace the cone's aft part; the cone was not trimmed"),
    ("disc_stage6", "shaft_tunnel", "tunnel starts at the last disc"),
    ("shaft_tunnel", "shaft", "shaft runs inside the tunnel"),
]
def joint_reason(a, b):
    for pa, pb, why in JOINTS:
        if (pa in a and pb in b) or (pa in b and pb in a): return why
    return None
for p_ in pairs:
    p_["by_design"] = joint_reason(p_["part_a"], p_["part_b"])
real = [p_ for p_ in pairs if p_["by_design"] is None]

# ---------------------------------------------------------------- 3c. drum outer radius against the hub line
r_drum_out = (v("rotor", "drum_r_mean") + 0.5 * v("rotor", "drum_t")) * MM
drum_rows = []
for s_ in E["compressor"]["stages"]:
    for kind in ("rotor", "stator"):
        b_ = s_[kind]
        drum_rows.append(dict(row=f"stage {s_['stage']} {kind}", r_hub_mm=b_["r_hub"] * MM,
                              drum_above_hub_mm=r_drum_out - b_["r_hub"] * MM,
                              obstructs_flow_path=bool(r_drum_out > b_["r_hub"] * MM)))

res = dict(
    note=("Phase 6A packaging check of the axial engine AS DRAWN. Exploratory only. No part was moved or resized "
          "to fit; clashes are reported, not corrected."),
    engine_OD_mm=2 * R_ENG, engine_L_raw_mm=L_RAW, engine_L_calibrated_mm=v("envelope", "L_calibrated") * MM,
    radial_gap_over_compressor_mm=v("envelope", "radial_gap_over_compressor") * MM,
    parts_outside_OD=out_of_env.to_dict("records"),
    boolean_confirmation_volume_outside_mm3=conf,
    axial_overhangs=dict(
        forward_of_front_face=[r for r in env.to_dict("records") if r["fwd_of_face_mm"] > 1e-6],
        aft_of_raw_length=[r for r in env.to_dict("records") if r["aft_of_L_raw_mm"] > 1e-6]),
    interferences=pairs, interferences_real=real, clearances=clear, envelope_table=env.to_dict("records"),
    drum_outer_radius_mm=r_drum_out, drum_vs_hub_line=drum_rows)
json.dump(res, open(os.path.join(OUT, "clash_report.json"), "w"), indent=1, default=float)

print(f"\n=== ENVELOPE: engine OD {2 * R_ENG:.2f} mm, raw length {L_RAW:.1f} mm ===")
if len(out_of_env):
    print(f"{'part':<28}{'r_max':>9}{'over OD':>10}  boolean volume outside [mm3]")
    for r in out_of_env.to_dict("records"):
        print(f"{r['part']:<28}{r['r_max_mm']:>9.2f}{r['over_OD_mm']:>10.2f}  {conf.get(r['part'])}")
else:
    print("every part is inside the engine OD")
print(f"\nlargest parts inside the OD:")
for r in env[env.over_OD_mm <= 1e-6].head(4).to_dict("records"):
    print(f"  {r['part']:<28} r_max {r['r_max_mm']:7.2f} mm  ({R_ENG - r['r_max_mm']:.2f} mm to the OD)")

print(f"\n=== AXIAL OVERHANG ===")
for r in res["axial_overhangs"]["forward_of_front_face"]:
    print(f"  {r['part']:<28} {r['fwd_of_face_mm']:6.2f} mm ahead of the compressor front face")
for r in res["axial_overhangs"]["aft_of_L_raw_mm"] if False else res["axial_overhangs"]["aft_of_raw_length"]:
    print(f"  {r['part']:<28} {r['aft_of_L_raw_mm']:6.2f} mm aft of the raw engine length")

print(f"\n=== INTERFERENCES, real (common volume > {V_TOL} mm3, assembly joints excluded) ===")
if real:
    for p in sorted(real, key=lambda q: -q["common_volume_mm3"]):
        print(f"  {p['part_a']:<26} x {p['part_b']:<26} {p['common_volume_mm3']:10.1f} mm3")
else:
    print("  none")
print(f"\n  ({len(pairs) - len(real)} further contacts are assembly joints by design; listed in the JSON)")

print(f"\n=== ROTOR DRUM (constant radius) AGAINST THE RISING HUB LINE ===")
print(f"  drum outer radius {r_drum_out:.2f} mm")
for d_ in drum_rows:
    if d_["obstructs_flow_path"]:
        print(f"  {d_['row']:<20} hub {d_['r_hub_mm']:6.2f} mm -> drum stands {d_['drum_above_hub_mm']:5.2f} mm INTO the flow path")

print(f"\n=== CLEARANCES ===")
for c in clear:
    flag = "  <-- CLASH" if c["touching_or_clashing"] else ""
    print(f"  {c['what']:<50}{c['min_distance_mm']:8.2f} mm{flag}")
