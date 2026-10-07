# Quick View (`-q`)

Add `-q/--qview` to open a window showing the whole grid right after the output file is written. Close the window to finish the command.

```sh
mkgraticule -q -g 10 10 -srs IAU_2015:30100 moon_graticule.gpkg
```

The window shows the lines written to the output file (and the companion point layer, if any) in the output CRS with equal axis scaling. When `-m/--major` is used, major lines are drawn darker and thicker than minor lines. It works with both the degree mode and [`-u meters`](metre-grids.md).

## Python

- Requires [matplotlib](https://matplotlib.org/), which is an optional dependency and is not installed with the conda package:

    ```sh
    conda install -c conda-forge matplotlib
    ```

    or, for a pip-based environment, `pip install mkgraticule_planet[quickview]`.

- The output file is written before the window opens. If matplotlib is missing, or only a non-interactive backend (for example `Agg`) is available, a warning is printed and the command still finishes successfully with the file written.
- The command exits when the window is closed.

## R

- Uses base graphics and opens a window on Windows (`windows()`), macOS (`quartz()`) and X11 (`x11()`).
- If the window cannot be opened, a warning is printed and the output file is kept.

## Not available for PLY output

`-q` is ignored with a warning when the output format is PLY.
