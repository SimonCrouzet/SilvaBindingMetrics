FROM condaforge/miniforge3:latest

# Heavy scientific deps — binary builds from conda-forge, GPU-compatible
RUN conda install -c conda-forge -y \
    "openmm>=8.0" \
    "pdbfixer>=1.9" \
    "mdtraj>=1.9" \
    "biotite>=0.41" \
    hydride \
    "gemmi>=0.6" \
    "scipy>=1.10" \
    numpy \
    && conda clean -afy

# binding-metrics — install package only, conda already provides all heavy deps
RUN pip install --no-cache-dir \
    "git+https://github.com/SimonCrouzet/BindingMetrics.git[all]" \
    --no-deps
