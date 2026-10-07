# Why Shapefile and GeoJSON export are not supported

`mkgraticule_planet` does not support direct Shapefile or GeoJSON export by design.

Shapefile is still widely supported, but it is an old multi-file format with strict field-name limits, fragile character encoding behavior, file-size constraints, and weak self-contained metadata handling. These issues are especially undesirable for planetary GIS data, where the coordinate reference system should be preserved clearly and unambiguously. If Shapefile output is required for legacy software, export a GeoPackage first and convert it with GDAL/OGR:

For background on Shapefile limitations, see [Switch from Shapefile](http://switchfromshapefile.org/).

```sh
ogr2ogr -f "ESRI Shapefile" output_shapefile input.gpkg
```

That conversion may lose or degrade metadata, field names, encoding information, or CRS handling depending on the target software.

GeoJSON is also not supported as a primary output format because RFC 7946 GeoJSON is defined for geographic coordinates in WGS 84 / CRS84, and support for alternative coordinate reference systems was removed from the specification. That is a poor fit for planetary coordinate systems based on IAU definitions: writing Mars, Moon, or other planetary coordinates as ordinary GeoJSON could incorrectly imply Earth-based WGS 84 coordinates, or produce non-standard GeoJSON that different software may interpret inconsistently.

For this reason, the 2D GIS outputs focus on formats that preserve CRS information more explicitly: GeoPackage (`.gpkg`) for most users and SpatiaLite (`.sqlite`) for SQLite-based spatial workflows.
