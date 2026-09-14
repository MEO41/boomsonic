#!/usr/bin/env bash
# centrifugal stage map in parallel chunks (one process per speed group), then merge. usage: run_centrifugal_map.sh <tag> [suffix]
# env: CC_SRC = design file (default data/phase3/<tag>_ac_out.json); MAP_DIR = output dir (default data/phase4);
#      CC_GROUPS = space-separated speed groups (default five groups covering 0.4-1.05)
TAG=$1; SUF=${2:-}; ROOT=$(cd "$(dirname "$0")/../.." && pwd); cd "$ROOT"
PY=./.venv-np1/Scripts/python.exe
SRC=${CC_SRC:-data/phase3/${TAG}_ac_out.json}; OUTD=${MAP_DIR:-data/phase4}
mkdir -p $OUTD/cmap_parts
i=0
for G in ${CC_GROUPS:-"1.0,0.6" "1.05,0.5" "0.95,0.4" "0.9,0.7" "0.85,0.8"}; do
  $PY scripts/phase4_turbomachinery/centrifugal_map.py $SRC $OUTD/cmap_parts/${TAG}${SUF}_g$i.json $G > $OUTD/cmap_parts/${TAG}${SUF}_g$i.log 2>&1 &
  i=$((i+1))
done
wait
./.venv/Scripts/python.exe - <<PYEOF
import json, glob
parts = sorted(glob.glob("$OUTD/cmap_parts/${TAG}${SUF}_g*.json")); d = None
for p in parts:
    x = json.load(open(p))
    if d is None: d = x
    else: d["points"] += x["points"]
json.dump(d, open("$OUTD/centrifugal_map_${TAG}${SUF}.json", "w"), indent=1)
print("merged", len(parts), "parts,", len(d["points"]), "points,", sum(1 for p in d["points"] if p.get("success")), "converged")
PYEOF
