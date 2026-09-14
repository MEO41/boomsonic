"""Phase 6: CAD mass vs the analysis mass model, item by item (run in .venv: needs the Phase 3R / 4R modules).

Model: engine_mass.engine() at the Phase 4R engine (cc_closure.engine_phase4: fielded cycle, grown combustor at 0.8 x the
liner rule, 32 x 25.6 mm shaft, 18 mm tunnel) -- the bottom-up "raw" masses before the x1.20 calibration.
CAD: data/phase6/engine_cad_mass.csv (engine_cad.py, volumes x the stated densities).
The CAD parts are conceptual (no flanges, bolts, fillets, seals, fuel manifold, igniters, instrumentation bosses): the
calibration factor exists for exactly those items, so the CAD is compared with the RAW model, not the calibrated one.
Output: data/phase6/mass_compare.csv
"""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase4_turbomachinery")); sys.path.insert(0, os.path.join(ROOT, "scripts", "phase3_cycle"))
os.environ.setdefault("P3_DATA", "phase3r")
import cc_closure as cc
d = json.load(open(os.path.join(ROOT, "data", "phase3r", f"cct_{cc.TAG}.json")))
e = cc.engine_phase4(d); items = e["engine"]["items"]
cad = pd.read_csv(os.path.join(ROOT, "data", "phase6", "engine_cad_mass.csv")).set_index("part")["mass_kg"]
MAP = {  # model item -> CAD parts
    "impeller": ["impeller"],
    "shroud_inlet": ["compressor_front_shroud", "compressor_front_wall"],
    "diffuser_deswirl": ["diffuser_back_plate", "diffuser_vanes", "deswirl_inner_wall", "deswirl_vanes"],
    "ngv_vanes": ["ngv_vanes"], "ngv_rings": ["ngv_hub_ring", "ngv_shroud_ring"], "turbine_blades": ["turbine_blades"],
    "turbine_disc": ["turbine_disc"], "turbine_shroud": ["turbine_shroud"],
    "combustor_liners": ["liner_outer", "liner_inner", "liner_dome", "vaporisers"], "outer_casing": ["compressor_casing", "hot_casing"],
    "nozzle_cones": ["nozzle_outer_cone", "tail_cone"], "shaft": ["shaft"],
    "shaft_tunnel_bearing_housings": ["shaft_tunnel", "housing_front", "housing_rear"], "bearings_2x_hybrid": ["bearing_front", "bearing_rear"],
    "starter_motor": [], "fuel_manifold_igniter": [], "fasteners_seals_balancing_10pct": [],     # not modelled in the CAD
}
rows, used = [], set()
for k, v in items.items():
    parts = MAP.get(k, [])
    parts = [p for p in parts if p in cad.index and p not in used]; used |= set(parts)
    rows.append(dict(model_item=k, model_raw_kg=float(v), cad_parts="+".join(parts), cad_kg=float(cad[parts].sum()) if parts else np.nan))
for p in cad.index:
    if p not in used: rows.append(dict(model_item="(no model item)", model_raw_kg=np.nan, cad_parts=p, cad_kg=float(cad[p])))
df = pd.DataFrame(rows); df["cad_over_model"] = df.cad_kg / df.model_raw_kg
hw = df[df.cad_parts.astype(str).str.len() > 0].model_raw_kg.sum()
tot = [dict(model_item="SUBTOTAL items drawn in the CAD", model_raw_kg=float(hw), cad_parts="all", cad_kg=float(cad.sum()), cad_over_model=float(cad.sum()) / hw),
       dict(model_item="TOTAL raw (incl. starter, manifold, 10 % fasteners)", model_raw_kg=e["dry_raw"], cad_parts="", cad_kg=np.nan, cad_over_model=np.nan)]
df = pd.concat([df, pd.DataFrame(tot)], ignore_index=True)
df.to_csv(os.path.join(ROOT, "data", "phase6", "mass_compare.csv"), index=False)
pd.set_option("display.width", 220); print(df.round(3).to_string(index=False))
print(f"calibrated model {e['dry_cal']:.2f} kg (x{d['calibration']['K_M']:.2f}); model length {e['engine']['L_engine_mm']:.1f} mm raw, {e['L_cal']:.1f} calibrated")
