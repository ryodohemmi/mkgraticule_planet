# Installation

## Python implementation

### Option 1: conda install (recommended)

```sh
conda install -c conda-forge mkgraticule-planet
```

Or install directly into a new dedicated environment:

```sh
conda create -y -n myenv mkgraticule-planet -c conda-forge
conda activate myenv
```

With conda 4.4 or newer (Dec 2017), the shorter `channel::package` form is also valid:

```sh
conda create -y -n myenv conda-forge::mkgraticule-planet
conda activate myenv
```

!!! note
    GDAL does not provide pre-built wheels on PyPI, so `pip install` cannot resolve the GDAL dependency reliably. Installing via conda is recommended.

For Python PLY output, `pip install embreex` in the same conda environment is recommended; the conda package includes the `trimesh`/`rtree` fallback but not Embree acceleration.

For [Quick View](quick-view.md) (`-q/--qview`) with the Python implementation, install matplotlib in the same environment (it is an optional dependency and is not installed with the conda package):

```sh
conda install -c conda-forge matplotlib
```

### Option 2: Use standalone scripts directly

The [`standalone/`](https://github.com/ryodohemmi/mkgraticule_planet/tree/main/standalone) directory contains self-contained single-file scripts for both Python and R. No package installation is required beyond the runtime libraries -- just download or clone and run.

These work in any environment where GDAL (Python) or sf (R) is already available:

- **Your existing conda environment** with `gdal` (Python), plus `trimesh rtree` and an Embree binding for Python PLY output, or `r-base r-sf r-rsqlite r-dbi` (R)
- **OSGeo4W Shell** bundled with QGIS (GDAL is pre-installed)
- Any other setup with the required libraries

```sh
# Clone and run
git clone https://github.com/ryodohemmi/mkgraticule_planet.git
python standalone/mkgraticule_planet.py --help
Rscript standalone/mkgraticule_planet.R --help
```

Or download a single file directly:

```sh
# Python
curl -O https://raw.githubusercontent.com/ryodohemmi/mkgraticule_planet/main/standalone/mkgraticule_planet.py
python mkgraticule_planet.py --help

# R
curl -O https://raw.githubusercontent.com/ryodohemmi/mkgraticule_planet/main/standalone/mkgraticule_planet.R
Rscript mkgraticule_planet.R --help
```

If you need to set up a fresh conda environment:

```sh
# Python
conda create -n myenv -c conda-forge gdal trimesh rtree
conda activate myenv

# R
conda create -n rsf -c conda-forge r-base r-sf r-rsqlite r-dbi
conda activate rsf
```

An equivalent environment file for Python PLY workflows is available at [`docs/setup/phobos-latlon-grid.yml`](https://github.com/ryodohemmi/mkgraticule_planet/blob/main/docs/setup/phobos-latlon-grid.yml):

```sh
conda env create -f docs/setup/phobos-latlon-grid.yml
conda activate phobos-latlon-grid
```

Embree acceleration is strongly recommended for shape-model PLY output. The `trimesh`/`rtree` fallback is useful for small jobs, but can require very large temporary arrays on irregular meshes. As of May 2026, `pip install embreex` is the recommended Embree path for current Python versions.

```sh
pip install embreex
```

`pyembree` is also available from conda-forge, but its package builds may lag behind current Python versions:

```sh
conda install -c conda-forge pyembree
```

### Option 3: Install from source (for development)

```sh
git clone https://github.com/ryodohemmi/mkgraticule_planet.git
cd mkgraticule_planet
conda create -n myenv -c conda-forge gdal trimesh rtree
conda activate myenv
pip install -e .
```

For a compact summary of conda download size and post-install environment size for both implementations, see [Conda environment size](setup/conda-env-size-summary-2026-03-17.md).
