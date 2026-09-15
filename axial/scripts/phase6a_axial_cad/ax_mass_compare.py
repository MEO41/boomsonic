"""Phase 6A (EXPLORATORY): CAD mass against the analysis mass model, item by item (run in .venv-cad).

The CAD is compared with the RAW bottom-up model (data/phase4ax/closure_<tag>.json engine.items), not the
calibrated 6.86 kg: the x1.2025 calibration exists precisely for what the CAD does not draw (flanges, bolts,
fillets, seals, fuel manifold, igniters, instrumentation bosses, wiring).

The variable-geometry systems are compared separately and in detail, because they are the reason Phase 6A was
run (open risk 4.4). Discrepancies are REPORTED, never absorbed by changing the CAD.
Outputs: data/phase6a/mass_compare.csv, data/phase6a/vg_mass_breakdown.csv
"""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AXROOT = os.path.abspath(os.path.join(HERE, "..", "..")); ROOT = os.path.abspath(os.path.join(AXROOT, ".."))
OUT = os.path.join(AXROOT, "data", "phase6a")
TAG = json.load(open(os.path.join(OUT, "axial_params.json")))["tag"]
E = json.load(open(os.path.join(OUT, "axial_params.json")))
CL = json.load(open(os.path.join(AXROOT, "data", "phase4ax", f"closure_{TAG}.json")))["engine"]
items = CL["items"]
core = pd.read_csv(os.path.join(OUT, "engine_cad_mass.csv")).set_index("part")["mass_kg"]
vgdf = pd.read_csv(os.path.join(OUT, "vg_cad_mass.csv"))
vg = vgdf[~vgdf.part.str.endswith("_open")].set_index("part")            # the open flap copy is the same hardware
cad = pd.concat([core, vg["mass_kg"]])

S = lambda *pre: [p for p in cad.index if any(p.startswith(q) for q in pre)]
MAP = {
    "rotor_blades": S("rotor_blades_stage"), "rotor_discs": S("disc_stage"),
    "stators": S("stator_vanes_stage", "stator_band_stage"), "compressor_casing": ["compressor_casing"],
    "drum_ties": ["rotor_drum"], "ngv_vanes": ["ngv_vanes"], "ngv_rings": ["ngv_hub_ring", "ngv_shroud_ring"],
    "turbine_blades": ["turbine_blades"], "turbine_disc": ["turbine_disc"], "turbine_shroud": ["turbine_shroud"],
    "combustor_liners": ["liner_outer", "liner_inner", "liner_dome", "vaporisers"], "outer_casing": ["hot_casing"],
    "nozzle_cones": ["nozzle_outer_cone", "tail_cone"], "shaft": ["shaft"],
    "shaft_tunnel_bearing_housings": ["shaft_tunnel", "housing_front", "housing_rear"],
    "bearings_2x_hybrid": ["bearing_front", "bearing_rear"],
    "VIGV vanes + spindles + levers + unison ring": ["vg_vigv_vanes", "vg_vigv_spindles", "vg_vigv_cranks",
                                                     "vg_vigv_unison_ring", "vg_vigv_pushrod", "vg_vigv_actuator_bracket"],
    "VIGV actuator (servo)": ["vg_vigv_actuator"],
    "bleed manifold (Al ring 25 x 1 mm) + band valve (SS 20 x 0.5 mm)": ["vg_bleed_manifold", "vg_bleed_band_valve",
                                                                         "vg_bleed_ports", "vg_bleed_duct",
                                                                         "vg_bleed_pushrod", "vg_bleed_actuator_bracket"],
    "bleed valve actuator (servo)": ["vg_bleed_actuator"],
    "variable nozzle flaps + sync ring + hinges": ["vg_nozzle_flaps_closed", "vg_nozzle_hinge_ring",
                                                   "vg_nozzle_sync_ring", "vg_nozzle_pushrods",
                                                   "vg_nozzle_heat_shield", "vg_nozzle_reduction"],
    "variable nozzle actuator (servo, heat-shielded)": ["vg_nozzle_actuator"],
    "starter_motor": [], "fuel_manifold_igniter": [], "fasteners_seals_balancing_10pct": [],
}
rows, used = [], set()
for k, val in items.items():
    ps = [p for p in MAP.get(k, []) if p in cad.index and p not in used]; used |= set(ps)
    rows.append(dict(model_item=k, model_raw_kg=float(val), cad_parts="+".join(ps),
                     cad_kg=float(cad[ps].sum()) if ps else np.nan))
for p in cad.index:
    if p not in used:
        rows.append(dict(model_item="(no model item)", model_raw_kg=np.nan, cad_parts=p, cad_kg=float(cad[p])))
df = pd.DataFrame(rows)
df["cad_over_model"] = df.cad_kg / df.model_raw_kg
df["delta_g"] = (df.cad_kg - df.model_raw_kg) * 1e3
drawn = df[df.cad_parts.astype(str).str.len() > 0].model_raw_kg.sum()
df = pd.concat([df, pd.DataFrame([
    dict(model_item="SUBTOTAL, items drawn in the CAD", model_raw_kg=float(drawn), cad_parts="all",
         cad_kg=float(cad.sum()), cad_over_model=float(cad.sum()) / drawn, delta_g=(cad.sum() - drawn) * 1e3),
    dict(model_item="TOTAL raw (incl. starter, manifold, 10 % fasteners)", model_raw_kg=CL["raw"],
         cad_parts="", cad_kg=np.nan, cad_over_model=np.nan, delta_g=np.nan)])], ignore_index=True)
df.to_csv(os.path.join(OUT, "mass_compare.csv"), index=False)

# ---- the variable-geometry systems on their own
VG_SYS = {"VIGV": ["VIGV vanes + spindles + levers + unison ring", "VIGV actuator (servo)"],
          "bleed": ["bleed manifold (Al ring 25 x 1 mm) + band valve (SS 20 x 0.5 mm)", "bleed valve actuator (servo)"],
          "variable nozzle": ["variable nozzle flaps + sync ring + hinges", "variable nozzle actuator (servo, heat-shielded)"]}
vrows = []
for sysname, keys in VG_SYS.items():
    mm = sum(items[k] for k in keys)
    cc = sum(float(cad[[p for p in MAP[k] if p in cad.index]].sum()) for k in keys)
    vrows.append(dict(system=sysname, freeze_allowance_kg=mm, cad_kg=cc, delta_g=(cc - mm) * 1e3, ratio=cc / mm))
vdf = pd.DataFrame(vrows)
vdf.loc[len(vdf)] = dict(system="TOTAL variable geometry", freeze_allowance_kg=vdf.freeze_allowance_kg.sum(),
                         cad_kg=vdf.cad_kg.sum(), delta_g=vdf.delta_g.sum(), ratio=vdf.cad_kg.sum() / vdf.freeze_allowance_kg.sum())
vdf.to_csv(os.path.join(OUT, "vg_mass_breakdown.csv"), index=False)

# ---- what the new VG mass would do to the engine and the closure, if carried through (NOT a re-closure)
d_vg = float(vdf.iloc[-1].delta_g) / 1e3
raw_new = CL["raw"] + d_vg
K_M = E["envelope"]["K_M"]["value"]
pd.set_option("display.width", 250)
print(df.round(4).to_string(index=False))
print("\n=== VARIABLE GEOMETRY, the reason Phase 6A was run ===")
print(vdf.round(4).to_string(index=False))
print(f"\nIf the CAD masses were carried into the engine model (they are NOT, this is exploratory):")
print(f"  raw dry mass {CL['raw']:.3f} -> {raw_new:.3f} kg ({d_vg * 1e3:+.0f} g)")
print(f"  calibrated (x{K_M:.4f}) {CL['cal']:.3f} -> {raw_new * K_M:.3f} kg ({(raw_new - CL['raw']) * K_M * 1e3:+.0f} g)")
print(f"  TOGW would move by the same {(raw_new - CL['raw']) * K_M:+.3f} kg before any airframe re-iteration:")
print(f"    powered-descent case 22.12 -> {22.12 + (raw_new - CL['raw']) * K_M:.2f} kg (margin {2.88 - (raw_new - CL['raw']) * K_M:.2f} kg)")
print(f"    engine-off case     18.54 -> {18.54 + (raw_new - CL['raw']) * K_M:.2f} kg (margin {6.46 - (raw_new - CL['raw']) * K_M:.2f} kg)")
