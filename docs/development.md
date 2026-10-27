# Development and tests

Create a conda environment with the same dependencies as GitHub Actions:

```sh
conda env create -f tests/environment.yml
conda activate mkgraticule-tests
python -m pip install --no-deps --no-build-isolation -e .
python -m unittest discover -s tests -v
```

The suite runs the package CLI, standalone Python script and standalone R script
against small temporary datasets. It checks GeoPackage/SpatiaLite output,
CRS and labels, shared defaults, major/minor classification, endpoint de-duplication, polar point
layers, metre grids, saved counts, metadata opt-in, dry runs and preservation of
existing output on failure. Python tests also cover partial write/replacement
failures, projection skips and standalone source parity. Shared Python/R PLY tests
check edge/tube output, sampled surface points, offsets, batches and invalid options.
R tests also simulate partial-write and replacement failures to verify that the
original file survives and staging directories are removed.
Custom PROJ, WKT1/WKT2 strings and WKT/PRJ files are checked for CRS and coordinate
accuracy. On Windows, a real file lock verifies output preservation and the retry
message for all three CLIs; this platform-specific test is skipped on Linux.

R tests are skipped if `Rscript` is unavailable. To use R from a different conda
environment, set `MKGRATICULE_R_COMMAND` to a JSON array of command arguments:

```sh
export MKGRATICULE_R_COMMAND='["conda", "run", "--no-capture-output", "-n", "rsf", "Rscript"]'
python -m unittest discover -s tests -v
```

GitHub Actions runs the full suite on Linux and Windows on pushes to `main` and pull requests,
with Python 3.11, 3.12 and 3.13 and R in conda-forge environments (six combinations).
The workflow matrix selects the Python versions; the environment file sets only
the minimum version for local test environments.
CI requires R tests and sets
`MKGRATICULE_REQUIRE_PLY=1` to fail if Python PLY dependencies or Rvcg are unavailable, and checks
the installed command entry points. The suite
does not exercise interactive Quick View windows or every OS/GDAL combination.

### Weekly dependency compatibility checks

The same six configurations run every Monday at 03:17 UTC (12:17 JST) on the
default branch. Scheduled runs disable the micromamba environment cache and
resolve dependencies afresh from conda-forge. Push and pull request runs retain
the environment cache. To run the same fresh-environment check manually, open
**Actions > Tests > Run workflow** and enable **fresh_environment**. With that
option unchecked, manual runs retain the cache too.

Every run logs the Python, Python-linked GDAL/PROJ, R and sf versions, sf's
external library versions, and the complete conda package list before testing.
This checks compatibility with versions the solver can install together for
each OS/Python combination. It does not guarantee testing the newest upstream
major release: conda-forge availability and other dependencies can constrain
the selected versions. Test failures still require investigation and fixes;
the workflow does not update users' environments or publish releases.

Scheduled checks become active when the workflow is merged into the default
branch; no additional secrets or external services are required. For failure
emails, check your GitHub **Settings > Notifications > System > Actions** settings,
enable **Email**, and optionally select **Only notify for failed workflows**.
See [GitHub's Actions notification settings](https://docs.github.com/en/subscriptions-and-notifications/how-tos/managing-github-actions-notifications).
Scheduled-workflow notifications go to the user who last changed the cron
schedule, subject to their notification settings.

GitHub may delay scheduled runs. In public repositories it also automatically
disables schedules after 60 days without repository activity. If disabled, open
the **Tests** workflow in **Actions** and re-enable it. Do not rely on manual runs
alone as a guarantee against this inactivity rule. See
[GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

The Python standalone file must remain byte-identical to
`src/mkgraticule_planet/_cli.py`. Copy the implementation after editing it; the
tests detect divergence.

Before publishing the conda recipe, create the release tag and add the SHA-256 of
its archive to `conda/meta.yaml`. A previous version's checksum must not be reused.
