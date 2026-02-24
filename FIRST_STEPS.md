# PA Redistricting Fairness Pipeline — First Steps

Based on the tech spec (PROJECT PA Redistricting Fairness P.txt), here is a proposed order of work.

---

## 1. Validate inputs and environment

- **Block data:** Confirm `block_level_data.gpkg` (or `data/pa_blocks_votes.gpkg`) has the required schema:
  - `GEOID20` (15-char), `block_pop`, `dem_block`, `rep_block`, `geometry`
  - **Tract:** Either `TRACT_GEOID20` or the components `STATEFP20` + `COUNTYFP20` + `TRACTCE20`. If `TRACT_GEOID20` is missing, `load_blocks()` (in `src/load_data.py`) builds it from those three columns.
- **District data:** Ensure `tl_2020_42_cd116.shp` (or equivalent) is present with `CD116FP` and `geometry`. If it lives elsewhere, put a copy in `data/` or set paths in config.
- **Python:** Use Python 3.11+ with `geopandas`, `pandas`, `numpy`, `shapely`. Add `pyogrio` for faster reads and `matplotlib` if you want quick plots.

**Deliverable:** A small script or notebook that loads both layers, prints CRS, columns, and row counts, and checks for required columns.

---

## 2. Project layout and config

- Create `data/` (if not present) and `outputs/`.
- Add `src/config.py` with:
  - Path to block GeoPackage and a **PLANS** dict: each entry is a map_id (e.g. `cd116`, `cd113`) with the path to that plan’s district shapefile and the district ID column (e.g. `CD116FP`, `CD113FP`). This lets you score multiple maps (CD116, CD113, etc.) with the same pipeline.
  - CRS constant: `EPSG:26918` (NAD83 UTM 18N for PA)
  - Output paths for CSV, JSON, and optional plots/GeoPackage
- Add `src/load_data.py` with:
  - `load_blocks()` → GeoDataFrame
  - `load_cds()` → GeoDataFrame  
  - `ensure_crs(gdf, epsg=26918)` to normalize CRS

**Deliverable:** Config and loaders so that `run_metrics_cd116.py` can run “load blocks + load CDs + reproject” and print shapes/CRS.

---

## 3. Block–district assignment (MVP-2)

- Add `src/assignments.py` with `assign_blocks_to_districts(blocks_gdf, cds_gdf)`:
  - Use block **representative points** (not polygons) for the join
  - `geopandas.sjoin(..., predicate="within", how="left")` with `cds_gdf[["CD116FP","geometry"]]`
  - QA: assert or report fraction of blocks with non-null `CD116FP` (e.g. > 99.9%); optionally export `outputs/missing_blocks.csv` for unassigned blocks
- If `CD116FP` is numeric, normalize to zero-padded strings `"01"`–`"18"`.

**Deliverable:** A single joined table (blocks + `CD116FP`) with a reported count of missing assignments.

---

## 4. District aggregation (MVP-3)

- Add `src/aggregate.py` with `aggregate_to_districts(blocks_joined_df)`:
  - Group by `CD116FP`; sum `block_pop`, `dem_block`, `rep_block`
  - Derive: `two_party_total`, `dem_share`, `rep_share`, `winner`, `margin`
- Validate: district sums of `dem_block`/`rep_block` match statewide block sums within a small tolerance.

**Deliverable:** `outputs/district_totals_cd116.csv` as specified in the spec.

---

## 5. Statewide and fairness metrics (MVP-4)

- Add `src/metrics.py` with:
  - `compute_efficiency_gap(district_df)` (two-party, spec convention)
  - `compute_mean_median(district_df)`
  - `compute_seat_vote_gap(district_df, statewide_dem_share)`
  - Optional: `compute_uniform_swing_bias(...)` for partisan bias at 50%
- Build a single metrics dict: statewide totals, seat counts, EG, mean–median, seat–vote gap, optional bias; add `notes` and `timestamp`.

**Deliverable:** `outputs/metrics_cd116.json` with all required (and any optional) fields. The JSON (and district CSV) also include **compactness** (e.g. Polsby–Popper) and **population deviation** per district; see METRICS_GUIDE.md.

---

## 6. Orchestration and optional outputs

- Implement `run_metrics_cd116.py`: call load → ensure CRS → assign → aggregate → metrics → write CSV and JSON.
- Optional: quick plots (e.g. `outputs/seat_vote_curve_cd116.png`, `outputs/district_dem_share_hist.png`) and `outputs/cd116_scored.gpkg` (dissolved districts + totals).

---

## Suggested order to implement

| Step | Action |
|------|--------|
| 1 | Validate inputs (schema + paths); create `data/`, `outputs/` |
| 2 | Add `src/config.py` and `src/load_data.py`; wire paths to your actual `block_level_data.gpkg` and `tl_2020_42_cd116.shp` |
| 3 | Implement `src/assignments.py` and QA for missing blocks |
| 4 | Implement `src/aggregate.py` and write district CSV |
| 5 | Implement `src/metrics.py` and write metrics JSON |
| 6 | Add `run_metrics_cd116.py` and optional plots/GeoPackage |

---

## Comparing multiple maps (e.g. CD113 vs CD116)

The pipeline is keyed by **map_id**. Each run produces outputs tagged with that id; the metrics JSON includes `"map_id"` so you can tell which map each file describes.

1. **Add the CD113 shapefile**  
   Download the Census TIGER shapefile for PA CD113 (e.g. `tl_rd13_42_cd113.zip`), unzip it into `data/`, so you have `data/tl_rd13_42_cd113.shp` (and `.shx`, `.dbf`, etc.). The config already has a `cd113` plan pointing at that path and `CD113FP` as the district column.

2. **Run both maps**  
   - CD116 (default): `python run_metrics_cd116.py` or `python run_metrics_cd116.py cd116`  
   - CD113: `python run_metrics_cd116.py cd113`

3. **Outputs**  
   - `outputs/metrics_cd116.json` and `outputs/metrics_cd113.json` — each has `"map_id"` at the top.  
   - `outputs/district_totals_cd116.csv` and `outputs/district_totals_cd113.csv`  
   Compare the two JSONs (efficiency_gap, seat_vote_gap, compactness_mean, pop_deviation_range_pct, etc.) for a fairness comparison.

4. **Adding more maps**  
   In `src/config.py`, add another entry to the **PLANS** dict with a new `map_id`, the path to the district shapefile, and the district ID column name (e.g. `CD118FP` for a future map). Then run `python run_metrics_cd116.py <map_id>`.

---

## Data path note

The spec references `data/pa_blocks_votes.gpkg` and `data/tl_2020_42_cd116.shp`. Your block file is `block_level_data.gpkg`. Either:

- Place `block_level_data.gpkg` and the CD116 shapefile (and its sidecar files) in `data/` and point config to `data/block_level_data.gpkg` and `data/tl_2020_42_cd116.shp`, or  
- Keep them at the project root and set paths in `src/config.py` accordingly.

Once the first-step validation (Step 1) passes, the rest of the pipeline can proceed as above.

---

## Ensemble workflow (generate many plans)

To **generate** many alternative district maps (contiguity + population balance) and score them:

1. **Run the ensemble:** `run_ensemble.py` builds a tract-level graph from blocks, runs a GerryChain ReCom chain, and writes **`outputs/ensemble_metrics.csv`** (one row per plan: plan_id + partisan, compactness, population metrics). Optionally it saves tract→district CSVs (`--save-plans-every N`) and can export a plan to GeoPackage (`--export-geopackage N`).
2. **Append mode:** If `ensemble_metrics.csv` already exists, new runs **append** rows and continue `plan_id` from the last (so you can run in batches without overwriting).
3. **Export a chosen plan to QGIS:** Use `export_plan_to_geopackage.py` with a saved plan CSV to produce a district-level .gpkg.

See **ENSEMBLE_OUTPUTS_GUIDE.md** (understanding the metrics CSV, QGIS export) and **SIMULATION_DESIGN.md** (ReCom, options like `--random-start`, full pipeline).
