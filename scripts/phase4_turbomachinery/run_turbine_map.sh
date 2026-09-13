#!/usr/bin/env bash
# run turbine_map.py one speed line per process (isolates solver crashes), then merge into one map file
# usage: run_turbine_map.sh <tag>
TAG=$1; ROOT=$(cd "$(dirname "$0")/../.." && pwd); PY=$ROOT/.venv-np1/Scripts/python.exe
mkdir -p $ROOT/data/phase4/tmap_parts
for N in ${TMAP_NS:-1.0 1.1 0.9 0.8 0.7 0.6 0.5 0.4 0.3}; do
  $PY $ROOT/scripts/phase4_turbomachinery/turbine_map.py $ROOT/data/phase3/${TAG}_tt_out.json $ROOT/data/phase4/tmap_parts/${TAG}_N$N.json $N 2>&1 | grep -E "DESIGN CHECK|^N " || echo "N $N: process failed"
done
cd "$ROOT" && ./.venv/Scripts/python.exe - <<PYEOF
import json, glob
parts = sorted(glob.glob("data/phase4/tmap_parts/${TAG}_N*.json"))
d = None
for p in parts:
    x = json.load(open(p))
    if d is None: d = x
    else: d["points"] += x["points"]
json.dump(d, open("data/phase4/turbine_map_${TAG}.json", "w"), indent=1)
print("merged", len(parts), "parts,", len(d["points"]), "points")
PYEOF
