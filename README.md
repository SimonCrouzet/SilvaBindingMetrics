# SilvaBindingMetrics

A modular, physics-based scoring pipeline for peptide–protein complexes, built as a
[Silva](https://github.com/chiral-data/silva) workflow. All metrics are computed by the
[binding-metrics](https://github.com/SimonCrouzet/BindingMetrics) package (included as a
git submodule).

Submitted to the **Chiral Peptide Blueprint Build Challenge 2026** by Simon Crouzet
(independent computational biologist, Lausanne).

---

## When to use this

Structure prediction and design tools (AlphaFold3, RFdiffusion, ProteinMPNN) can generate
tens to hundreds of candidate peptide–protein complexes. This pipeline helps you **rank and
filter them** by computing physics-based binding quality metrics on each candidate — so you
know which ones are worth progressing before committing to expensive wet-lab work.

Run it in **batch mode** (the default) to score an entire library in one shot: drop your CIF
files into `01-structure-prep/input_files/` and get a single HTML scorecard comparing all
candidates side-by-side. Or use single mode to inspect one complex in detail.

The HTML scorecard uses RAG indicators to flag each metric. A strong candidate typically
shows a large negative ΔG_int (< −10 kcal/mol), high shape complementarity (Sc > 0.6),
low relaxation RMSD (< 1 Å), and > 90% Ramachandran-favoured backbone. Candidates failing
multiple indicators can be deprioritised before wet-lab validation.

---

## What it does

Given one or more peptide–protein complexes (PDB or CIF), the pipeline:

1. **Cleans and protonates** the structure (`binding-metrics-prep`)
2. **Relaxes** it with implicit-solvent MD (`binding-metrics-relax`, AMBER ff14SB + OBC2)
3. **Computes a full suite of physics-based binding metrics** on the relaxed structure:
   interaction energy, interface geometry, backbone quality, electrostatics, and pre/post RMSD
4. **Generates an HTML report** (CSV + scorecard with RAG indicators) comparing all scored
   structures via `binding-metrics-report`

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
│  at given pH                │  → complex_prep.log
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
│  CSV export + HTML report    │  → complex_results.csv
│  (RAG scorecard)            │  → complex_report.html
└─────────────────────────────┘
```

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) (running)
- [Silva](https://github.com/chiral-data/silva) installed
- Internet access for the first run (pulls `simoncrouzet/binding-metrics:latest` from Docker Hub)
- A CUDA-capable GPU + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/) **required** for MD relaxation (node 02) and metrics (node 03)

> **GPU setup:** Silva passes `use_gpu = true` to Docker, but requires the NVIDIA runtime to be set as Docker's default. Run once after installing the NVIDIA Container Toolkit:
> ```bash
> sudo nvidia-ctk runtime configure --runtime=docker --set-as-default
> sudo systemctl restart docker
> ```
> Verify with:
> ```bash
> docker run --rm --gpus all simoncrouzet/binding-metrics:latest binding-metrics-check-env
> ```
> Only the OpenMM check matters here — OpenFold3 is not used by this pipeline and its absence is expected.

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
| `example_linearpeptide_1YCR.cif` | Linear peptide (PDB: 1YCR) |
| `example_cyclicpeptide_3P8F.cif` | Cyclic peptide (PDB: 3P8F) |

The default configuration runs in **batch mode**, processing both examples in a single
execution and producing a side-by-side HTML scorecard — a linear peptide and a cyclic
peptide scored together.

Launch Silva, select `peptide-binding-metrics`, and run — no changes needed:

```bash
/path/to/silva/target/release/silva
```

```
Select workflow → peptide-binding-metrics → Run
```

### 4. Use your own structures

**Batch mode (default):** drop one or more CIF/PDB files into
`01-structure-prep/input_files/` alongside the examples and re-run. All structures in
the folder are scored together.

**Single mode:** set `BATCH_MODE = false` in the TUI or in `global_params.json`,
then point `INPUT_COMPLEX` at the file you want:

```json
{
  "BATCH_MODE": "false",
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
| `BATCH_MODE` | `true` | `true` = process all CIF/PDB in `INPUT_DIR` (default); `false` = single file via `INPUT_COMPLEX` |
| `PH` | `7.4` | pH for hydrogen addition during structure preparation |
| `PEPTIDE_CHAIN` | `""` | Peptide chain ID (empty = auto-detect smallest chain) |
| `RECEPTOR_CHAIN` | `""` | Receptor chain ID (empty = auto-detect by Cα contacts) |
| `MD_DURATION_PS` | `200.0` | MD duration in picoseconds (`0` = minimisation only) |
| `SOLVENT_MODEL` | `obc2` | Implicit solvent model: `obc2` or `gbn2` |
| `DEVICE` | `cuda` | OpenMM compute device: `cuda` or `cpu` |

### GPU acceleration

All nodes use `DEVICE=cuda` by default. If no NVIDIA GPU is available, override to `cpu`
in the TUI or in `global_params.json`. Note that MD and force-field energy steps are
**orders of magnitude slower on CPU**.

---

## Output files

Silva runs each node in a timestamped temp directory and collects outputs there. After a
run, all outputs are accessible under:

```
/tmp/silva-<timestamp>/
├── 01-structure-prep/outputs/
│   ├── cleaned_*.cif           ← protonated, cleaned structure
│   └── *_prep.log
├── 02-md-relaxation/outputs/
│   ├── cleaned_*.cif           ← pass-through for RMSD reference
│   ├── *_minimized.cif         ← energy-minimised structure
│   ├── *_md_final.cif          ← final MD snapshot
│   └── *_relax.log
├── 03-compute-metrics/outputs/
│   ├── *_results.json          ← full structured metrics per structure
│   └── metrics.log
└── 04-report/outputs/
    ├── *_results.json          ← copy of metrics JSON
    ├── *_results.csv           ← flat CSV row per structure
    ├── *_report.html           ← self-contained HTML scorecard (RAG indicators)
    └── *_report.log
```

Find the latest run's temp dir with:

```bash
ls -td /tmp/silva-* | head -1
```

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

The HTML report produced by node 04 (`*_report.html`) includes a **cyclic topology
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
