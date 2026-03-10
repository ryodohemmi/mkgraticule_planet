# mkgraticule_planet v0.3.1

## Highlights

- Added strict validation for CLI step arguments:
  - `--grid` (`xstep`, `ystep`)
  - `--res` (`xres`, `yres`)
  - `--major` (`xmajor`, `ymajor`)

  Non-positive values now fail fast with clear `ValueError` messages.

- Fixed projection-center handling when `-lo/--lato` is specified.
  After overriding `latitude_of_origin`, the tool now recomputes center latitude/longitude used for center-related logic.

- Improved center-point duplicate detection in the companion point layer (`*_points`).
  Any existing coincident point is treated as duplicate (no dependency on `point_role`).

## Notes

- Version bump: `0.3.0` → `0.3.1`.
- This release focuses on correctness and safer input handling; no breaking CLI flag changes were introduced.
