# mkgraticule_planet v0.3.1

## What's Changed

- Removed the `-lo/--lato` CLI option and the related `latitude_of_origin` override code path.
- Strengthened CLI preflight validation:
  - `-g/--grid` (`xstep`, `ystep`) must be `> 0`
  - `-r/--res` (`xres`, `yres`) must be `> 0`
  - `xstep <= 360`, `ystep <= 180`
  - when `-m/--major` is provided, `xmajor`, `ymajor` must be `> 0`
- Added major-interval applicability rule:
  - `xmajor` is applied only if it is a natural-number multiple of `xstep`
  - `ymajor` is applied only if it is a natural-number multiple of `ystep`
  - when not applicable, corresponding `grid_type` remains `NULL` and an informational message is printed

## Notes

These changes prevent invalid inputs from reaching `np.arange(...)` and make major/minor classification behavior explicit for incompatible major intervals.
