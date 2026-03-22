#!/bin/bash
set -euo pipefail

mkdir -p ./outputs

SUMMARY_FLAG=""
if [ "${PARAM_REPORT_SUMMARY:-true}" = "true" ]; then
    SUMMARY_FLAG="--summary"
fi

found=0
for results_file in ./*_results.json; do
    [ -e "$results_file" ] || continue
    found=$((found + 1))
    echo "==> Reporting: $results_file"
    binding-metrics-report \
        --results  "$results_file" \
        --format   csv \
        --output-dir ./outputs/ \
        $SUMMARY_FLAG
done

if [ "$found" -eq 0 ]; then
    echo "ERROR: no *_results.json files found" >&2
    exit 1
fi

echo "Report(s) written to ./outputs/"
