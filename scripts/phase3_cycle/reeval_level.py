"""Re-evaluate one technology level of an existing trade case with the current code (feasibility check,
fresh pyCycle problem). Usage: python reeval_level.py <case_tag> <level> <OPR> [cc_ref]"""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
tag, level, opr = sys.argv[1], sys.argv[2], float(sys.argv[3])
os.environ["P3_OPR"] = str(opr)
sys.path.insert(0, HERE)
import arch_trade as at
d = json.load(open(os.path.join(ROOT, "data", "phase3", f"trade_{tag}_tool.json")))
case = d["case"]; case["eta_c_centrifugal_ref"] = float(sys.argv[4]) if len(sys.argv) > 4 else 0.794
ev = at.evaluate(case, level)
if ev is None:
    print("CYCLE DOES NOT CLOSE"); sys.exit(0)
af = at.airframe(ev); e = ev["engine"]
row = dict(case=tag, arch=case["kind"], rpm=case["rpm"], level=level, eta_c=ev["eta_c"], eta_t=ev["eta_t"], W=ev["cycle"]["W_kgps"],
           TSFC_dash=ev["cycle"]["TSFC_kgpNh"], Fn=ev["cycle"]["Fn_N"], D_engine_mm=e["D_engine_mm"], D_comp=e["D_breakdown"]["compressor"],
           D_comb=e["D_breakdown"]["combustor"], D_turb=e["D_breakdown"]["turbine"], D_engine_comb_hi_mm=ev["engine_comb_hi"]["D_engine_mm"],
           L_engine_mm=e["L_engine_mm"], dry_mass_kg=e["dry_mass_kg"], dry_mass_comb_hi_kg=ev["engine_comb_hi"]["dry_mass_kg"],
           CDS_nom=af["dash"]["nom"]["CDS_cm2"], CDS_hi=af["dash"]["hi"]["CDS_cm2"], drag_nom=af["dash"]["nom"]["drag_N"], drag_hi=af["dash"]["hi"]["drag_N"],
           margin_nom=af["dash"]["nom"]["margin"], margin_hi=af["dash"]["hi"]["margin"], TOGW=af["TOGW_kg"], fuel=af["fuel_kg"])
print({k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else v) for k, v in row.items()})
json.dump(dict(case=case, eval=ev, airframe=af), open(os.path.join(ROOT, "data", "phase3", f"trade_{tag}_{level}.json"), "w"), indent=1, default=float)
import pandas as pd
fn = os.path.join(ROOT, "data", f"phase3_arch_trade_opr{opr:g}_t1150{'_cap' if tag.endswith('_cap') else ''}.csv"); df = pd.read_csv(fn)
df = df[~((df.case == tag) & (df.level == level))]; df = pd.concat([df, pd.DataFrame([row])], ignore_index=True); df.to_csv(fn, index=False)
