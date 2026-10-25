# Python and R implementations

Both implementations generate 2D planetary GIS grids. Their defaults and
reprojection controls differ, so explicitly set `-g`, `-r`, `-e` and `-srs` when
comparing results. The implementations do not promise identical binary output or
identical geometries near projection-domain limits.

| Capability | Python / GDAL | R / sf |
| ---------- | ------------- | ------ |
| GeoPackage / SpatiaLite | Yes | Yes |
| Degree-based graticules and projected metre grids | Yes | Yes |
| Latitude/longitude labels, major/minor classification | Yes | Yes |
| Full-360° endpoint de-duplication (`-nde`) | Yes | Yes |
| Projection latitude parameter overrides | Yes | Yes |
| Collapsed-feature and projection-center point layer | Yes | Yes |
| Quick View (`-q`) | Optional matplotlib dependency | Base R graphics |
| Preview (`--dry-run`) | Yes; PLY checks options and mesh path only | Yes; 2D formats |
| Optional generation records (`--metadata`) | SQLite table / PLY comments | SQLite table |
| Preserve previous output if generation fails | Yes | Yes |
| Counts read back from saved 2D output | Yes | Yes |
| Skip failed features (`-s`) | Yes | No CLI switch |
| Partial reprojection (`-p`) | Yes | No CLI switch; transformations use sf behaviour |
| Near-global, limited-domain projection guard | Yes | No equivalent explicit guard |
| Fitted 3D PLY, mesh ray casting, tubes | Yes | No |
| Degree-mode default `-g` | `5 5` | Required |
| Degree-mode default `-r` | `0.1 0.1` | `0.5 0.1` |
| Metre-mode default `-g` | `5000 5000` | `5000 5000` |
| Metre-mode default `-r` | `100 100` | `100 100` |
| Installation | conda-forge package or standalone | Standalone |
| Main 2D dependencies | GDAL, numpy | sf, DBI, RSQLite |

See the [CLI reference](cli-reference.md) for the complete option list,
[Usage](usage.md#output-safety-and-generation-records) for output safety and
records, and [Development](development.md) for the shared integration tests.
