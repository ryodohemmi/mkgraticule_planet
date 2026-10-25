# Development and tests

Create a conda environment with the same dependencies as GitHub Actions:

```sh
conda env create -f tests/environment.yml
conda activate mkgraticule-tests
python -m pip install --no-deps --no-build-isolation -e .
python -m unittest discover -s tests -v
```

The suite runs the package CLI, standalone Python script and standalone R script
against small temporary datasets. It checks GeoPackage/SpatiaLite output,
CRS and labels, major/minor classification, endpoint de-duplication, polar point
layers, metre grids, saved counts, metadata opt-in, dry runs and preservation of
existing output on failure. Python tests also cover partial write/replacement
failures, projection skips, PLY edge/tube output and standalone source parity.
R tests also simulate partial-write and replacement failures to verify that the
original file survives and staging directories are removed.

R tests are skipped if `Rscript` is unavailable. To use R from a different conda
environment, set `MKGRATICULE_R_COMMAND` to a JSON array of command arguments:

```sh
export MKGRATICULE_R_COMMAND='["conda", "run", "--no-capture-output", "-n", "rsf", "Rscript"]'
python -m unittest discover -s tests -v
```

GitHub Actions runs the full suite on Linux on pushes and pull requests, with
Python 3.11 and R in a conda-forge environment. CI requires R tests and sets
`MKGRATICULE_REQUIRE_PLY=1` to fail if PLY dependencies are unavailable, and checks
the installed command entry points. The suite
does not exercise interactive Quick View windows or every OS/GDAL combination.

The Python standalone file must remain byte-identical to
`src/mkgraticule_planet/_cli.py`. Copy the implementation after editing it; the
tests detect divergence.

Before publishing the conda recipe, create the release tag and add the SHA-256 of
its archive to `conda/meta.yaml`. A previous version's checksum must not be reused.
