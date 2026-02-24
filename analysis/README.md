# Analysis

One-off and exploratory analysis scripts, separate from the core redistricting pipeline in `src/`.

## Block adjacency regression

**Script:** `block_adjacency_regression.py`

Estimates how likely adjacent blocks are to vote similarly using `data/block_level_data.gpkg`:

1. Loads blocks, derives two-party Democratic share per block.
2. Builds Queen adjacency (blocks that touch).
3. For each block, computes mean neighbor Democratic share.
4. OLS: block dem_share ~ mean neighbor dem_share (with optional cluster-robust SE by tract).
5. Writes `outputs/block_adjacency_regression_data.csv` and optional scatter plot.

**Run from project root:**

```bash
python analysis/block_adjacency_regression.py
```

**Requires:** `libpysal`, `statsmodels` (see main `requirements.txt`).
