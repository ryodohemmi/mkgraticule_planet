# Changelog

All notable changes to this project will be documented in this file.

## [1.4.0] - Unreleased

### Changed
- **CLI compatibility change:** `-s` now takes a CRS value and is equivalent to `-srs` and `--srs`. The former `-s` skip-failures flag has moved to `-skipf`; replace old skip-failures uses with `-skipf` or the unchanged `--skipfailures`. Python and R do not guess the meaning from whether a value is supplied.
- **CLI compatibility change:** `-s` / `-srs` / `--srs` is now required for all 2D GeoPackage and SpatiaLite output, including `--dry-run`. The previous implicit Moon CRS (`IAU_2015:30100`) has been removed in Python and R. Existing Moon commands that omitted it must add `-srs IAU_2015:30100`; other bodies must specify their intended CRS. Missing or blank values stop before output creation or replacement. PLY continues to use input mesh coordinates and does not require `-srs`.

## [1.3.2] - 2026-10-25

### Fixed
- Read only the CRS node's own authority identifier in R, so custom PROJ/WKT definitions do not mistake nested unit identifiers such as EPSG:9122 for a geographic CRS.

### Changed
- Expand GitHub Actions coverage to Linux and Windows with Python 3.11, 3.12 and 3.13, retaining required R and PLY integration tests.
- Explicitly document `.wkt` / `.prj` CRS file inputs in both CLIs' `-srs` help and the documentation.

## [1.3.1] - 2026-10-25

### Added
- Implemented `-s/--skipfailures`, `-p/--partial-reprojection` and the near-global limited-domain guard in R.
- Added native R fitted 3D PLY output using optional Rvcg, including edge/tube output, ray origins, offsets, colours, batches, dry runs, metadata and failed-output protection. Python is not required by the R implementation.

### Changed
- Align shared R CLI defaults with Python: degree-mode `-g` now defaults to `5 5`, and `-r` defaults to `0.1 0.1` instead of `0.5 0.1`. Metre-mode defaults remain `5000 5000` / `100 100`. To retain the previous R sampling spacing, pass `-r 0.5 0.1` explicitly.
- Match Python's default output-extension handling when the supplied filename has an unrecognized suffix.
- Lead the README with conda-forge installation and a quick-start example, and link to the detailed Python/R comparison on Read the Docs.
- Document the implemented Python/R features and backend differences, with shared output and option tests.

## [1.3.0] - 2026-10-25

### Added
- Added `--dry-run` to Python and R: validate settings and show the generation plan and approximate 2D output size without writing files, asking for confirmation or opening Quick View. Python PLY validates CLI options and the input mesh path without loading the mesh or ray casting.
- Added opt-in `--metadata`: generation settings, version, UTC time and command arguments are recorded in a `mkgraticule_metadata` key/value table for GeoPackage/SpatiaLite, or header comments for Python PLY. The effective CRS WKT is included for 2D output.
- Added shared Python/R integration tests and GitHub Actions CI, including standalone source parity, output formats, labels, CRS, polar points, dry runs, metadata, PLY and failure protection.
- Added Python/R feature and default-value comparison tables and development documentation.

### Changed
- Generate output in a temporary directory on the destination filesystem and replace existing output only after generation and validation succeed. Existing files are still overwritten automatically; failed generation preserves the previous file.
- Report actual saved 2D feature counts by reading the written output, with separate line/point counts and an explicit empty-line count. Outputs with no non-empty lines are rejected.
- Keep the previous output intact and show an actionable message when replacement is denied (for example, an output open in QGIS). Output-size confirmation happens before creating output directories.
- Use a common plain-text metadata value format in Python and R, select settings by output type, and record actual CRS projection parameters separately from requested overrides.
- Updated the package, standalone scripts, conda recipe and citation metadata to `1.3.0`.

### Fixed
- Fall back to the R display width when terminal width information is unavailable, including non-interactive CI environments.

## [1.2.1] - 2026-10-08

### Changed
- Raised the minimum Python version from 3.9 to 3.11 to follow conda-forge's `python_min` (CFEP-25): `requires-python`, the Python classifiers, the conda recipe and the PLY environment file are updated. The standalone scripts are unchanged apart from their version.
- Updated Python package, standalone Python script, standalone R script, conda recipe, and citation metadata to `1.2.1`.

## [1.2.0] - 2026-10-07

### Added
- Added `-q/--qview` (Quick View): opens a window showing the whole grid right after the output file is written. The Python implementation uses matplotlib, which is an optional dependency (`conda install matplotlib`, or the `quickview` extra when installing from source with `pip install -e .[quickview]`); the R script uses base graphics.
- Added `-u/--units {degrees,meters}` (default `degrees`). With `-u meters`, `-g/-r/-m/-e` are interpreted as projected metres and an easting/northing grid is written directly in the output CRS without reprojection. It requires a projected CRS whose linear unit is the metre and an explicit `-e`. The defaults become `-g 5000 5000` and `-r 100 100`. Output fields are `x`, `y` and `grid_type`.
- Added an output-size check for `-r`: the recommended range is `0.1 <= res <= step/2` degrees (`10 <= res <= step/2` metres with `-u meters`). Below the lower bound, or when the estimated output exceeds 100 MB, a warning with the estimated size is printed and `Continue? [y/N]` is asked; only `y`/`yes` continues and otherwise nothing is written (exit status 1). Values above `step/2` only print a note. When stdin is not a terminal the command stops, and the new `-y/--yes` option continues without asking. PLY output is not checked.
- Added a readthedocs documentation site (MkDocs) built from `docs/`.

### Changed
- Updated Python package, standalone Python script, standalone R script, conda recipe, and citation metadata to `1.2.0`.
- Normalized the line endings of `src/mkgraticule_planet/_cli.py` to LF so it is byte-identical to `standalone/mkgraticule_planet.py`.

### Notes
- `-q` and `-u meters` are not available for PLY output.

## [1.1.1] - 2026-05-26

### Changed
- Added shorter PLY command-line aliases and updated README examples to use them.
- Kept the previous PLY option names as compatibility aliases.
- Made absolute and fractional PLY offsets mutually exclusive.
- Report unknown option-looking tokens before argparse can reinterpret short-option typos.
- Updated Python package and standalone script versions to `1.1.1`.

## [1.1.0] - 2026-05-26

### Added
- Added Python-only fitted 3D PLY output for OBJ/mesh shape models.
- Added PLY-specific CLI options for mesh input, ray origin, offsets, colors, and tube meshes.
- Added a conda environment file for Python PLY workflows.
- Documented why Shapefile and GeoJSON are not direct output formats.

### Changed
- Updated Python package and standalone Python script version to `1.1.0`.
- Added `trimesh` and `rtree` as packaged Python dependencies; Embree via `embreex` or `pyembree` is documented as the recommended fast path.
- Added a fail-fast guard for large PLY ray-casting jobs when Embree is unavailable.

### Notes
- The R standalone script remains a 2D GeoPackage/SpatiaLite implementation; fitted 3D PLY output is Python-only.

## [1.0.1] - 2026-05-13

### Added
- Added `mkgraticule` as the preferred installed CLI command.

### Changed
- Kept `mkgraticule_planet` available as a compatibility alias.

## [0.4.0] - 2026-03-27
### Added
- Added an R implementation of `mkgraticule_planet` alongside the existing Python script.

### Changed
- Changed the project license from MIT to Apache-2.0.

### Notes
- For changes prior to `v0.4.0`, see the GitHub Releases page.
