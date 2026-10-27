# Python and R implementations

Both implementations generate 2D planetary GIS grids. Defaults for options
supported by both implementations are kept aligned with Python. Both include
reprojection controls and fitted PLY output. The implementations do not promise
identical binary output or identical geometries near projection-domain limits.

| Capability | Python / GDAL | R / sf |
| ---------- | ------------- | ------ |
| GeoPackage / SpatiaLite | Yes | Yes |
| 2D target CRS (`-s` / `-srs` / `--srs`) | Required; no default | Required; no default |
| Degree-based graticules and projected metre grids | Yes | Yes |
| Latitude/longitude labels, major/minor classification | Yes | Yes |
| Full-360° endpoint de-duplication (`-nde`) | Yes | Yes |
| Projection latitude parameter overrides | Yes | Yes |
| Collapsed-feature and projection-center point layer | Yes | Yes |
| Quick View (`-q`) | Optional matplotlib dependency | Base R graphics |
| Preview (`--dry-run`) | Yes; PLY checks options and mesh path only | Same |
| Optional generation records (`--metadata`) | SQLite table / PLY comments | SQLite table / PLY comments |
| Preserve previous output if generation fails | Yes | Yes |
| Counts read back from saved 2D output | Yes | Yes |
| Skip failed features (`-skipf`) | Yes | Yes |
| Partial reprojection (`-p`) | Yes | Yes |
| Near-global, limited-domain projection guard | Yes | Yes |
| Fitted 3D PLY, mesh ray casting, tubes | Yes | Yes |
| PLY ray backend | Embree, or trimesh/rtree fallback | Rvcg / VCGLIB |
| Degree-mode default `-g` | `5 5` | `5 5` |
| Degree-mode default `-r` | `0.1 0.1` | `0.1 0.1` |
| Metre-mode default `-g` | `5000 5000` | `5000 5000` |
| Metre-mode default `-r` | `100 100` | `100 100` |
| Installation | conda-forge package or standalone | Standalone |
| Main 2D dependencies | GDAL, numpy | sf, DBI, RSQLite |
| Additional PLY dependencies | trimesh, rtree, optional embreex | Rvcg |

R runs natively and does not invoke Python. R's `-skipf` drops empty transformed
features; GDAL/Python may retain some as empty geometries. Both report the actual
saved counts, and `-p` explicitly enables partial reprojection. The backend-choice
flag `--ray-slow` applies to Python's fallback; R accepts it for compatibility but
always uses the Rvcg accelerator.

See the [CLI reference](cli-reference.md) for the complete option list,
[Usage](usage.md#output-safety-and-generation-records) for output safety and
records, and [Development](development.md) for the shared integration tests.
