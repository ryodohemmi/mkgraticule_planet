# Usage

After installation, the recommended command is:

```sh
mkgraticule --help
```

For compatibility, the longer command is also available:

```sh
mkgraticule_planet --help
```

You can also run via `python -m`:

```sh
python -m mkgraticule_planet --help
```

When running standalone scripts from a cloned repository, use the files in `standalone/`.

Output filenames may be specified either with or without the `.gpkg` extension. If the extension is omitted, it is added automatically.

The output format is auto-detected from the file extension:

| Extension | Format |
| --------- | ------ |
| `.gpkg` (default) | GeoPackage |
| `.sqlite` / `.sqlite3` / `.spatialite` | SpatiaLite |
| `.ply` | Python-only fitted 3D PLY |

To override auto-detection, use `-f/--format`:

```sh
python mkgraticule_planet.py -f spatialite ... out.db
```

The `-e` option specifies the geographic extent in the order: `xmin ymax xmax ymin` ("ullr" style). With `-u meters` it is given in projected metres instead (see [Metre-based grids](metre-grids.md)).

All options are listed in the [CLI reference](cli-reference.md).

## Basic example

!!! note
    Examples are provided in two forms:

    - **conda** — use the `mkgraticule` command after `conda install -c conda-forge mkgraticule-planet`. `mkgraticule_planet` is also available as a compatibility alias.
    - **standalone** — run the single-file script directly with `python mkgraticule_planet.py ...` or `Rscript mkgraticule_planet.R ...`.

    R has no conda-forge package yet, so only the standalone form is shown for R.

=== "Python / GDAL (conda)"

    ```sh
    # Moon
    mkgraticule -g 10 10 \
                -r 0.2 0.2 \
                -srs IAU_2015:30100 \
                -e -180 90 180 -90 \
                moon_graticule.gpkg

    # Mars
    mkgraticule -g 15 15 \
                -r 0.5 0.5 \
                -srs IAU_2015:49900 \
                mars_graticule.gpkg
    ```

=== "Python / GDAL (standalone)"

    ```sh
    # Moon
    python mkgraticule_planet.py -g 10 10 \
                                 -r 0.2 0.2 \
                                 -srs IAU_2015:30100 \
                                 -e -180 90 180 -90 \
                                 moon_graticule.gpkg

    # Mars
    python mkgraticule_planet.py -g 15 15 \
                                 -r 0.5 0.5 \
                                 -srs IAU_2015:49900 \
                                 mars_graticule.gpkg
    ```

=== "R / sf (standalone)"

    ```sh
    # Moon
    Rscript mkgraticule_planet.R -g 10 10 \
                                 -r 0.2 0.2 \
                                 -srs IAU_2015:30100 \
                                 -e -180 90 180 -90 \
                                 moon_graticule.gpkg

    # Mars
    Rscript mkgraticule_planet.R -g 15 15 \
                                 -r 0.5 0.5 \
                                 -srs IAU_2015:49900 \
                                 mars_graticule.gpkg
    ```

## Major/minor graticules

=== "Python / GDAL (conda)"

    ```sh
    mkgraticule -g 10 10 \
                -m 30 30 \
                -srs IAU_2015:40100 \
                -e -180 90 180 -90 \
                phobos_graticule.gpkg
    ```

=== "Python / GDAL (standalone)"

    ```sh
    python mkgraticule_planet.py -g 10 10 \
                                 -m 30 30 \
                                 -srs IAU_2015:40100 \
                                 -e -180 90 180 -90 \
                                 phobos_graticule.gpkg
    ```

=== "R / sf (standalone)"

    ```sh
    Rscript mkgraticule_planet.R -g 10 10 \
                                 -m 30 30 \
                                 -srs IAU_2015:40100 \
                                 -e -180 90 180 -90 \
                                 phobos_graticule.gpkg
    ```

If `-m/--major` is set: `grid_type` will be `"major"` or `"minor"`.
If omitted: `grid_type` is NULL.

## Metre-based grids, Quick View and the output size check

Optional modes and safeguards are described on their own pages:

- [Metre-based grids (`-u meters`)](metre-grids.md): a planar easting/northing grid written directly in a metre-based projected CRS.
- [Quick View (`-q`)](quick-view.md): a window showing the whole grid right after the file is written.
- [Output size check](cli-reference.md#output-size-check): a yes/no confirmation, with an estimated file size, when `-r` is below its recommended lower bound or the output would exceed 100 MB (`-y/--yes` skips it).
