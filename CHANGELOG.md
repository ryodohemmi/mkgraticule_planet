# Changelog

All notable changes to this project will be documented in this file.

## [1.2.0] - 2026-10-07

### Added
- Added `-q/--qview` (Quick View): opens a window showing the whole grid right after the output file is written. The Python implementation uses matplotlib, which is an optional dependency (`pip install mkgraticule_planet[quickview]` or `conda install matplotlib`); the R script uses base graphics.
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
