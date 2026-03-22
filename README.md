# SilvaBindingMetrics

A modular, physics-based scoring pipeline for peptide–protein complexes, built as a
[Silva](https://github.com/chiral-data/silva) workflow. All metrics are computed by the
[binding-metrics](https://github.com/SimonCrouzet/BindingMetrics) package (included as a
git submodule).

Submitted to the **Chiral Peptide Blueprint Build Challenge 2026** by Simon Crouzet
(independent computational biologist, Lausanne).

---

## What it does

Given a peptide–protein complex (PDB or CIF), the pipeline:

1. **Cleans and protonates** the structure (`binding-metrics-prep`)
2. **Relaxes** it with implicit-solvent MD (`binding-metrics-relax`, AMBER ff14SB + OBC2)
3. **Computes a full suite of physics-based binding metrics** on the relaxed structure:
   interaction energy, interface geometry, backbone quality, electrostatics, and pre/post RMSD
4. **Generates a per-structure report** (CSV + Markdown scorecard) via `binding-metrics-report`

Cyclic peptides and non-linear scaffolds are supported natively — topology is auto-detected
by the relaxation protocol.

---

## Scientific background

### Why physics-based metrics?

Structure prediction and design tools (AlphaFold3, RFdiffusion, ProteinMPNN, etc.) produce
many candidate complexes. Selecting the most promising ones requires more than confidence
scores — you need to evaluate the actual physical quality of the predicted interface.

This pipeline computes metrics that are directly interpretable in terms of binding physics:

| Metric | What it measures | Why it matters |
|--------|-----------------|----------------|
| **ΔG_int** (kcal/mol) | Solvation free energy gain upon binding (Eisenberg–McLachlan) | Proxy for binding affinity |
| **Buried SASA** (Å²) | Solvent-accessible surface area lost upon complex formation | Larger interface = stronger binding tendency |
| **Interaction energy** (kJ/mol) | AMBER ff14SB intermolecular energy in implicit solvent | Direct MM energy of the bound state |
| **Coulomb energy** (kJ/mol) | Pairwise electrostatic interaction across chains | Charge complementarity |
| **H-bonds** | Count of cross-chain hydrogen bonds | Key contributors to specificity |
| **Salt bridges** | Count of cross-chain salt bridges | Electrostatic anchors |
| **Shape complementarity (Sc)** | Surface dot-product similarity at the interface (0–1) | Geometric fit quality |
| **Buried void volume** (Å³) | Unfilled space at the interface | Packing efficiency |
| **Ramachandran favoured %** | Backbone dihedral quality of the peptide | Structural validity |
| **Omega deviation** | Peptide bond planarity | Covalent geometry quality |
| **Pre/post RMSD** (Å) | Structural drift during relaxation | Stability of the design |

### Why implicit-solvent MD relaxation?

Predicted or designed complexes often have minor clashes or suboptimal side-chain
rotamers. A short implicit-solvent minimisation (AMBER ff14SB + OBC2) resolves these
artefacts without the cost of explicit-solvent simulation, making the pipeline fast enough
for screening. The multi-stage minimisation protocol (global → backbone-restrained →
unrestrained) prevents over-relaxation.

---

## Pipeline overview

```
01-structure-prep/input_files/
    └── your_complex.cif
           │
           ▼
┌─────────────────────────────┐
│  01-structure-prep          │  binding-metrics-prep
│  Fix missing atoms, add H   │  → cleaned_complex.cif
│  at given pH                │  → prep_summary_complex.json
└─────────────────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  02-md-relaxation           │  binding-metrics-relax
│  Multi-stage minimisation   │  → cleaned_complex.cif (pass-through)
│  + optional short MD        │  → complex_minimized.cif
│  AMBER ff14SB + OBC2        │  → complex_md_final.cif
│  Cyclic topology auto-det.  │
└─────────────────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  03-compute-metrics         │  binding-metrics Python API
│  Full metric suite on the   │  → complex_results.json
│  relaxed structure + RMSD   │
│  vs pre-relaxation          │
└─────────────────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  04-report                  │  binding-metrics-report
│  CSV export + Markdown       │  → complex_results.csv
│  scorecard (RAG indicators) │  → complex_report.md
└─────────────────────────────┘
```

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) (running)
- [Silva](https://github.com/chiral-data/silva) installed
- Internet access for the first run (pulls `simoncrouzet/binding-metrics:latest` from Docker Hub)
- A CUDA-capable GPU + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/) recommended for MD and energy steps

---

## Quick start

### 1. Clone

```bash
git clone --recurse-submodules https://github.com/SimonCrouzet/SilvaBindingMetrics.git
cd SilvaBindingMetrics
```

If you cloned without `--recurse-submodules`:
```bash
git submodule update --init
```

### 2. Set the Silva workflow home

```bash
export SILVA_WORKFLOW_HOME=/path/to/parent/of/SilvaBindingMetrics
```

Add to `~/.bashrc` or `~/.zshrc` to make it permanent.

### 3. Run with the bundled examples

Two example complexes are included in `01-structure-prep/input_files/`:

| File | Description |
|------|-------------|
| `example_linearpeptide_1YCR.cif` | Linear peptide (PDB: 1YCR) — **default** |
| `example_cyclicpeptide_3P8F.cif` | Cyclic peptide (PDB: 3P8F) |

Launch Silva and select `peptide-binding-metrics`:

```bash
/path/to/silva/target/release/silva
```

**Run 1 — linear peptide** (default `INPUT_COMPLEX`, no changes needed):
```
Select workflow → peptide-binding-metrics → Run
```

**Run 2 — cyclic peptide** (change one parameter in the TUI before launching):
```
Select workflow → peptide-binding-metrics
  → set INPUT_COMPLEX = example_cyclicpeptide_3P8F.cif
  → Run
```

### 4. Use your own structure

Copy your PDB or CIF into `01-structure-prep/input_files/`, then in the TUI set:
```
INPUT_COMPLEX = my_complex.cif
```

Or edit `global_params.json` directly:
```json
{
  "INPUT_COMPLEX": "my_complex.cif"
}
```

---

## Configuration

All parameters can be set in `global_params.json` at the workflow root, or overridden
per-job in the TUI before launching.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `INPUT_DIR` | `input_files` | Subfolder inside `01-structure-prep/` containing input structures |
| `INPUT_COMPLEX` | `example_linearpeptide_1YCR.cif` | Input filename (single mode) |
| `BATCH_MODE` | `false` | `true` = process all CIF/PDB in `INPUT_DIR` |
| `PH` | `7.4` | pH for hydrogen addition during structure preparation |
| `PEPTIDE_CHAIN` | `""` | Peptide chain ID (empty = auto-detect smallest chain) |
| `RECEPTOR_CHAIN` | `""` | Receptor chain ID (empty = auto-detect by Cα contacts) |
| `MD_DURATION_PS` | `200.0` | MD duration in picoseconds (`0` = minimisation only) |
| `SOLVENT_MODEL` | `obc2` | Implicit solvent model: `obc2` or `gbn2` |
| `DEVICE` | `cuda` | OpenMM compute device: `cuda` or `cpu` |
| `REPORT_SUMMARY` | `true` | Write a Markdown scorecard (`*_report.md`) alongside the CSV |

### GPU acceleration

All nodes use `DEVICE=cuda` by default. If no NVIDIA GPU is available, override to `cpu`
in the TUI or in `global_params.json`. Note that MD and force-field energy steps are
**orders of magnitude slower on CPU**.

---

## Output files

Final outputs land in `04-report/outputs/` (one set per structure):

| File | Description |
|------|-------------|
| `{stem}_results.csv` | All metrics as a flat CSV row |
| `{stem}_report.md` | Human-readable Markdown scorecard with RAG indicators (🟢/🟡/🔴) |

Intermediate outputs are preserved in each node's `outputs/` folder:

| Node | Key outputs |
|------|-------------|
| `01-structure-prep/outputs/` | `cleaned_*.cif`, `prep_summary_*.json` |
| `02-md-relaxation/outputs/` | `cleaned_*.cif` (pass-through), `*_minimized.cif`, `*_md_final.cif` |
| `03-compute-metrics/outputs/` | `*_results.json` (full structured results per structure) |

---

## Repository structure

```
SilvaBindingMetrics/
├── binding-metrics/              ← git submodule (SimonCrouzet/BindingMetrics)
├── .chiral/
│   └── workflow.toml             ← workflow metadata and job dependency chain
├── global_params.json            ← runtime parameter values (edit before running)
├── 01-structure-prep/
│   ├── .chiral/job.toml
│   ├── run.sh
│   └── input_files/
│       ├── example_linearpeptide_1YCR.cif
│       └── example_cyclicpeptide_3P8F.cif
├── 02-md-relaxation/
│   ├── .chiral/job.toml
│   └── run.sh
├── 03-compute-metrics/
│   ├── .chiral/job.toml
│   ├── run.sh
│   └── compute_metrics.py
└── 04-report/
    ├── .chiral/job.toml
    └── run.sh
```

---

## Docker image

All nodes share a single pre-built image: `simoncrouzet/binding-metrics:latest`

It is built from the `binding-metrics` submodule Dockerfile and published to Docker Hub
automatically on every push to `main`. It includes GPU-ready OpenMM (CUDA 12.2), all
conda-forge dependencies, and the full `binding-metrics[all]` install.

Pull it manually if needed:
```bash
docker pull simoncrouzet/binding-metrics:latest
```

> **Note — submodule vs image:** The `binding-metrics/` submodule is pinned to a specific
> commit (used as a code reference and for local development). The Docker image tracks the
> `main` branch independently via GitHub Actions and may be ahead of the pinned submodule.
> The image is what actually runs in the pipeline — ensure it is up to date with
> `docker pull simoncrouzet/binding-metrics:latest` before running.

---

## Cyclic peptide support

Cyclic peptide topology (head-to-tail and side-chain cyclisations) is **auto-detected** by
`binding-metrics-relax` — no flag or parameter is needed. The relaxation protocol patches
the cyclic closure bonds before building the OpenMM system, applies a dedicated warmup
stage to resolve closure geometry, and handles `addHydrogens` correctly for the termini
involved in the ring.

The Markdown scorecard produced by node 04 (`*_report.md`) includes a **cyclic topology
section** when a cyclic peptide is detected, listing the closure bond type(s) and residues
involved.

The bundled example `example_cyclicpeptide_3P8F.cif` (PDB: 3P8F) demonstrates this
end-to-end.

---

## binding-metrics

All computation is delegated to the
[binding-metrics](https://github.com/SimonCrouzet/BindingMetrics) package (Apache 2.0),
an open-source Python library for evaluating biologics binding through physics-based metrics.

CLIs used directly:

| CLI | Node | Purpose |
|-----|------|---------|
| `binding-metrics-prep` | 01 | Structure cleaning and protonation |
| `binding-metrics-relax` | 02 | Implicit-solvent energy minimisation + MD |
| `binding-metrics-report` | 04 | CSV export and Markdown scorecard |

Python API called in node 03 (`compute_metrics.py`):

| Function | Metric group |
|----------|-------------|
| `compute_interaction_energy` | AMBER ff14SB force-field interaction energy |
| `compute_interface_metrics` | Buried SASA, ΔG_int, H-bonds, salt bridges |
| `compute_ramachandran` | Backbone dihedral quality |
| `compute_omega_planarity` | Peptide bond planarity |
| `compute_shape_complementarity` | Interface geometric fit (Sc score) |
| `compute_buried_void_volume` | Interface packing efficiency |
| `compute_coulomb_cross_chain` | Pairwise Coulomb electrostatics |
| `compute_structure_rmsd` | Pre/post relaxation structural comparison |

---

## Licence

This workflow is released under the **Apache License 2.0**. The `binding-metrics` submodule
is also Apache 2.0 licensed. See `LICENSE` for details.
