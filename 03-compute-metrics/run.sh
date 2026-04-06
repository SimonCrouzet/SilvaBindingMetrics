#!/bin/bash
set -euo pipefail

mkdir -p ./outputs

for f in inputs/*; do [ -e "$f" ] && cp "$f" .; done

python3 ./compute_metrics.py \
    --inputs-dir     ./ \
    --outputs-dir    ./outputs/ \
    --device         "${PARAM_DEVICE:-cuda}" \
    --peptide-chain  "${PARAM_PEPTIDE_CHAIN:-}" \
    --receptor-chain "${PARAM_RECEPTOR_CHAIN:-}" \
    --log-file       ./outputs/metrics.log
