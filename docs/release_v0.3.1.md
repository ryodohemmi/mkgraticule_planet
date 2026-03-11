# mkgraticule_planet v0.3.1

## What's Changed

- Removed the `-lo/--lato` CLI option and the related `latitude_of_origin` override code path.
- Strengthened CLI preflight validation:
  - `-g/--grid` (`xstep`, `ystep`) must be `> 0`
  - `-r/--res` (`xres`, `yres`) must be `> 0`
  - `xstep <= 360`, `ystep <= 180`
  - when `-m/--major` is provided, `xmajor`, `ymajor` must be `> 0`
  - when `-m/--major` is provided, `xstep <= xmajor` and `ystep <= ymajor`

## Notes

These changes prevent invalid inputs from reaching `np.arange(...)` and provide clearer argument constraints at parse time.
