#!/usr/bin/env bash
# re-run compressor-map speed groups that crashed (out of memory), keeping their original part numbers, then re-merge
cd /c/Users/MEO/Desktop/Projects/JetEngine/boomsonic_v0
PY=./.venv-np1/Scripts/python.exe; D=data/phase3r/maps
run() { $PY scripts/phase4_turbomachinery/centrifugal_map.py data/phase3r/$1_cc_out.json $D/cmap_parts/$1_g$2.json $3 > $D/cmap_parts/$1_g$2.log 2>&1; }
run ce75000_opr4_t1150_b0_cap 3 0.9,0.7 & run ce75000_opr4_t1150_b20_cap 0 1.0,0.6 & wait
run ce75000_opr4_t1150_b20_cap 1 1.05,0.5 & run ce75000_opr4_t1150_b20_cap 3 0.9,0.7 & wait
for T in ce75000_opr4_t1150_b0_cap ce75000_opr4_t1150_b20_cap; do
./.venv/Scripts/python.exe - <<PYEOF
import json, glob
parts = sorted(glob.glob("$D/cmap_parts/${T}_g*.json")); d = None
for p in parts:
    x = json.load(open(p))
    if d is None: d = x
    else: d["points"] += x["points"]
json.dump(d, open("$D/centrifugal_map_${T}.json", "w"), indent=1)
print("${T}: merged", len(parts), "parts,", len(d["points"]), "points,", sum(1 for p in d["points"] if p.get("success")), "converged")
PYEOF
done
