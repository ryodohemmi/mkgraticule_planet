# Usage

From v1.4.0, **`-s` / `-srs` / `--srs` is required for GeoPackage and SpatiaLite output**,
including `--dry-run`; there is no default CRS. Missing or blank CRS values stop
before creating directories or replacing output. To retain the previous Moon
CRS, add `-srs IAU_2015:30100` to older commands. For other bodies, specify the
intended CRS. PLY uses input mesh coordinates and does not require `-srs`.

All three CRS aliases take a value. The old `-s` skip-failures flag has moved to
`-skipf`; update old commands to use `-skipf` or the unchanged `--skipfailures`.
The program never guesses the old meaning of `-s` from the presence of a value.

## Output safety and generation records

Existing output files are replaced automatically, including any other layers in
the file. Output is first generated in a temporary directory on the destination
filesystem, closed, and (for 2D GIS output) read back for validation. Only then is
the destination replaced. Errors during generation, metadata recording or
replacement leave the previous output intact. Temporary files are cleaned up on
normal completion or handled errors. Enough disk space for both the old and new
files is required. SQLite journal files at the destination block replacement;
close applications using that output and retry. This does not coordinate concurrent
writers or provide recovery from a process kill or power loss.

The 2D summary shows **saved latitude/longitude lines** (or northing/easting lines),
**saved line features**, **empty line geometries**, and **saved point features**.
These are counted from the written output. Collapsed lines are in the point layer;
features skipped during reprojection are absent from the saved counts. Empty line
features, if present, are included in the saved totals and reported separately.
An output with no non-empty grid lines is treated as a failure.

### Preview without writing (`--dry-run`)

```sh
mkgraticule --dry-run -g 10 10 -r 0.5 0.5 -srs IAU_2015:30100 moon.gpkg
Rscript standalone/mkgraticule_planet.R --dry-run -g 10 10 -srs IAU_2015:30100 moon.gpkg
```

Validates the options and CRS and shows the format, effective CRS, extent, units,
grid spacing, sampling spacing, major intervals, estimated line/vertex counts and
approximate geometry size. It also reports whether an existing output would be
replaced and whether metadata recording is enabled. It creates no directories or
files, asks no confirmation questions, and opens no Quick View window, even with
`-q`. Invalid settings still produce a nonzero exit status.

The estimate is before reprojection and excludes attributes, indexes and storage
overhead. It cannot predict which features will collapse or fail reprojection.
Python's near-global projection-domain check still applies. For PLY, an existing
input mesh path and valid CLI options are required, but the mesh is not loaded,
ray casting is not performed, and output geometry/size are not estimated.

### Optional generation records (`--metadata`)

```sh
mkgraticule --metadata -g 10 10 -m 30 30 -srs IAU_2015:30100 moon.gpkg
```

Off by default. With `--metadata`, GeoPackage and SpatiaLite contain a plain
SQLite table named `mkgraticule_metadata` with `key` and `value` text columns.
The record includes the tool version, implementation, UTC timestamp, original
command arguments, output format, CRS, effective grid/resolution/extent/major
settings, projection parameter overrides and endpoint de-duplication setting.
The effective output CRS is also stored as `crs_wkt`, so a custom or file-based
CRS can be recovered. Python and R use the same value format: scalars are plain
text, numeric lists are space-separated, booleans are `true`/`false`, and an unset
option is an empty string. `format` is, for example, `gpkg`, and `grid` is `10 10`.
Only settings relevant to the output are included; 2D output has no PLY-specific
settings or display/confirmation flags. Both implementations record their degree-mode
reprojection switches. `no_duplicate_endpoint` is `false` for metre grids, where
the switch has no effect.

`override_lat_orig`, `override_lat_sp` and `override_lat_sp2` record explicit CLI
overrides. Actual projection parameters, including CRS defaults, are recorded
separately as `crs_parameter_<name>`. Names are lowercased WKT parameter names with
non-alphanumeric characters removed: Lambert's first standard parallel is, for
example, `crs_parameter_latitudeof1ststandardparallel`. Values use the units declared
in `crs_wkt`. Command arguments are stored as shell-quoted text for reference.
`mkgraticule_metadata` cannot be used as the grid layer name when recording is enabled.

```sql
SELECT key, value FROM mkgraticule_metadata ORDER BY key;
```

PLY output from both implementations records settings, including mesh path, ray origin, offsets and tube
parameters, in `comment mkgraticule key=value` header lines (values are JSON-escaped
text to keep comments on one line). PLY coordinates are
in the input mesh coordinate system; no geographic output CRS is recorded.
The mesh contents are not embedded, so keep the source mesh to reproduce the
result. Command records include local paths supplied on the command line.

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
| `.ply` | Fitted 3D PLY (Python or R) |

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
