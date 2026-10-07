# Design notes

## Degree-based graticules in projected CRSs

Unlike QGIS's built-in [**Vector creation - Create grid (Vector > Research Tools > Create Grid)**](https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/qgis/vectorcreation.html#create-grid), which defines grid spacing in the map units of the output CRS, `mkgraticule_planet` defines meridians and parallels in degrees in geographic coordinates and then reprojects them. It can therefore create a true degree-based latitude/longitude graticule directly in a metre-based projected CRS, in addition to supporting IAU 2015 planetary coordinate systems. (When a planar metre-based grid is what you want, `-u meters` provides one; see [Metre-based grids](../metre-grids.md).)

This distinction matters because QGIS's on-the-fly reprojection affects how layers are rendered in a project, but does not rewrite their stored coordinates. When a vector layer is imported into a database such as a GeoPackage, QGIS uses the source layer's CRS as the default output CRS rather than adopting the CRS of other layers already stored in the destination. A degree-based graticule may therefore appear correctly over metre-based projected data in the QGIS map canvas while remaining stored in angular coordinates, unless it is explicitly reprojected during export or import. `mkgraticule_planet` avoids this extra and potentially error-prone step by defining the graticule spacing in degrees and writing its geometries already transformed into the requested projected CRS. See the QGIS documentation on [on-the-fly reprojection](https://docs.qgis.org/latest/en/docs/training_manual/vector_analysis/reproject_transform.html) and [database layer imports](https://docs.qgis.org/latest/en/docs/user_manual/introduction/browser.html#importing-a-vector-layer).

## Comparison with QGIS and sf

For the rationale behind the graticule-generation workflow and a comparison with QGIS-native projected-grid tools and `sf::st_graticule()`, see [Comparison with QGIS and sf](comparison-with-qgis-and-sf.md).

## QGIS 4.x compatibility

GeoPackage output from `mkgraticule_planet` has been tested for normal operation through QGIS 3.44. The files are expected to remain readable in [QGIS 4.0](https://changelog.qgis.org/en/version/4.0/) and later, but they have not yet been fully validated with these releases. QGIS 4.0 was released on 6 March 2026.

## Planetary CRS caveats in QGIS 4.x

Planetary users should take particular care with CRS transformations and distance-related workflows in QGIS 4.x. The public QGIS issue tracker documents [clipping and graticule/grid failures during reprojection between lunar IAU CRSs](https://github.com/qgis/QGIS/issues/63048). Recent merged QGIS changes also explicitly address [hard-coded WGS 84 assumptions in non-Earth projects](https://github.com/qgis/QGIS/pull/65000), [invalid distance and area results for spherical planetary bodies](https://github.com/qgis/QGIS/pull/66467), and [spurious attempts to transform non-Earth CRSs to EPSG:4326](https://github.com/qgis/QGIS/pull/66468). Accordingly, use a metre-based projected map CRS whenever possible and verify reprojection results. The QGIS documentation distinguishes [ellipsoidal measurements from Cartesian (planimetric) measurements](https://docs.qgis.org/latest/en/docs/user_manual/map_views/map_view.html#measuring) and notes that some measurement workflows do not transform data to the project CRS before measuring. When the map view uses a geographic CRS in degrees, prefer ellipsoidal measurements and keep **Planimetric measurements** disabled; use Cartesian measurements only with a suitable projected CRS.
