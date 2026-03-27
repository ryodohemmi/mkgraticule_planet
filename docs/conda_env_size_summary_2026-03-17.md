# Conda environment size summary

**As of 17 March 2026**

This summary compares, for two example environments, the package download size estimated from `conda create --dry-run --json` and the post-install size measured in two ways:

- `conda env list --size`: conda-managed environment size
- `du -sBM "$CONDA_PREFIX"`: apparent on-disk size of the environment directory

## Summary table

| Environment | Install command | Download size (dry-run) | Conda-managed size | Apparent env dir size |
|---|---|---:|---:|---:|
| `gdal01` | `conda create -y -n gdal01 -c conda-forge gdal` | 127.68 MB | 498.0 MB | 527 MB |
| `rsf01` | `conda create -y -n rsf01 -c conda-forge r-base r-sf r-rsqlite r-dbi` | 346.96 MB | 1.46 GB | 1537 MB |
| `rsf01 / gdal01` ratio | — | 2.72x | 2.93x | 2.92x |

## Commands used

### 1. Estimated download size before installation

#### `gdal01`

```bash
CONDA_PKGS_DIRS=$(mktemp -d) conda create -n gdal01 -c conda-forge gdal --dry-run --json | python -c 'import sys,json; d=json.load(sys.stdin); b=sum(x["size"] for x in d["actions"]["FETCH"]); print(f"{b/1_000_000:.2f} MB"); print(f"{b/1_000_000_000:.3f} GB")'
```

Output:

```text
127.68 MB
0.128 GB
```

#### `rsf01`

```bash
CONDA_PKGS_DIRS=$(mktemp -d) conda create -n rsf01 -c conda-forge r-base r-sf r-rsqlite r-dbi --dry-run --json | python -c 'import sys,json; d=json.load(sys.stdin); b=sum(x["size"] for x in d["actions"]["FETCH"]); print(f"{b/1_000_000:.2f} MB"); print(f"{b/1_000_000_000:.3f} GB")'
```

Output:

```text
346.96 MB
0.347 GB
```

### 2. Environment creation

```bash
conda create -y -n gdal01 -c conda-forge gdal
conda create -y -n rsf01 -c conda-forge r-base r-sf r-rsqlite r-dbi
```

### 3. Conda-managed environment size

```bash
conda env list --size | grep -e "gdal01" -e "rsf01"
```

Output:

```text
gdal01                     498.0 MB /home/hemmi/miniforge3/envs/gdal01
rsf01                       1.46 GB /home/hemmi/miniforge3/envs/rsf01
```

### 4. Apparent on-disk environment directory size

#### `gdal01`

```bash
conda activate gdal01 && du -sBM "$CONDA_PREFIX" && conda deactivate
```

Output:

```text
527M    /home/hemmi/miniforge3/envs/gdal01
```

#### `rsf01`

```bash
conda activate rsf01 && du -sBM "$CONDA_PREFIX" && conda deactivate
```

Output:

```text
1537M   /home/hemmi/miniforge3/envs/rsf01
```

## Notes

- The **download size** is the total size of package archives listed in `actions.FETCH` from `conda create --dry-run --json`.
- The **conda-managed size** is reported by `conda env list --size`.
- The **apparent env dir size** is reported by `du` for the environment directory itself.
- In both examples, the installed environment size is substantially larger than the download size.
- For these measurements, `rsf01` is roughly **2.7x to 2.9x** larger than `gdal01`, depending on the metric used.
