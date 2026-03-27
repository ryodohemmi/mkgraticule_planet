## Advantages over QGIS-native projected-grid tools

- **Graticule semantics preserved in angular space**  
  QGIS-native tools such as **Create Grid** construct features from an extent and spacing expressed in the coordinates and units of the output CRS. In projected CRSs, this makes them planar grid generators rather than true latitude/longitude graticule generators. `mkgraticule_planet` defines meridians and parallels in geographic coordinates first and only then reprojects them for output.

- **No closed polygon artefacts in polar line output**  
  In polar and other singular projections, projected-grid workflows can collapse meridians into closed geometries at the pole. `mkgraticule_planet` always writes the graticule itself as line features; pole-collapsed cases are emitted to a companion point layer instead of being promoted to polygonal geometry.

- **No degree-to-projected-unit workflow mismatch**  
  Because the graticule is defined in angular space before reprojection, the output preserves the intended cartographic meaning of “this is a meridian/parallel at a specified degree value,” rather than approximating that intent from metre-based grid spacing in the target CRS.

- **Deterministic, scriptable, non-interactive**  
  `mkgraticule_planet` runs as a headless CLI in a GDAL Python environment, without introducing a QGIS Processing runtime into the workflow.

## Advantages over `sf::st_graticule() + st_write(..., ".gpkg")`

- **No extra R runtime or package stack**  
  An `sf::st_graticule()` workflow requires an R installation and an additional application-layer spatial stack on top of GDAL/GEOS/PROJ. `mkgraticule_planet` stays within a single GDAL-based Python toolchain.

- **Less backend ambiguity for planetary CRS handling**  
  In an `sf` workflow, CRS parsing and transformation are delegated to the GDAL/PROJ stack linked into the local R environment. For planetary cartography, this makes behaviour more environment-dependent. `mkgraticule_planet` keeps CRS handling inside a dedicated GDAL-based CLI workflow and can persist the resolved CRS definition directly into the GeoPackage metadata.

- **Richer per-feature label fields**  
  `sf::st_graticule()` returns a single `label` field together with basic metadata. `mkgraticule_planet` writes all supported notation variants (`lat_90`, `lat_ns`, `lon_180`, `lon_ew`, `lon_360`, `lon_360e`) as concurrent attributes on the same feature, so cartographic labelling conventions can be switched in QGIS without regenerating the layer.

- **Major/minor classification in a single pass**  
  Producing a two-tier graticule with `sf::st_graticule()` typically requires multiple calls and a merge step. `mkgraticule_planet` emits a `grid_type` field (`major` / `minor`) in one run, ready for rule-based symbology and labelling.

- **Native 0°–360° longitude-domain workflows**  
  `mkgraticule_planet` is designed for planetary bodies where 0°–360° longitude notation is a first-class requirement, and provides explicit duplicate-endpoint suppression (`-nde`) for wraparound-safe output.

- **Purpose-built GeoPackage output for cartography**  
  The output is not just geometry serialized to GPKG; it is a cartography-ready GeoPackage layer with line identity, notation variants, and hierarchy encoded as feature attributes from the start.