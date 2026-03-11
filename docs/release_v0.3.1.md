# mkgraticule_planet v0.3.1

## What's Changed

- Removed the `-lo/--lato` CLI option and the related `latitude_of_origin` override code path.
- Added preflight CLI validation to require positive (`> 0`) values for:
  - `-g/--grid` (`xstep`, `ystep`)
  - `-r/--res` (`xres`, `yres`)
  - `-m/--major` (`xmajor`, `ymajor`, when provided)
- Improved UX by surfacing clear argparse validation errors before runtime processing.

## Validation

- Added unit tests for CLI argument validation:
  - valid default invocation
  - rejection of non-positive `--grid` values
  - rejection of non-positive `--res` values
  - rejection of non-positive `--major` values
  - confirmation that removed `-lo/--lato` is no longer accepted
