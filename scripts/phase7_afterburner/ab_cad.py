"""Phase 7 CAD: the frozen engine with the afterburner and its variable nozzle
(run in .venv-cad; CadQuery 2.8 / OCCT 7.9).

Built ON the Phase 6 engine, not instead of it.  Every Phase 6 part is imported from
`cad/engine/*.step` unchanged, except the two the afterburner replaces:

    nozzle_outer_cone   the dry convergent nozzle   -> replaced by the diffuser + plug nozzle
    tail_cone           the dry tail cone           -> replaced by the diffuser tail cone

so the compressor, combustor, turbine, shaft and impeller geometry in this assembly is bit-for-bit
the Phase 6 geometry and nothing upstream of the turbine exit has been re-drawn.

Every dimension of the new hardware comes from the Phase 7 data files, not from this script:
  data/phase7/ab_hardware.json     diffuser length, burn length, duct diameter, gutter count
  data/phase7/ab_nozzle_trade.json cowl and plug geometry, plug stroke, the dry and wet stations
  data/phase7/ab_design_point.json the AB duct area the duct diameter comes from
  data/phase6/engine_params.json   the turbine exit the afterburner has to be fed from

Configuration drawn: `M0.20_theta7` (afterburner duct Mach 0.20, 7 deg equivalent-cone diffuser) --
the one the envelope, the nozzle trade and the closure were all computed on.  The plug is drawn in
its WET (afterburner-lit) position; the dry position is exported as a separate part file so the
stroke is visible in CAD.

PROVISIONAL, shape only, not performance-validated (same convention as Phase 6):
  * the tail cone taper and the diffuser wall are straight cones at the equivalent-cone angle the
    length calculation used; a real afterburner diffuser would be contoured;
  * the screech liner is drawn with circumferential corrugations of an arbitrary 25 mm pitch and
    2 mm amplitude -- a drawing convention standing in for a liner that has NOT been acoustically
    designed (R7.3), and no cooling holes are drawn;
  * the V-gutter section is a 25 mm bluff body at the analysed blockage, not a designed gutter;
  * the nozzle actuator linkage is SCHEMATIC: it shows the forward-mounted arrangement D7.4
    requires (the tailpipe is at 698 C against a +50 C actuator rating) but the bellcrank,
    pushrod buckling and thermal growth are not designed (R7.2).

Outputs: cad/afterburner/<part>.step, cad/engine_with_afterburner_assembly.step,
         data/phase7/ab_cad_mass.csv
Usage:   .venv-cad\\Scripts\\python scripts\\phase7_afterburner\\ab_cad.py
         (this venv's processes exit non-zero at teardown; check the outputs, not the exit code)
"""
import os, sys, json, math, numpy as np, pandas as pd
import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase6_cad"))
from cadlib import revolve, pattern, valid

CAD6 = os.path.join(ROOT, "cad", "engine")
CAD7 = os.path.join(ROOT, "cad", "afterburner")
os.makedirs(CAD7, exist_ok=True)
D7 = os.path.join(ROOT, "data", "phase7")
MM = 1e3
RHO = dict(Ti=4430.0, Al=2760.0, SS=7900.0, IN625=8440.0, IN713=7910.0, steel=7850.0, HastX=8220.0)
COLORS = dict(Ti=(0.62, 0.64, 0.68), Al=(0.69, 0.77, 0.87), SS=(0.72, 0.53, 0.04),
              IN625=(1.0, 0.55, 0.0), IN713=(0.70, 0.13, 0.13), steel=(0.35, 0.35, 0.35),
              HastX=(0.85, 0.35, 0.10))

# what the afterburner replaces, and what is not an engine part
REPLACED = {"nozzle_outer_cone", "tail_cone"}
NOT_A_PART = {"impeller_sector"}

CONFIG = "M0.20_theta7"

# ----------------------------------------------------------------- inputs
E = json.load(open(os.path.join(ROOT, "data", "phase6", "engine_params.json")))
HW = json.load(open(os.path.join(D7, "ab_hardware.json")))
NZ = json.load(open(os.path.join(D7, "ab_nozzle_trade.json")))
v = lambda sec, k: E[sec][k]["value"]

cfg = HW["configurations"][CONFIG]
te = HW["turbine_exit"]

# turbine exit station, exactly as engine_cad.py computes it
ach = [x * MM for x in v("turbine", "axial_chord")]
x_rot_c = v("stations", "x_rotor_centre") * MM
x_tex = (x_rot_c - 0.5 * ach[1]) + ach[1] + 3.0
r_hub_te = te["r_hub_mm"]
r_tip_te = te["r_tip_mm"]
r_case_te = r_tip_te + v("turbine", "tip_clearance")[1] * MM + 2.6      # hot-casing radius over the turbine

# afterburner geometry
R_DUCT = NZ["duty"]["R_duct_mm"]                    # 82.1 mm, the AB duct flow radius
L_DIFF = cfg["L_diffuser_mm"]
L_BURN = cfg["L_burn_mm"]
L_COWL = 110.0                                      # the cowl length the plug model used
R_COWL_EXIT = 62.0
R_PLUG_MAX = 45.0
L_PLUG_FWD, L_PLUG_AFT = 70.0, 100.0
S_DRY = [r for r in NZ["plug"]["loads"] if r["state"] == "dry"][0]["station_mm"]
S_WET = [r for r in NZ["plug"]["loads"] if r["state"] == "wet"][0]["station_mm"]
N_GUTTER_RINGS = int(HW["assumptions"]["n_gutter_rings"])
T_LINER = HW["assumptions"]["liner_t_mm"]
T_CASING = HW["assumptions"]["casing_t_mm"]
COOL_ANNULUS = 6.0                                  # liner-to-casing gap (ab_hardware mass model)

x_d0 = x_tex                                        # diffuser start
x_d1 = x_d0 + L_DIFF                                # diffuser end / burn section start
x_b1 = x_d1 + L_BURN                                # burn section end / cowl start
x_c1 = x_b1 + L_COWL                                # cowl exit

parts = {}


def cone_shell(x0, r0, x1, r1, t):
    """thin conical shell from (x0, r0) to (x1, r1), wall t outward."""
    return revolve([(x0, r0), (x1, r1), (x1, r1 + t), (x0, r0 + t)])


# ----------------------------------------------------------------- 1. diffuser
# Outer wall: from the hot-casing radius over the turbine out to the afterburner duct.  The
# EQUIVALENT cone angle of the whole annulus-to-circle transition is the 7 deg the length came
# from; the outer wall on its own rises more slowly because the hub is falling away at the same
# time (that is what an annular diffuser does).
parts["ab_diffuser_casing"] = (cone_shell(x_d0, r_case_te, x_d1, R_DUCT, T_CASING), "IN625")
half_angle_outer = math.degrees(math.atan2(R_DUCT - r_case_te, L_DIFF))

# Tail cone: closes the turbine hub out over the diffuser length, ending 20 mm short of the
# diffuser exit with a 3 mm blunt tip.
x_tc1 = x_d1 - 20.0
tc = [(x_d0, r_hub_te), (x_tc1, 3.0), (x_tc1, 3.0 - 0.0)]
parts["ab_tail_cone"] = (revolve([(x_d0, r_hub_te - 0.8), (x_d0, r_hub_te),
                                  (x_tc1, 3.0), (x_tc1, 2.2)]), "IN625")
half_angle_hub = math.degrees(math.atan2(r_hub_te - 3.0, x_tc1 - x_d0))

# Diffuser struts: 3 radial struts carrying the tail cone (and, on one of them, the nozzle linkage).
# Radial parts are built along +y, not +z: the meridional section figure is cut on the plane z = 0,
# so anything standing on the +z axis is invisible in it (the Phase 6 deswirl vanes use +y too).
strut = cq.Workplane("XY").box(40.0, R_DUCT - 10.0, 1.5, centered=(True, False, True)) \
    .translate((x_d0 + 0.55 * L_DIFF, 8.0, 0)).val()
parts["ab_diffuser_struts"] = (pattern(strut, 3), "IN625")

# ----------------------------------------------------------------- 2. burn section
parts["ab_casing"] = (cone_shell(x_d1, R_DUCT, x_b1, R_DUCT, T_CASING), "IN625")

# Screech liner: corrugated shell inside a cooling annulus.  The corrugation is a DRAWING
# CONVENTION (25 mm pitch, 2 mm amplitude); no acoustic design exists (R7.3).
r_liner = R_DUCT - COOL_ANNULUS
xs = np.linspace(x_d1, x_b1, 240)
r_corr = r_liner + 2.0 * np.sin(2 * math.pi * (xs - x_d1) / 25.0)
prof = [(x, r) for x, r in zip(xs, r_corr)] + [(x, r + T_LINER) for x, r in zip(xs[::-1], r_corr[::-1])]
parts["ab_liner"] = (revolve(prof), "HastX")

# V-gutter flameholder rings, 25 mm bluff bodies at the analysed blockage
def vgutter(rc, w=25.0, L=30.0, t=1.2):
    h = 0.5 * w
    k = t * math.hypot(L, h) / L                       # wall thickness measured normal to the leg
    tn = t * math.hypot(L, h) / h                      # inner apex offset along x
    return revolve([(0.0, rc), (L, rc + h), (L, rc + h - k), (tn, rc),
                    (L, rc - h + k), (L, rc - h)])


x_fh = x_d1 + 12.0
guts = []
for i in range(N_GUTTER_RINGS):
    rc = r_liner * (i + 0.5) / N_GUTTER_RINGS
    guts.append(vgutter(rc).translate((x_fh, 0, 0)))
parts["ab_flameholder_gutters"] = (cq.Compound.makeCompound(guts), "HastX")

gstrut = cq.Workplane("XY").box(30.0, r_liner - 2.0, 1.5, centered=(True, False, True)) \
    .translate((x_fh + 15.0, 1.0, 0)).val()
parts["ab_gutter_struts"] = (pattern(gstrut, 3 * N_GUTTER_RINGS), "HastX")

# Spray bars: 12 radial tubes upstream of the gutters, and the manifold ring outside the casing
x_sb = x_d1 + 2.0
bar_o = cq.Solid.makeCylinder(2.0, r_liner, cq.Vector(x_sb, 0, 0), cq.Vector(0, 1, 0))
bar_i = cq.Solid.makeCylinder(1.5, r_liner, cq.Vector(x_sb, 0, 0), cq.Vector(0, 1, 0))
parts["ab_spray_bars"] = (pattern(bar_o.cut(bar_i), 12), "IN625")
# manifold: an 8 mm OD / 6 mm ID tube ring, as the mass model sizes it (a solid ring section
# drew 2.3 x the model's mass, which was a drawing error and not a finding)
r_man = R_DUCT + T_CASING + 4.0
parts["ab_fuel_manifold"] = (revolve([(x_sb - 4.0, r_man - 3.0), (x_sb - 4.0, r_man - 4.0),
                                      (x_sb + 4.0, r_man - 4.0), (x_sb + 4.0, r_man + 4.0),
                                      (x_sb - 4.0, r_man + 4.0), (x_sb - 4.0, r_man + 3.0),
                                      (x_sb + 3.0, r_man + 3.0), (x_sb + 3.0, r_man - 3.0)]), "IN625")
parts["ab_igniter"] = (cq.Solid.makeCylinder(7.0, 26.0, cq.Vector(x_fh + 6.0, r_liner - 4.0, 0), cq.Vector(0, 1, 0)), "SS")

# ----------------------------------------------------------------- 3. variable plug nozzle
parts["nozzle_cowl"] = (cone_shell(x_b1, R_DUCT, x_c1, R_COWL_EXIT, T_CASING), "IN625")


def plug_solid(station_mm):
    """Conical plug whose shoulder sits at `station_mm` measured from the cowl start, hollow."""
    xs_ = x_b1 + station_mm
    outer = [(xs_ - L_PLUG_FWD, 0.0), (xs_, R_PLUG_MAX), (xs_ + L_PLUG_AFT, 0.0)]
    inner = [(xs_ + L_PLUG_AFT - 4.0, 0.0), (xs_, R_PLUG_MAX - 0.8 * math.hypot(L_PLUG_AFT, R_PLUG_MAX) / L_PLUG_AFT),
             (xs_ - L_PLUG_FWD + 4.0, 0.0)]
    return revolve(outer + inner)


parts["nozzle_plug"] = (plug_solid(S_WET), "IN625")

# plug support: 3 struts from the cowl to the plug shoulder
pstrut = cq.Workplane("XY").box(24.0, R_DUCT - R_PLUG_MAX, 1.5, centered=(True, False, True)) \
    .translate((x_b1 + S_WET, R_PLUG_MAX, 0)).val()
parts["nozzle_plug_struts"] = (pattern(pstrut, 3), "IN625")

# ----------------------------------------------------------------- 4. actuation, SCHEMATIC (R7.2)
# D7.4: the only compliant sourced actuator (Actuonix P16-50-256, 300 N rated against the 123 N
# demand) is rated to +50 C and the tailpipe skin is at 698 C, so it MUST be mounted forward, on
# the compressor casing at 36 C, and reach the plug through a pushrod.  Drawn to show the
# arrangement and the run length; the bellcrank, buckling and thermal growth are NOT designed.
x_act = v("stations", "x_compressor_section_end") * MM - 40.0
R_case_comp = v("diffuser", "r4") * MM + v("diffuser", "casing_wall") * MM
parts["nozzle_actuator"] = (cq.Workplane("XY").box(97.0, 22.0, 22.0, centered=(False, True, True))
                            .translate((x_act, R_case_comp + 14.0, 0)).val(), "Al")
parts["nozzle_pushrod"] = (cq.Solid.makeCylinder(3.0, (x_d0 + 0.55 * L_DIFF) - (x_act + 97.0),
                                                 cq.Vector(x_act + 97.0, R_case_comp + 14.0, 0),
                                                 cq.Vector(1, 0, 0)), "steel")
parts["nozzle_link_radial"] = (cq.Solid.makeCylinder(2.5, R_case_comp + 14.0 - 6.0,
                                                     cq.Vector(x_d0 + 0.55 * L_DIFF, 6.0, 0),
                                                     cq.Vector(0, 1, 0)), "steel")
parts["nozzle_actuator_rod"] = (cq.Solid.makeCylinder(5.0, (x_b1 + S_WET - L_PLUG_FWD) - (x_d0 + 0.55 * L_DIFF),
                                                      cq.Vector(x_d0 + 0.55 * L_DIFF, 0, 0),
                                                      cq.Vector(1, 0, 0)), "steel")

# ----------------------------------------------------------------- export
new_parts = dict(parts)
rows = []
asm = cq.Assembly(name="boomsonic_engine_with_afterburner")

kept, dropped = [], []
for f in sorted(os.listdir(CAD6)):
    if not f.endswith(".step"):
        continue
    nm = f[:-5]
    if nm in NOT_A_PART:
        continue
    if nm in REPLACED:
        dropped.append(nm)
        continue
    kept.append(nm)

m6 = pd.read_csv(os.path.join(ROOT, "data", "phase6", "engine_cad_mass.csv")).set_index("part")
for nm in kept:
    shp = cq.importers.importStep(os.path.join(CAD6, nm + ".step")).val()
    mat = m6.loc[nm, "material"] if nm in m6.index else "SS"
    asm.add(shp, name=nm, color=cq.Color(*COLORS[mat]))
    rows.append(dict(part=nm, source="phase6", material=mat, volume_cm3=shp.Volume() / 1e3,
                     mass_kg=shp.Volume() * 1e-9 * RHO[mat], valid=valid(shp)))

for nm, (shp, mat) in new_parts.items():
    cq.exporters.export(cq.Workplane().add(shp), os.path.join(CAD7, nm + ".step"))
    asm.add(shp, name=nm, color=cq.Color(*COLORS[mat]))
    rows.append(dict(part=nm, source="phase7", material=mat, volume_cm3=shp.Volume() / 1e3,
                     mass_kg=shp.Volume() * 1e-9 * RHO[mat], valid=valid(shp)))

# the dry plug position, as a part file only (not in the assembly): the stroke, visible in CAD
dry_plug = plug_solid(S_DRY)
cq.exporters.export(cq.Workplane().add(dry_plug), os.path.join(CAD7, "nozzle_plug_DRY_POSITION.step"))

out_step = os.path.join(ROOT, "cad", "engine_with_afterburner_assembly.step")
asm.save(out_step)

df = pd.DataFrame(rows)
df.to_csv(os.path.join(D7, "ab_cad_mass.csv"), index=False)

# ----------------------------------------------------------------- checks and report
pd.set_option("display.width", 220)
print("=" * 108)
print("Phase 6 parts carried over unchanged: %d" % len(kept))
print("Replaced by the afterburner: %s" % ", ".join(dropped))
print("=" * 108)
print(df[df.source == "phase7"][["part", "material", "volume_cm3", "mass_kg", "valid"]]
      .to_string(index=False, float_format=lambda x: "%.4f" % x))

bad = df[~df.valid]
print()
print("geometry: %d/%d solids valid" % ((df.valid).sum(), len(df)))
if len(bad):
    print("  INVALID: " + ", ".join(bad.part))

comp = cq.Compound.makeCompound([s for s, _ in new_parts.values()])
bb_new = comp.BoundingBox()
all_shapes = [cq.importers.importStep(os.path.join(CAD6, nm + ".step")).val() for nm in kept] + \
             [s for s, _ in new_parts.values()]
bb = cq.Compound.makeCompound(all_shapes).BoundingBox()

print()
print("=" * 108)
print("Geometry")
print("=" * 108)
print("  turbine exit at x %.1f mm, hub %.2f / tip %.2f mm" % (x_tex, r_hub_te, r_tip_te))
print("  diffuser   x %.1f -> %.1f mm (%.1f mm), outer wall %.2f -> %.2f mm (%.2f deg), hub %.2f -> 3.0 mm (%.2f deg)"
      % (x_d0, x_d1, L_DIFF, r_case_te, R_DUCT, half_angle_outer, r_hub_te, half_angle_hub))
print("  burn       x %.1f -> %.1f mm (%.1f mm), duct radius %.2f mm, liner at %.2f mm, %d gutter rings"
      % (x_d1, x_b1, L_BURN, R_DUCT, r_liner, N_GUTTER_RINGS))
print("  cowl       x %.1f -> %.1f mm (%.1f mm), %.2f -> %.2f mm" % (x_b1, x_c1, L_COWL, R_DUCT, R_COWL_EXIT))
print("  plug       shoulder at %.1f mm from the cowl start (wet); dry position %.1f mm, stroke %.1f mm"
      % (S_WET, S_DRY, abs(S_DRY - S_WET)))
x_plug_tip = x_b1 + S_WET + L_PLUG_AFT
x_dry_nozzle_exit = v("stations", "x_nozzle_exit") * MM
print("  the plug tip is the aft-most point, at x %.1f mm (%.1f mm past the cowl exit)"
      % (x_plug_tip, x_plug_tip - x_c1))
print("  assembly   x %.1f .. %.1f mm (length %.1f mm), max diameter %.1f mm"
      % (bb.xmin, bb.xmax, bb.xlen, max(bb.ylen, bb.zlen)))
print("  the afterburner replaces the dry nozzle, which ended at x %.1f mm, so the engine grows"
      % x_dry_nozzle_exit)
print("  by %.1f mm, not by the %.1f mm module length (the closure used the larger, conservative figure)"
      % (x_plug_tip - x_dry_nozzle_exit, x_c1 - x_d0))

# ---------- packaging against the engine envelope, part by part (the Phase 6A F6A.2 check)
D_env = 2 * R_case_comp
print()
print("=" * 108)
print("Packaging: does it fit inside the %.1f mm engine envelope the airframe was drawn around?" % D_env)
print("=" * 108)
clash = []
for nm, (shp, mat) in new_parts.items():
    b = shp.BoundingBox()
    r_max = max(abs(b.ymin), abs(b.ymax), abs(b.zmin), abs(b.zmax))
    clash.append(dict(part=nm, r_max_mm=r_max, over_envelope_mm=r_max - R_case_comp))
cl = pd.DataFrame(clash).sort_values("r_max_mm", ascending=False)
print(cl.to_string(index=False, float_format=lambda x: "%+.2f" % x))
out_env = cl[cl.over_envelope_mm > 0]
print()
if len(out_env):
    print("  OUTSIDE the envelope: " + ", ".join("%s (+%.1f mm)" % (r.part, r.over_envelope_mm)
                                                 for _, r in out_env.iterrows()))
    print("  The afterburner FLOW PATH fits with room to spare: the duct is at r %.2f mm against the"
          % (R_DUCT + T_CASING))
    print("  %.2f mm envelope, a %.2f mm free annulus.  What does not fit is the nozzle ACTUATOR."
          % (R_case_comp, R_case_comp - R_DUCT - T_CASING))
    print("  This is Phase 6A's F6A.2 repeated: a Volz DA 22 case is 22.0 mm on its smallest side and")
    print("  the P16 body about 20 mm, against a %.1f mm annulus over the afterburner duct and none at" % (R_case_comp - R_DUCT - T_CASING))
    print("  all over the compressor casing, where the actuator has to sit for temperature (D7.4).")
    print("  Phase 6 measured the engine-to-fuselage-skin gap at 8.7 mm, so it does not fit there either.")
    print("  Fix options -- a local fairing (which changes the airframe cross-section and hence the wave")
    print("  drag the dash margin rests on) or a longer remote linkage -- are NOT assessed (R7.8).")
else:
    print("  everything is inside the envelope")

# ----------------------------------------------------------------- mass tracking
print()
print("=" * 108)
print("Mass: CAD against the Phase 7 bottom-up model")
print("=" * 108)
model = dict(HW["configurations"][CONFIG]["mass"])
model_nozzle = dict(NZ["plug"]["mass"])
cad7 = df[df.source == "phase7"].set_index("part").mass_kg

groups = {
    "diffuser + tail cone + struts": (["ab_diffuser_casing", "ab_tail_cone", "ab_diffuser_struts"],
                                      model["diffuser_outer_cone"] + model["diffuser_tailcone"]),
    "burn casing": (["ab_casing"], model["ab_outer_casing"]),
    "screech liner": (["ab_liner"], model["ab_liner"]),
    "flameholder + struts": (["ab_flameholder_gutters", "ab_gutter_struts"],
                             model["flameholder_gutters"] + model["gutter_struts"]),
    "spray bars + manifold": (["ab_spray_bars", "ab_fuel_manifold"],
                              model["spray_bars"] + model["fuel_manifold"]),
    "igniter": (["ab_igniter"], model["igniter"]),
    "nozzle cowl + plug + struts": (["nozzle_cowl", "nozzle_plug", "nozzle_plug_struts"],
                                    model_nozzle["cowl"] + model_nozzle["plug"] + model_nozzle["struts"]),
    "actuation (rod, pushrod, links, actuator)": (["nozzle_actuator_rod", "nozzle_pushrod",
                                                   "nozzle_link_radial", "nozzle_actuator"],
                                                  model_nozzle["rod"] + 0.095),
}
mrows = []
for g, (names, m_model) in groups.items():
    m_cad = float(sum(cad7.get(n, 0.0) for n in names))
    mrows.append(dict(group=g, CAD_kg=m_cad, model_kg=m_model,
                      delta_kg=m_cad - m_model,
                      pct=100 * (m_cad / m_model - 1) if m_model else np.nan))
mdf = pd.DataFrame(mrows)
print(mdf.to_string(index=False, float_format=lambda x: "%+.4f" % x))
tot_cad = float(cad7.sum())
tot_model = sum(m for _, m in groups.values())
print()
print("  CAD afterburner + nozzle + actuation  %.3f kg" % tot_cad)
print("  Phase 7 bottom-up model               %.3f kg   (delta %+.3f kg, %+.1f %%)"
      % (tot_model, tot_cad - tot_model, 100 * (tot_cad / tot_model - 1)))
m6_kept = float(df[df.source == "phase6"].mass_kg.sum())
print("  Phase 6 engine parts carried over     %.3f kg" % m6_kept)
print("  WHOLE CAD ASSEMBLY                    %.3f kg (raw CAD; the mass model's x1.2025"
      % float(df.mass_kg.sum()))
print("                                                  calibration covers what CAD does not draw)")

# ---------- feed the CAD mass back into the 25 kg closure
# The CAD draws the hardware but not the allowances the bottom-up model carries, so those are
# added to the CAD side before comparing -- otherwise the CAD looks lighter than it is.
CL = json.load(open(os.path.join(D7, "ab_closure.json")))
m_model_total = CL["mass"]["total"]                      # module + nozzle + actuator + fuel system
mod = HW["configurations"][CONFIG]["mass"]
noz_m = NZ["plug"]["mass"]
undrawn = {
    "AB fuel valve and lines (A7.13)": mod["fuel_valve_and_lines"],
    "plug slide bearing": noz_m["slide_bearing"],
    "actuator linkage allowance": 0.060,
    "AB fuel system (A7.15)": CL["mass"]["fuel_system"],
}
flanges = 0.10 * float(cad7[[n for n in cad7.index if n.startswith("ab_")]].sum())
undrawn["flanges + fasteners, 10 % of the drawn AB module"] = flanges
m_cad_total = tot_cad + sum(undrawn.values())
d = m_cad_total - m_model_total
growth = CL["closure"]["growth_frac"]
togw_model = CL["closure"]["TOGW_phase7"]
togw_cad = togw_model + d * (1.0 + growth)

print()
print("=" * 108)
print("What the CAD mass does to the 25 kg closure")
print("=" * 108)
print("  drawn in CAD                                      %.3f kg" % tot_cad)
for k, val in undrawn.items():
    print("  + %-46s %.3f kg" % (k, val))
print("  %-48s %.3f kg" % ("CAD-based afterburner total", m_cad_total))
print("  %-48s %.3f kg" % ("Phase 7 bottom-up model", m_model_total))
print("  %-48s %+.3f kg" % ("difference", d))
print()
print("  TOGW was %.3f kg (margin %+.3f kg).  With the CAD mass and its %.1f %% growth allowance:"
      % (togw_model, 25.0 - togw_model, 100 * growth))
print("  TOGW %.3f kg, margin to 25 kg %+.3f kg  ->  %s"
      % (togw_cad, 25.0 - togw_cad, "still closes" if togw_cad <= 25.0 else "OVER the 25 kg ceiling"))
m03 = HW["configurations"]["M0.30_theta10"]["mass"]["total"]
m07 = HW["configurations"][CONFIG]["mass"]["total"]
print("  The lighter duct-Mach-0.30 / 10 deg build is %.3f kg lighter in the module alone, which on"
      % (m07 - m03))
print("  the same drawing basis would put it at about %.3f kg (margin %+.3f kg)."
      % (togw_cad - (m07 - m03) * (1.0 + growth), 25.0 - (togw_cad - (m07 - m03) * (1.0 + growth))))

json.dump(dict(config=CONFIG, cad_mass_kg=float(df.mass_kg.sum()),
               cad_afterburner_kg=tot_cad, model_afterburner_kg=tot_model,
               cad_total_with_allowances_kg=m_cad_total, undrawn_allowances=undrawn,
               model_total_kg=m_model_total,
               delta_kg=d, TOGW_model_kg=togw_model, TOGW_cad_kg=togw_cad,
               margin_to_25_kg=25.0 - togw_cad,
               length=dict(x_turbine_exit_mm=x_tex, x_plug_tip_mm=x_plug_tip,
                           x_dry_nozzle_exit_mm=x_dry_nozzle_exit,
                           growth_over_dry_mm=x_plug_tip - x_dry_nozzle_exit,
                           assembly_length_mm=bb.xlen, max_diameter_mm=max(bb.ylen, bb.zlen)),
               packaging=cl.to_dict("records"), envelope_diameter_mm=D_env,
               groups=mdf.to_dict("records")),
          open(os.path.join(D7, "ab_cad.json"), "w"), indent=1, default=float)

print()
print("wrote %s" % out_step)
print("wrote %s" % os.path.join(D7, "ab_cad_mass.csv"))
print("wrote %s" % os.path.join(D7, "ab_cad.json"))
print("wrote %d part files to cad/afterburner/" % (len(new_parts) + 1))
