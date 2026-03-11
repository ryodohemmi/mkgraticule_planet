# mkgraticule_planet v0.3.1

## What's Changed

- Removed the `-lo/--lato` CLI option and the related `latitude_of_origin` override code path.
- Strengthened CLI preflight validation:
  - `-g/--grid` (`xstep`, `ystep`) must be `> 0`
  - `-r/--res` (`xres`, `yres`) must be `> 0`
  - `xstep <= 360`, `ystep <= 180`
  - when `-m/--major` is provided, `xmajor`, `ymajor` must be `> 0`
  - when `-m/--major` is provided, `xmajor <= xstep` and `ymajor <= ystep`
- Added runtime compatibility warnings for major/minor classification:
  - if `xstep` is not evenly divisible by `xmajor`, longitude `grid_type` values are set to `NULL`
  - if `ystep` is not evenly divisible by `ymajor`, latitude `grid_type` values are set to `NULL`

## Notes

These changes prevent invalid inputs from reaching `np.arange(...)` and clarify behavior when major/minor classification intervals cannot be cleanly applied to generated graticule lines.
