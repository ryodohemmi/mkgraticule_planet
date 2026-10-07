# mkgraticule_planet

Create planetary-scale graticules with multi-format labels for any **GDAL/PROJ-supported CRS** — exported as **GeoPackage**, **SpatiaLite**, or Python-only fitted **3D PLY**.

A small CLI utility for generating latitude/longitude grids for planetary bodies using **IAU 2015 planetary coordinate systems**.

Currently, two CLI implementations are available:

* **Python / GDAL**: [`mkgraticule_planet.py`](https://github.com/ryodohemmi/mkgraticule_planet/blob/main/standalone/mkgraticule_planet.py)
* **R / sf**: [`mkgraticule_planet.R`](https://github.com/ryodohemmi/mkgraticule_planet/blob/main/standalone/mkgraticule_planet.R)

The fitted 3D PLY output for OBJ/mesh shape models is available in the Python implementation only.

## Quick start

```sh
conda install -c conda-forge mkgraticule-planet
mkgraticule -g 10 10 -srs IAU_2015:30100 moon_graticule.gpkg
```

See [Installation](installation.md) and [Usage](usage.md) for details.

## Features

* Supports **IAU 2015 planetary coordinate systems**
    * QGIS-friendly output suitable for map production: label fields allow immediate graticule labeling, and CRS metadata ([`definition_12_063`](https://www.geopackage.org/spec/#gpkg_spatial_ref_sys_cols_crs_wkt)) ensures that IAU coordinate systems are correctly recognized when the GeoPackage is loaded in QGIS (GeoPackage only).
* Generates degree-based latitude/longitude graticules even when the output CRS is a metre-based projected CRS
* GeoPackage and SpatiaLite output
* Python-only fitted 3D PLY output for OBJ/mesh shape models
* Optional metre-based mode `-u/--units meters`: writes a planar easting/northing grid directly in a metre-based projected CRS (no reprojection) — see [Metre-based grids](metre-grids.md)
* Quick View `-q/--qview`: opens a window showing the whole grid right after the file is written — see [Quick View](quick-view.md)
* Compatible with **GDAL 3.x**
* Two CLI implementations for 2D GIS output:
    * Python version for [GDAL](https://github.com/OSGeo/gdal)-centric workflows (conda-forge / standalone)
    * R version for [sf (Simple Features for R)](https://github.com/r-spatial/sf/)-centric workflows (standalone only)
* Multiple graticule label styles
* Optional major/minor classification via `-m/--major` (`grid_type = major|minor`, otherwise NULL)
* Safer handling for projected CRS with limited domains:
    * abort on projected + near-global extent unless `-s/--skipfailures` is used
    * optional `-p/--partial-reprojection` for partial output near projection-domain limits
* Override Lambert Conic Conformal projection parameters via `-lo` (latitude of origin), `-ls` (1st standard parallel), and `-ls2` (2nd standard parallel), allowing customization of the IAU defaults (0°, 20°, 60°)
* Optional endpoint de-duplication for 360° longitude spans: `-nde/--no-duplicate-endpoint`
* Automatic companion point layer (`point`) for projected CRS:
    * collapsed graticule features at projection singularities
    * projection-center label points
* Point-role classification in the companion point layer via `point_role` (`collapsed` / `center`)

Latitude labels:

* `lat_90` → -90° to 90°
* `lat_ns` → 90°S to 90°N

Longitude labels:

* `lon_180` → -180° to 180°
* `lon_ew` → 180°W to 180°E
* `lon_360` → 0° to 360°
* `lon_360e` → 0° to 360°E
* `lon_360w` → 0° to 360°W

## Acknowledgement

This project is based on the GDAL sample script:

<https://github.com/OSGeo/gdal/blob/master/swig/python/gdal-utils/osgeo_utils/samples/mkgraticule.py>

The R implementation was developed as an `sf`-based companion workflow for the same `mkgraticule_planet` concept.

## Citation

If you use this software in your research, please cite:

Hemmi, R. (2026). *mkgraticule_planet*. Zenodo.  
<https://doi.org/10.5281/zenodo.18864189>

## License

Apache-2.0 License. See [LICENSE](https://github.com/ryodohemmi/mkgraticule_planet/blob/main/LICENSE) for details.
