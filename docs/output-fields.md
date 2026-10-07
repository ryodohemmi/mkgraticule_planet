# Output fields

## Main graticule layer

| Field      | Description |
| ---------- | ----------- |
| fid        | feature id |
| lat        | latitude value |
| lon        | longitude value |
| lat_90     | latitude label (-90° … 90°) |
| lat_ns     | latitude label (90°S … 90°N) |
| lon_180    | longitude label (-180° … 180°) |
| lon_ew     | longitude label (180°W … 180°E) |
| lon_360    | longitude label (0° … 360°) |
| lon_360e   | longitude label (0° … 360°E) |
| lon_360w   | longitude label (0° … 360°W) |
| grid_type  | `"major"` / `"minor"` when `--major` is used (otherwise NULL) |

## Metre grid layer (`-u meters`)

| Field      | Description |
| ---------- | ----------- |
| fid        | feature id |
| x          | easting of a vertical line, in projected metres (NULL for horizontal lines) |
| y          | northing of a horizontal line, in projected metres (NULL for vertical lines) |
| grid_type  | `"major"` / `"minor"` when `--major` is used (otherwise NULL) |

## Companion point layer (`point`)

| Field      | Description |
| ---------- | ----------- |
| fid        | feature id |
| lat        | latitude value, when applicable |
| lon        | longitude value, when applicable |
| lat_90     | latitude label (-90° … 90°) |
| lat_ns     | latitude label (90°S … 90°N) |
| lon_180    | longitude label (-180° … 180°) |
| lon_ew     | longitude label (180°W … 180°E) |
| lon_360    | longitude label (0° … 360°) |
| lon_360e   | longitude label (0° … 360°E) |
| lon_360w   | longitude label (0° … 360°W) |
| point_role | point role: `collapsed` or `center` |
