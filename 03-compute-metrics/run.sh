#!/bin/bash
set -euo pipefail

mkdir -p ./outputs

python3 /workspace/compute_metrics.py \
    --inputs-dir     ./ \
    --outputs-dir    ./outputs/ \
    --device         "${PARAM_DEVICE:-cpu}" \
    --peptide-chain  "${PARAM_PEPTIDE_CHAIN:-}" \
    --receptor-chain "${PARAM_RECEPTOR_CHAIN:-}"
