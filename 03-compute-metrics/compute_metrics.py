"""Node 03 — Compute Metrics

Mirrors the steps of ``binding-metrics-run`` on the relaxed structures from
node 02: energy → interface → geometry → electrostatics.  Relaxation has
already been done upstream so interaction energy is evaluated in ``raw`` mode
on the already-relaxed structure.  Pre/post RMSD is computed from the
cleaned structure passed through by node 02.

Outputs one ``{sample_id}_results.json`` per structure (consumed by node 04
via ``binding-metrics-report``).

Usage:
    python compute_metrics.py [--inputs-dir .] [--outputs-dir ./outputs]
                              [--device cpu|cuda]
                              [--peptide-chain A] [--receptor-chain B]
"""

import argparse
import sys
import traceback
from pathlib import Path


def _safe(fn, label: str, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        print(f"  [warning] {label} failed: {exc}", flush=True)
        traceback.print_exc()
        return {"error": str(exc)}


def _step(name: str) -> None:
    print(f"\n{'='*60}\n  {name}\n{'='*60}", flush=True)


def process_structure(relaxed_path, pre_path, outputs_dir, device, peptide_chain, receptor_chain):
    stem = relaxed_path.stem
    if stem.endswith("_md_final"):
        sample_id = stem[:-9]
    elif stem.endswith("_minimized"):
        sample_id = stem[:-10]
    else:
        sample_id = stem

    print(f"\n{'#'*60}\n  sample: {sample_id}\n  input:  {relaxed_path}\n{'#'*60}", flush=True)

    results: dict = {"sample_id": sample_id, "input": str(relaxed_path)}

    # Chain detection
    _step("Chain detection")
    from binding_metrics.io.structures import detect_chains_from_file
    chain_info = _safe(detect_chains_from_file, "chain detection",
                       relaxed_path, peptide_chain=peptide_chain,
                       receptor_chain=receptor_chain, verbose=True)
    if "error" not in chain_info:
        peptide_chain  = chain_info.get("peptide_chain")  or peptide_chain
        receptor_chain = chain_info.get("receptor_chain") or receptor_chain
    results["chains"] = chain_info

    # Relax — done upstream; record placeholder + pre/post RMSD
    relax_info: dict = {"skipped": True, "note": "relaxation done in node 02"}
    if pre_path is not None and pre_path.exists():
        _step("Pre/post RMSD")
        from binding_metrics.metrics.comparison import compute_structure_rmsd
        relax_info["pre_post_comparison"] = _safe(
            compute_structure_rmsd, "RMSD pre→post",
            str(pre_path), str(relaxed_path), design_chain=peptide_chain,
        )
    results["relax"] = relax_info

    # Energy (raw mode — structure already relaxed)
    _step("Interaction Energy")
    from binding_metrics.metrics.energy import compute_interaction_energy
    results["energy"] = _safe(
        compute_interaction_energy, "energy",
        relaxed_path, peptide_chain=peptide_chain, receptor_chain=receptor_chain,
        device=device, modes=("raw",),
    )

    # Interface
    _step("Interface Metrics (SASA, ΔG_int, H-bonds, salt bridges)")
    from binding_metrics.metrics.interface import compute_interface_metrics
    results["interface"] = _safe(
        compute_interface_metrics, "interface",
        relaxed_path, design_chain=peptide_chain, receptor_chain=receptor_chain,
    )

    # Geometry
    _step("Geometry (Ramachandran, ω-planarity, shape complementarity, buried void)")
    from binding_metrics.metrics.geometry import (
        compute_ramachandran, compute_omega_planarity,
        compute_shape_complementarity, compute_buried_void_volume,
    )
    results["geometry"] = {
        "ramachandran":          _safe(compute_ramachandran,          "ramachandran",          relaxed_path, chain=peptide_chain),
        "omega":                 _safe(compute_omega_planarity,       "omega planarity",       relaxed_path, chain=peptide_chain),
        "shape_complementarity": _safe(compute_shape_complementarity, "shape complementarity", relaxed_path),
        "buried_void":           _safe(compute_buried_void_volume,    "buried void volume",    relaxed_path),
    }

    # Electrostatics
    _step("Electrostatics (Coulomb cross-chain)")
    from binding_metrics.metrics.electrostatics import compute_coulomb_cross_chain
    results["electrostatics"] = _safe(
        compute_coulomb_cross_chain, "electrostatics",
        relaxed_path, peptide_chain=peptide_chain, receptor_chain=receptor_chain,
    )

    results["openfold"] = {"skipped": True}

    # Write per-structure JSON
    from binding_metrics.protocols.report import write_report
    out_path = write_report(results, outputs_dir, sample_id, fmt="json")
    print(f"\n  Results → {out_path}", flush=True)

    return results


def main():
    parser = argparse.ArgumentParser(description="Compute binding metrics (node 03).")
    parser.add_argument("--inputs-dir",     type=Path, default=Path("."))
    parser.add_argument("--outputs-dir",    type=Path, default=Path("./outputs"))
    parser.add_argument("--device",         type=str,  default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--peptide-chain",  type=str,  default="")
    parser.add_argument("--receptor-chain", type=str,  default="")
    args = parser.parse_args()

    inputs_dir  = args.inputs_dir
    outputs_dir = args.outputs_dir
    outputs_dir.mkdir(parents=True, exist_ok=True)

    peptide_chain  = args.peptide_chain  or None
    receptor_chain = args.receptor_chain or None

    # Discover relaxed structures — priority: *_md_final > *_minimized > cleaned (fallback)
    relaxed: dict[str, Path] = {}
    for pat in ("*_md_final.cif", "*_md_final.pdb"):
        for f in sorted(inputs_dir.glob(pat)):
            relaxed.setdefault(f.stem[:-9], f)
    for pat in ("*_minimized.cif", "*_minimized.pdb"):
        for f in sorted(inputs_dir.glob(pat)):
            relaxed.setdefault(f.stem[:-10], f)
    for pat in ("cleaned_*.cif", "cleaned_*.pdb"):
        for f in sorted(inputs_dir.glob(pat)):
            stem = f.stem[8:]
            if stem not in relaxed:
                print(f"  [warning] no relaxed structure for '{stem}'; using cleaned fallback.")
                relaxed[stem] = f

    if not relaxed:
        print(f"ERROR: no structures found in {inputs_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"\nFound {len(relaxed)} structure(s) to process.")

    processed = 0
    for stem, relaxed_path in sorted(relaxed.items()):
        pre_path = None
        for ext in (".cif", ".pdb"):
            c = inputs_dir / f"cleaned_{stem}{ext}"
            if c.exists():
                pre_path = c
                break
        try:
            process_structure(relaxed_path, pre_path, outputs_dir,
                              args.device, peptide_chain, receptor_chain)
            processed += 1
        except Exception as exc:
            print(f"\n[ERROR] {relaxed_path.name}: {exc}", file=sys.stderr)
            traceback.print_exc()

    print(f"\n{'#'*60}\n  Done: {processed}/{len(relaxed)} processed → {outputs_dir}\n{'#'*60}\n", flush=True)
    if processed == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
