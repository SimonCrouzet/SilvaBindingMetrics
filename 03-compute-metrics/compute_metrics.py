"""
Node 03 — Compute Metrics

For each structure pair (pre-relaxation cleaned_*.cif, post-relaxation *_md_final.cif
or *_minimized.cif), runs the full binding-metrics suite and writes scores.csv.

Column naming convention:
  pre_<metric>   — metric computed on the cleaned (pre-relaxation) structure
  post_<metric>  — metric computed on the relaxed structure
  delta_<metric> — post − pre  (relaxation-induced change; key scalars only)
  rmsd, bb_rmsd, rmsd_design, bb_rmsd_design — comparison between pre and post

Usage:
  python compute_metrics.py [--inputs-dir DIR] [--outputs-dir DIR] [--device cpu|cuda]
                            [--peptide-chain A] [--receptor-chain B]
"""

import argparse
import json
import sys
import traceback
from pathlib import Path


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _safe(fn, label: str, *args, **kwargs):
    """Call fn(*args, **kwargs), returning {} on any exception."""
    try:
        return fn(*args, **kwargs) or {}
    except Exception as e:
        print(f"  [warn] {label} failed: {type(e).__name__}: {e}", file=sys.stderr)
        return {}


def compute_all_metrics(cif_path: Path, device: str, peptide_chain: str | None, receptor_chain: str | None) -> dict:
    """Run the full binding-metrics suite on one structure.

    Returns a flat dict of scalar metric values.  List/nested values (e.g.
    per_residue breakdowns) are dropped since they cannot live in a CSV row.
    """
    from binding_metrics import (
        compute_interface_metrics,
        compute_interaction_energy,
        compute_coulomb_cross_chain,
        compute_ramachandran,
        compute_omega_planarity,
        compute_shape_complementarity,
        compute_buried_void_volume,
    )

    path_str = str(cif_path)
    chain_kwargs = {}
    if peptide_chain:
        chain_kwargs["design_chain"] = peptide_chain
    if receptor_chain:
        chain_kwargs["receptor_chain"] = receptor_chain

    row: dict = {}

    # --- Interface metrics (SASA, solvation energy, H-bonds, salt bridges) ---
    m = _safe(compute_interface_metrics, "interface_metrics", path_str, **chain_kwargs)
    for key in [
        "delta_sasa", "delta_g_int", "delta_g_int_kJ",
        "polar_area", "apolar_area", "fraction_polar",
        "hbonds", "saltbridges",
        "n_interface_residues_peptide", "n_interface_residues_receptor",
    ]:
        row[key] = m.get(key)

    # --- Force-field interaction energy (raw mode — structure already relaxed) ---
    m = _safe(
        compute_interaction_energy, "interaction_energy",
        path_str, modes=("raw",), device=device, **chain_kwargs,
    )
    row["raw_interaction_energy"] = m.get("raw_interaction_energy")

    # --- Coulomb electrostatics ---
    m = _safe(compute_coulomb_cross_chain, "coulomb", path_str, **chain_kwargs)
    row["coulomb_energy_kJ"] = m.get("coulomb_energy_kJ")
    row["n_charged_pairs"]   = m.get("n_charged_pairs")

    # --- Backbone geometry ---
    rama_kwargs = {}
    if peptide_chain:
        rama_kwargs["chain"] = peptide_chain
    m = _safe(compute_ramachandran, "ramachandran", path_str, **rama_kwargs)
    row["ramachandran_favoured_pct"] = m.get("ramachandran_favoured_pct")
    row["ramachandran_outlier_pct"]  = m.get("ramachandran_outlier_pct")

    m = _safe(compute_omega_planarity, "omega", path_str, **rama_kwargs)
    row["omega_mean_dev"]        = m.get("omega_mean_dev")
    row["omega_outlier_fraction"] = m.get("omega_outlier_fraction")

    # --- Interface geometry ---
    m = _safe(compute_shape_complementarity, "shape_complementarity", path_str, **chain_kwargs)
    row["sc"]       = m.get("sc")
    row["sc_A_to_B"] = m.get("sc_A_to_B")
    row["sc_B_to_A"] = m.get("sc_B_to_A")

    m = _safe(compute_buried_void_volume, "void_volume", path_str, **chain_kwargs)
    row["void_volume_A3"] = m.get("void_volume_A3")

    return row


# ---------------------------------------------------------------------------
# Per-structure pipeline
# ---------------------------------------------------------------------------

DELTA_KEYS = [
    "delta_sasa", "delta_g_int", "delta_g_int_kJ",
    "hbonds", "saltbridges",
    "raw_interaction_energy", "coulomb_energy_kJ",
    "sc", "void_volume_A3",
]


def process_structure(
    sample_id: str,
    pre_file: Path,
    post_file: Path,
    device: str,
    peptide_chain: str | None,
    receptor_chain: str | None,
) -> dict:
    """Compute pre/post metrics + RMSD comparison for one structure pair."""
    from binding_metrics import compute_structure_rmsd

    print(f"\n[{sample_id}] Pre-relaxation:  {pre_file.name}")
    pre_metrics = compute_all_metrics(pre_file, device, peptide_chain, receptor_chain)

    print(f"[{sample_id}] Post-relaxation: {post_file.name}")
    post_metrics = compute_all_metrics(post_file, device, peptide_chain, receptor_chain)

    # --- RMSD comparison (pre vs post) ---
    print(f"[{sample_id}] RMSD comparison...")
    rmsd_dict = _safe(
        compute_structure_rmsd, "structure_rmsd",
        str(pre_file), str(post_file),
        **({} if not peptide_chain else {"design_chain": peptide_chain}),
    )

    # --- Assemble flat row ---
    row: dict = {"sample_id": sample_id, "success": True, "error_message": None}

    for key, val in pre_metrics.items():
        row[f"pre_{key}"] = val
    for key, val in post_metrics.items():
        row[f"post_{key}"] = val

    # Delta (relaxation-induced change: post − pre)
    for key in DELTA_KEYS:
        pre_val  = pre_metrics.get(key)
        post_val = post_metrics.get(key)
        if pre_val is not None and post_val is not None:
            row[f"delta_{key}"] = post_val - pre_val
        else:
            row[f"delta_{key}"] = None

    # RMSD
    row["rmsd"]        = rmsd_dict.get("rmsd")
    row["bb_rmsd"]     = rmsd_dict.get("bb_rmsd")
    row["rmsd_design"] = rmsd_dict.get("rmsd_design")
    row["bb_rmsd_design"] = rmsd_dict.get("bb_rmsd_design")

    # Source paths (informational)
    row["pre_structure"]  = str(pre_file)
    row["post_structure"] = str(post_file)

    return row


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compute binding metrics for pre/post relaxation pairs.")
    parser.add_argument("--inputs-dir",     type=Path, default=Path("./inputs"))
    parser.add_argument("--outputs-dir",    type=Path, default=Path("./outputs"))
    parser.add_argument("--device",         type=str,  default="cpu")
    parser.add_argument("--peptide-chain",  type=str,  default="")
    parser.add_argument("--receptor-chain", type=str,  default="")
    args = parser.parse_args()

    inputs_dir  = args.inputs_dir
    outputs_dir = args.outputs_dir
    outputs_dir.mkdir(parents=True, exist_ok=True)

    peptide_chain  = args.peptide_chain  or None
    receptor_chain = args.receptor_chain or None

    # --- Find pre/post pairs ---
    pre_files = sorted(inputs_dir.glob("cleaned_*.cif")) + \
                sorted(inputs_dir.glob("cleaned_*.pdb"))

    if not pre_files:
        print("ERROR: no cleaned_*.cif / cleaned_*.pdb files found in inputs/", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(pre_files)} structure(s) to score.")

    rows = []
    for pre_file in pre_files:
        stem = pre_file.stem.removeprefix("cleaned_")   # e.g. "complex"

        # Prefer MD final frame; fall back to minimized
        post_md  = inputs_dir / f"{stem}_md_final.cif"
        post_min = inputs_dir / f"{stem}_minimized.cif"

        if post_md.exists():
            post_file = post_md
        elif post_min.exists():
            post_file = post_min
        else:
            print(f"[{stem}] WARNING: no relaxed structure found, skipping.", file=sys.stderr)
            rows.append({
                "sample_id": stem,
                "success": False,
                "error_message": "No post-relaxation structure found",
            })
            continue

        try:
            row = process_structure(
                stem, pre_file, post_file,
                args.device, peptide_chain, receptor_chain,
            )
        except Exception as e:
            print(f"[{stem}] ERROR: {e}", file=sys.stderr)
            traceback.print_exc()
            rows.append({
                "sample_id": stem,
                "success": False,
                "error_message": f"{type(e).__name__}: {e}",
            })
            continue

        rows.append(row)
        print(f"[{stem}] OK — delta_g_int: pre={row.get('pre_delta_g_int'):.3f}  post={row.get('post_delta_g_int'):.3f}  "
              f"RMSD={row.get('rmsd')}")

    # --- Save outputs ---
    import pandas as pd

    df = pd.DataFrame(rows)

    csv_path  = outputs_dir / "scores.csv"
    json_path = outputs_dir / "scores.json"

    df.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(rows, f, indent=2, default=str)

    n_ok   = int(df["success"].sum()) if "success" in df.columns else len(df)
    n_fail = len(df) - n_ok
    print(f"\nDone. {n_ok} succeeded, {n_fail} failed.")
    print(f"  scores.csv  → {csv_path}")
    print(f"  scores.json → {json_path}")


if __name__ == "__main__":
    main()
