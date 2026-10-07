# Projected CRS and planetary CRS

## Projected CRS considerations

Some projected coordinate systems (e.g., polar stereographic) have **limited valid domains**.
If a near-global geographic extent is requested, reprojection may fail.

- Default behavior: **abort** with a message suggesting to restrict the extent with `-e`
- Recommended approach: restrict the geographic extent to the valid projection domain (e.g., `-e -180 -60 180 -90` for south polar views)
- To force output anyway (skip features that fail reprojection): `-s/--skipfailures`
- Optionally enable partial reprojection: `-p/--partial-reprojection`

For projected + near-global requests, restricting the extent with `-e` is usually the best solution.  
Combining `-s` with `-p` can sometimes produce partial output near projection domain limits.

For projections with a singular center, the tool also writes a companion point layer (`point`).  
This layer can contain:

- `collapsed` points for graticule features that collapse to a single point in the projected CRS
- `center` points for projection-center label points

This makes it possible to label features such as `90°S`, `90°N`, or a projection-center graticule label in QGIS even when the corresponding line geometry is not visible.

!!! info
    These domain limits do not apply to [`-u meters`](metre-grids.md), which writes lines directly in the projected CRS without reprojection.

### Dateline handling

If the longitude span is approximately **360°** (e.g. `-180..180` or `0..360`), duplicate endpoint meridians can be generated.

To drop the duplicate endpoint meridian while keeping the minimum longitude endpoint:

- `-180..180` → keep `-180`, drop `180`
- `0..360` → keep `0`, drop `360`

```sh
mkgraticule ... -nde
```

## Planetary CRS

The `-srs` option accepts any coordinate reference system supported by GDAL / PROJ.

Planetary coordinate systems typically follow the **IAU 2015 cartographic coordinate system definitions**.
Many IAU CRS definitions can be browsed at <https://spatialreference.org/>.

Example codes:

- `IAU_2015:30100` — Moon
- `IAU_2015:49900` — Mars
- `IAU_2015:40100` — Phobos
