#!/bin/bash
set -euo pipefail

mkdir -p ./outputs

# Pass through scores for easy access in the final output
cp ./inputs/scores.csv  ./outputs/scores.csv
cp ./inputs/scores.json ./outputs/scores.json

# Patch title and rank_by from workflow params into the config
python3 - <<'PYEOF'
import json, os, sys

config_path = "/workspace/report_config.json"
with open(config_path) as f:
    cfg = json.load(f)

title   = os.environ.get("PARAM_REPORT_TITLE", "").strip()
rank_by = os.environ.get("PARAM_RANK_BY",      "").strip()

if title:
    cfg["title"] = title
if rank_by:
    cfg["rank_by"] = rank_by

out_path = "/tmp/report_config_runtime.json"
with open(out_path, "w") as f:
    json.dump(cfg, f, indent=2)

print(f"Report config: title={cfg['title']!r}  rank_by={cfg['rank_by']!r}")
PYEOF

binding-metrics-report \
    --input   ./inputs/scores.csv \
    --output  ./outputs/report.html \
    --config  /tmp/report_config_runtime.json

echo "Report written to ./outputs/report.html"
