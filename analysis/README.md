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

---

## VTD adjacency regression

**Script:** `vtd_adjacency_regression.py`

Same idea as block-level but at **VTD (precinct) level**, using congressional vote proportions from `data/Final Working VTD With Vote Totals.csv`. Use this when block-level votes were distributed from VTDs proportionally by population (so every block in a VTD has the same proportions and block-level analysis is redundant).

1. Loads VTD CSV; derives two-party Democratic share (uses `dem_votes`/`rep_votes`, or `dem_votes_2`/`rep_votes_2` when missing).
2. Builds point geometry from VTD centroids (INTPTLAT20, INTPTLON20), projects to PA UTM.
3. Defines “neighbors” as **K-nearest VTDs** (default K=8) by distance in projected space.
4. OLS: VTD dem_share ~ mean neighbor dem_share (with optional cluster-robust SE by county).
5. Writes `outputs/vtd_adjacency_regression_data.csv` and `outputs/vtd_adjacency_scatter.png`.

**Run from project root:**

```bash
python analysis/vtd_adjacency_regression.py
python analysis/vtd_adjacency_regression.py -k 6 --vtd-csv "data/other_vtds.csv"   # optional
```

**Requires:** `libpysal`, `statsmodels`, `geopandas`, `shapely`.
