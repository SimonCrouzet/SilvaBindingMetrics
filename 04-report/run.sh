#!/bin/bash
set -euo pipefail

mkdir -p ./outputs

for f in inputs/*; do [ -e "$f" ] && cp "$f" .; done

found=0
for results_file in ./*_results.json; do
    [ -e "$results_file" ] || continue
    found=$((found + 1))
    name=$(basename "$results_file" _results.json)
    echo "==> Reporting: $results_file"
    binding-metrics-report \
        --results        "$results_file" \
        --format         csv \
        --output-dir     ./outputs/ \
        --summary \
        --summary-format html \
        --log-file       "./outputs/${name}_report.log"
done

if [ "$found" -eq 0 ]; then
    echo "ERROR: no *_results.json files found" >&2
    exit 1
fi

echo "Report(s) written to ./outputs/"
