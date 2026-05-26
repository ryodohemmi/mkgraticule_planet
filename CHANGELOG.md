# Changelog

All notable changes to this project will be documented in this file.

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
