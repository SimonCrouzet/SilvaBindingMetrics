#!/bin/bash
set -euo pipefail

mkdir -p ./outputs

run_prep() {
    local input_file="$1"
    local name
    name=$(basename "$input_file")
    name="${name%.*}"   # strip extension
    local ext="${input_file##*.}"
    local output="./outputs/cleaned_${name}.${ext}"

    echo "==> Preparing: $input_file -> $output"
    binding-metrics-prep \
        --input  "$input_file" \
        --output "$output" \
        --ph     "${PARAM_PH:-7.4}" \
        | tee "./outputs/prep_summary_${name}.json"
    echo "    Done: $output"
}

INPUT_DIR="./${PARAM_INPUT_DIR:-input_files}"

if [ "${PARAM_BATCH_MODE:-false}" = "true" ]; then
    # Batch mode: process every CIF/PDB in INPUT_DIR
    found=0
    for f in "${INPUT_DIR}"/*.cif "${INPUT_DIR}"/*.pdb; do
        [ -e "$f" ] || continue
        run_prep "$f"
        found=$((found + 1))
    done
    if [ "$found" -eq 0 ]; then
        echo "ERROR: no CIF/PDB files found in ${INPUT_DIR}" >&2
        exit 1
    fi
    echo "Prepared $found structure(s)."
else
    # Single mode: INPUT_DIR/INPUT_COMPLEX
    input_file="${INPUT_DIR}/${PARAM_INPUT_COMPLEX:-example_complex.cif}"
    if [ ! -f "$input_file" ]; then
        echo "ERROR: input file not found: $input_file" >&2
        echo "  Place your structure in ${INPUT_DIR}/ and set INPUT_COMPLEX to its filename." >&2
        exit 1
    fi
    run_prep "$input_file"
fi
