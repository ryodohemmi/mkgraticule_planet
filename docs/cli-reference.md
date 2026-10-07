# CLI reference

```text
mkgraticule [options] outfile
```

`mkgraticule_planet` and `python -m mkgraticule_planet` are equivalent. The standalone scripts take the same options (the R script supports the options marked in the *R* column). Run `--help` for the authoritative list of your installed version.

## General

| Option | Default | R | Description |
| ------ | ------- | - | ----------- |
| `outfile` | — | ✓ | Output filename. If no extension is given, `.gpkg` is appended. |
| `-f`, `--format` | auto | ✓ (`gpkg`, `spatialite`) | `gpkg`, `spatialite` or `ply`. Auto-detected from the extension if omitted. |
| `-l`, `--layer` | `grid` | ✓ | Output layer name (the companion point layer is `point`, or `<layer>_point` when `-l` is set). |
| `-v`, `--version` | — | ✓ | Show the version and exit. |
| `-h`, `--help` | — | ✓ | Show help and exit. |

## Grid definition

| Option | Default | R | Description |
| ------ | ------- | - | ----------- |
| `-srs`, `--srs` | `IAU_2015:30100` | ✓ | Target spatial reference (IAU code, other GDAL/PROJ code, or `*.prj` file). |
| `-e`, `--extent ulx uly lrx lry` | `-180 90 180 -90` | ✓ | Extent in degrees (`xmin ymax xmax ymin`). With `-u meters`: projected metres, required. |
| `-g`, `--grid xstep ystep` | `5 5` (`-u meters`: `5000 5000`) | ✓ (degrees: required, no default) | Grid size in degrees (metres with `-u meters`). |
| `-r`, `--res xres yres` | `0.1 0.1` (`-u meters`: `100 100`) | ✓ (degrees: `0.5 0.1`) | Sampling spacing used to polygonize lines, in degrees (metres with `-u meters`). Recommended range: see [Output size check](#output-size-check). |
| `-m`, `--major xmajor ymajor` | none | ✓ | Major interval; must be a natural-number multiple of the grid step. Sets `grid_type` to `major`/`minor`. |
| `-u`, `--units` | `degrees` | ✓ | `degrees` or `meters`. See [Metre-based grids](metre-grids.md). |
| `-nde`, `--no-duplicate-endpoint` | off | ✓ | Drop the duplicate endpoint meridian for ~360° longitude spans. |

## Projection and reprojection

| Option | Default | R | Description |
| ------ | ------- | - | ----------- |
| `-lo`, `--lat-orig` | none | ✓ | Override latitude of origin / false origin / natural origin (degrees). |
| `-ls`, `--lat-sp` | none | ✓ | Override the (1st) standard parallel (degrees). |
| `-ls2`, `--lat-sp2` | none | ✓ | Override the 2nd standard parallel (degrees). |
| `-s`, `--skipfailures` | off | — | Skip features that fail reprojection. |
| `-p`, `--partial-reprojection` | off | — | Allow partial reprojection near projection-domain limits. |

## Output size check

| Option | Default | R | Description |
| ------ | ------- | - | ----------- |
| `-y`, `--yes` | off | ✓ | Answer yes to the confirmation below. Required when stdin is not a terminal. |

For each axis, `-r` should satisfy `floor <= res <= step/2`, where the floor is 0.1 degrees, or 10 m with `-u meters`. If `step/2` is smaller than the floor, the floor is relaxed to `step/2`.

| Situation | Behaviour |
| --------- | --------- |
| `res` below the floor, or estimated output above 100 MB | Warning with the estimated size, then `Continue? [y/N]`. Only `y`/`yes` (any case) continues; `n`/`no`, end of input, or any other final answer stops with exit status 1 and writes nothing. Invalid answers are asked again. An existing output file is left untouched. |
| Same, but stdin is not a terminal | Stops with exit status 1 unless `-y/--yes` is given. |
| `res` above `step/2` | A note is printed and the command continues. |
| PLY output | Not checked. |

The estimate is `vertices × 16 bytes` (2D coordinates in WKB). It is approximate: it counts geometry only and ignores the spatial index, so the real file is usually somewhat larger, and it is an upper bound on the vertex count because lines that collapse to a point are still counted.

## Quick View

| Option | Default | R | Description |
| ------ | ------- | - | ----------- |
| `-q`, `--qview` | off | ✓ | Open a window showing the whole grid after the file is written. See [Quick View](quick-view.md). |

## PLY options (Python only)

These options are marked `[PLY only]` in `--help`. See [3D PLY](ply.md).

| Option | Default | Description |
| ------ | ------- | ----------- |
| `-mesh`, `--input-mesh` | — | Input OBJ/mesh shape model (required for PLY output). |
| `-rorig`, `--ray-orig X Y Z` | `0 0 0` | Lat/lon origin in mesh coordinates for ray casting. |
| `-rscale`, `--ray-scale` | `3.0` | Ray start distance as a multiple of the mesh radius. |
| `-odist`, `--offset-distance` | `0` | Absolute outward offset applied to fitted vertices. |
| `-ofrac`, `--offset-fraction` | `0` | Outward offset as a fraction of the mesh radius. Mutually exclusive with `-odist`. |
| `-rbatch`, `--ray-batch` | `200000` | Ray-casting batch size. |
| `-rslow`, `--ray-slow` | off | Allow the `trimesh`/`rtree` intersector when Embree is unavailable. |
| `-prgb`, `--ply-rgb R,G,B` | `255,255,255` | Colour of the output. |
| `-trad`, `--tube-rad` | `0` | If > 0, write a tube mesh instead of edge primitives. |
| `-tseg`, `--tube-seg` | `8` | Radial segments of the tube cross-section. |

The previous long option names (`--mesh`, `--origin`, `--far-scale`, `--batch-size`, `--allow-slow-raycast`, `--color`, `--tube-radius`, `--tube-segments`, `-ofract`) remain accepted as compatibility aliases.

## Compatibility between options

| Combination | Result |
| ----------- | ------ |
| `-u meters` with a geographic CRS, or a projected CRS not in metres | Error |
| `-u meters` without `-e` | Error |
| `-u meters` with PLY output | Error |
| `-q` with PLY output | Warning, `-q` ignored |
| `-r` below the floor / output above 100 MB | Confirmation (see [Output size check](#output-size-check)) |
| `-nde`, `-s`, `-p` with `-u meters` | Ignored (notice printed) |
