# mkgraticule_planet

Create planetary graticules for **IAU coordinate systems** and export them as **GeoPackage**.

A small CLI utility for generating latitude/longitude grids for planetary bodies using **IAU 2015 planetary coordinate systems**.

## Features

* Supports **IAU 2015 planetary coordinate systems**
* GeoPackage output
* Compatible with **GDAL 3.x**
* Multiple graticule label styles
* QGIS-friendly output suitable for map production: label fields allow immediate graticule labeling, and CRS metadata (`definition_12_063`) ensures that IAU coordinate systems are correctly recognized when the GeoPackage is loaded.

Latitude labels:

* `lat_180` → -90° to 90°
* `lat_ns` → 90°S to 90°N

Longitude labels:

* `lon_180` → -180° to 180°
* `lon_ew` → 180°W to 180°E
* `lon_360` → 0° to 360°

## Requirements

Python with GDAL Python bindings.

Example installation (conda):

```sh
conda install gdal
```

## Usage

Basic example:

```sh
# Moon
python mkgraticule_planet.py \
  -g 10 10 \
  -r 0.2 0.2 \
  -srs IAU_2015:30100 \
  -e -180 90 180 -90 \
  moon_graticule.gpkg
```

## Planetary CRS

The `-srs` option accepts any coordinate reference system supported by GDAL / PROJ.

Planetary coordinate systems typically follow the IAU 2015 definitions.
Many IAU CRS codes can be browsed at:

https://spatialreference.org/

Example codes:

- `IAU_2015:30100` — Moon
- `IAU_2015:49900` — Mars
- `IAU_2015:40100` — Phobos

## Output fields

| Field   | Description                     |
| ------- | ------------------------------- |
| lat     | latitude value                  |
| lon     | longitude value                 |
| lat_180 | latitude label (-90° … 90°)     |
| lat_ns  | latitude label (90°S … 90°N)    |
| lon_180 | longitude label (-180° … 180°)  |
| lon_ew  | longitude label (180°W … 180°E) |
| lon_360 | longitude label (0° … 360°)     |

## Acknowledgement

This project is based on the GDAL sample script:

https://github.com/OSGeo/gdal/blob/master/swig/python/gdal-utils/osgeo_utils/samples/mkgraticule.py

## License

MIT License. See the LICENSE file for details.
