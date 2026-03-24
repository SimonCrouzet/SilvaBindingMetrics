#!/bin/bash
set -euo pipefail

mkdir -p ./outputs

# Always pass through pre-relaxation structures for comparison in node 03
for f in ./cleaned_*.cif ./cleaned_*.pdb; do
    [ -e "$f" ] || continue
    cp "$f" "./outputs/$(basename "$f")"
done

run_relax() {
    local input_file="$1"
    local name
    name=$(basename "$input_file")
    name="${name%.*}"          # e.g. "cleaned_complex"
    name="${name#cleaned_}"    # e.g. "complex"

    echo "==> Relaxing: $input_file (sample_id=$name)"

    CHAIN_ARGS=""
    [ -n "${PARAM_PEPTIDE_CHAIN:-}" ]  && CHAIN_ARGS="$CHAIN_ARGS --peptide-chain  ${PARAM_PEPTIDE_CHAIN}"
    [ -n "${PARAM_RECEPTOR_CHAIN:-}" ] && CHAIN_ARGS="$CHAIN_ARGS --receptor-chain ${PARAM_RECEPTOR_CHAIN}"

    binding-metrics-relax \
        --input          "$input_file" \
        --output-dir     ./outputs/ \
        --md-duration-ps "${PARAM_MD_DURATION_PS:-200.0}" \
        --solvent-model  "${PARAM_SOLVENT_MODEL:-obc2}" \
        --device         "${PARAM_DEVICE:-cuda}" \
        --sample-id      "$name" \
        --log-file       "./outputs/${name}_relax.log" \
        $CHAIN_ARGS

    echo "    Done: outputs/${name}_minimized.cif"
    [ "${PARAM_MD_DURATION_PS:-200.0}" != "0" ] && \
        [ "${PARAM_MD_DURATION_PS:-200.0}" != "0.0" ] && \
        echo "         outputs/${name}_md_final.cif"
}

for f in ./cleaned_*.cif ./cleaned_*.pdb; do
    [ -e "$f" ] || continue
    run_relax "$f"
done
