# Metre-based grids (`-u meters`)

By default, `-g`, `-r`, `-m` and `-e` are in degrees. With `-u meters` (default: `-u degrees`) they are interpreted as metres in the projected output CRS, and an easting/northing grid is written directly in that CRS, without reprojection. This is a planar grid similar to QGIS's Create Grid, not a degree-based graticule.

!!! tip "Which mode do I need?"
    Use the default (degrees) when the lines should be meridians and parallels at given degree values, even in a projected CRS. Use `-u meters` when you want evenly spaced easting/northing lines in map units, for example a 100 km grid. See [Design notes](design/notes.md) for the rationale of the degree-based default.

## Rules

- Requires a projected `-srs` whose linear unit is the metre; otherwise the command stops with an error before touching any existing output file.
- `-e` is required and is given in projected metres (`xmin ymax xmax ymin`).
- Grid lines are placed at integer multiples of the step (anchored at 0) and span the extent. For example, with `-g 250000 250000` and an extent of ±600 000 m, lines are drawn at −500 000, −250 000, 0, 250 000 and 500 000 m in each direction.
- Without `-r`, each line is written as a straight segment between the extent edges. With `-r`, vertices are added at that spacing (in metres). Lines are straight in the projected CRS, so `-r` is only needed if you want vertices for later processing.
- `-m` works as in degree mode: lines at multiples of the major interval get `grid_type = major`, the others `minor`. The major interval must be a natural-number multiple of the grid step.
- Output fields are `x`, `y` and `grid_type` (see [Output fields](output-fields.md)); the latitude/longitude label fields are not written, and no companion point layer is created.
- Not available for PLY output. `-nde` (and, in Python, `-s` and `-p`) have no effect because nothing is reprojected.
- `-lo`, `-ls` and `-ls2` still apply to the output CRS.

## Examples

=== "Python / GDAL (conda)"

    ```sh
    mkgraticule -u meters \
                -srs IAU_2015:30135 \
                -g 100000 100000 \
                -m 500000 500000 \
                -e -500000 500000 500000 -500000 \
                moon_south_pole_grid_100km.gpkg
    ```

=== "Python / GDAL (standalone)"

    ```sh
    python mkgraticule_planet.py -u meters \
                                 -srs IAU_2015:30135 \
                                 -g 100000 100000 \
                                 -m 500000 500000 \
                                 -e -500000 500000 500000 -500000 \
                                 moon_south_pole_grid_100km.gpkg
    ```

=== "R / sf (standalone)"

    ```sh
    Rscript mkgraticule_planet.R -u meters \
                                 -srs IAU_2015:30135 \
                                 -g 100000 100000 \
                                 -m 500000 500000 \
                                 -e -500000 500000 500000 -500000 \
                                 moon_south_pole_grid_100km.gpkg
    ```

This writes 11 horizontal and 11 vertical lines (every 100 km from −500 km to +500 km), with the lines at 0 and ±500 km marked as `major`.

## Errors you may see

| Message (abridged) | Cause |
| ------------------ | ----- |
| `-u meters requires a projected target CRS` | `-srs` is a geographic CRS (degrees). Use a projected CRS or omit `-u`. |
| `... linear unit is the metre` | The projected CRS uses another unit (for example feet). |
| `-u meters requires -e/--extent ...` | `-e` was not given. The default degree extent is meaningless in metres. |
| `-u meters is not supported with PLY output.` | Combined with `-f ply` or a `.ply` output file. |
