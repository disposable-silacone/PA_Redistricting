# Algorithmic Map Generation & Ensemble Scoring

How to generate ~3,000 legal district maps (contiguity + population equality), score each with your existing metrics, and compare selected plans to 2024 election totals.

---

## 1. High-level pipeline

```
[Tract graph + initial partition]  →  GerryChain (ReCom)  →  3,000 partitions (tract → district)
                                                                        ↓
[Block data + tract assignment]     →  For each partition: block→tract→district → aggregate → metrics
                                                                        ↓
                                    →  ensemble_metrics.csv (one row per plan)
                                                                        ↓
[Select sample plans]               →  Save tract→district for those plans
                                    →  Apply to 2024 block/precinct data → compare to actual 2024
```

---

## 2. Legal requirements

- **Contiguity:** Each district is one connected component (no “islands”). GerryChain enforces this via the ReCom proposal and a contiguity constraint.
- **Population equality:** All districts within ±ε of ideal population (e.g. ε = 0.01 → ±1%). ReCom’s `pop_target` and `epsilon` enforce this.

Your block data already has tract IDs (`TRACT_GEOID20` or equivalent). **Building blocks for the graph = census tracts** (not blocks), so each plan is a partition of tracts into 18 districts.

---

## 3. Data prep (one-time)

### 3.1 Tract geography and adjacency

You need **one tract-level geography** and **population per tract**:

- **Option A (from your blocks):** Dissolve the block GeoPackage by `TRACT_GEOID20` to get tract polygons. Then build a **rook or queen adjacency graph** (shared edge or shared edge-or-corner) so each node = tract, each edge = two tracts that touch.
- **Option B:** Download Census tract shapefile for PA (e.g. `tl_2020_42_tract.shp`), build adjacency from that. Join tract population (and optional vote totals) from your block aggregates.

### 3.2 Graph node attributes

Each tract (node) needs at least:

- **Population** — Required for ReCom. Sum `block_pop` by tract from your block layer.
- **Initial district assignment** — So the chain has a valid starting partition. Use CD116: for each tract, assign the CD116 district that contains the tract’s centroid (or largest overlap). That gives 18 contiguous districts with roughly equal population to start from.

### 3.3 Block–tract link

Keep a table: **block GEOID20 → TRACT_GEOID20** (and block vote columns). You already have this in the block layer. For each generated plan you will: **tract → district** from the partition; **block → tract** from the block layer; so **block → district**; then aggregate block votes by district.

---

## 4. Generating 3,000 plans (GerryChain + ReCom)

Use **GerryChain** (Python package `gerrychain`) with the **ReCom** proposal:

1. **Build graph:** Tracts as nodes, adjacency as edges. Node attribute for population (e.g. `population`).
2. **Initial partition:** From CD116 (tract → district) or from a **random** partition (`--random-start`) so plan 0 is not the current map.
3. **ReCom proposal:** Merge two adjacent districts, then split the combined area into two districts with a spanning tree so that:
   - Both new districts are contiguous.
   - Both are within **ε of ideal population** (e.g. `epsilon=0.01` → ±1%).
4. **Chain:** Run a Markov chain with that proposal and a **contiguity** constraint. Accept every move (or use a Metropolis accept rule if you add a score). Run **3,000 steps** (or more and sample every Nth step to get 3,000 less-correlated plans).
5. **Store:** For each step, you have a **partition**: tract_id → district_id (e.g. 1..18). You do *not* need to store full geometry for 3,000 plans. Store either:
   - **In memory during run:** At each step, compute your metrics (see below) and append one row to a table; discard the partition, OR
   - **Save only the assignment:** For each of 3,000 plans, save `tract_geoid, district_id` (e.g. one CSV per plan or one big CSV with a `plan_id` column). Then you can re-score later or apply to 2024 data.

Recommendation: **During the chain, compute and write one row of metrics per plan to `ensemble_metrics.csv`.** Optionally, every 100th plan (or a random sample of 50 plans), also save the tract→district assignment to a file (e.g. `saved_plans/plan_000100.csv`) so you can later run 2024 validation on a few chosen plans.

---

## 5. Scoring each plan with your existing metrics

For **one** partition (tract → district):

1. **Block → district:** Join blocks to tract; join tract to partition assignment → each block gets a `district_id`.
2. **Aggregate:** Same as now: `aggregate_to_districts(blocks_joined, district_col="district_id")` → `district_df` with `pop_total`, `dem_total`, `rep_total`, `dem_share`, `winner`, etc.
3. **Partisan metrics:** Reuse `compute_efficiency_gap(district_df)`, `compute_mean_median`, `compute_seat_vote_gap`, `compute_competitiveness`, `compute_safe_seats`, etc.
4. **Compactness:** Build district geometries for this plan by **dissolving tract polygons by district_id**. Then run `compute_compactness(cds_gdf, id_col="district_id")` (same Polsby-Popper logic).
5. **Population deviation:** You already have `pop_total` per district in `district_df`; run `compute_population_deviation(district_df, id_col="district_id")`.

So for each plan you get one row:  
`plan_id, efficiency_gap, mean_median, seat_vote_gap, competitive_count, compactness_mean, pop_deviation_range_pct, ...`

Write that row to **ensemble_metrics.csv** (or a Parquet file for 3,000 rows). No need to keep 3,000 full maps in memory.

---

## 6. Output table: `ensemble_metrics.csv`

Columns (example):

| plan_id | efficiency_gap | mean_median | seat_vote_gap | seats_dem | seats_rep | competitive_count | compactness_mean | pop_deviation_range_pct | ... |
|--------|----------------|-------------|---------------|-----------|----------|-------------------|------------------|--------------------------|-----|
| 0      | -0.02          | 0.01        | -0.01         | 8         | 10       | 5                 | 0.28             | 2.1                      |     |
| 1      | 0.01           | -0.00       | 0.01          | 9         | 9        | 6                 | 0.31             | 1.8                      |     |
| ...    | ...            | ...         | ...           | ...       | ...      | ...               | ...              | ...                      |     |

You can sort/filter this table to **select a few sampled plans** (e.g. “most compact”, “closest to proportional”, “middle of the pack”, “one R-favoring and one D-favoring”) for 2024 validation.

---

## 7. Comparing selected plans to 2024 election totals (predictive value)

1. **2024 data:** Get 2024 vote totals at **block** or **precinct** level for PA (same geography as your blocks, or a precinct file that you can join to blocks). If it’s precinct-level, you’ll need precinct→block or block→precinct so that under a given plan you can assign 2024 votes to districts.
2. **For each selected plan:** You need that plan’s **tract → district** assignment (saved in step 4). Then:
   - Assign each 2024 geographic unit (block or precinct) to a tract (if 2024 is block, use existing block→tract).
   - Tract → district from the plan → each 2024 unit gets a district.
   - Aggregate 2024 votes by district → predicted 2024 result for that plan.
3. **Actual 2024:** Get official 2024 congressional results by district (e.g. certified results for the 18 PA districts).
4. **Compare:** For each selected plan, compare predicted district totals (or seat outcome) to actual 2024. Metrics: correlation, MAE, whether the plan “predicted” the correct winner in each district, or correct statewide seat count.

This validates whether plans scored well on 2020-style metrics also predict 2024 outcomes (out-of-sample predictive value).

---

## 8. Implementation checklist

| Step | Task | Output |
|------|------|--------|
| 1 | Install `gerrychain` (+ dependency `networkx`). Confirm tract column in block layer. | - |
| 2 | Build tract polygons (dissolve blocks by TRACT_GEOID20) or load PA tract shapefile. | Tract GeoDataFrame |
| 3 | Build tract adjacency graph (e.g. from tract shapes with `libpysal` or `geopandas`). | Graph with tract ids, edges |
| 4 | Add node attributes: population (from block sums), initial assignment (from CD116). | Graph ready for GerryChain |
| 5 | Run GerryChain ReCom chain (3,000 steps), contiguity + ε=0.01. At each step: block→district from partition, aggregate, compute all metrics, write one row. | `ensemble_metrics.csv` |
| 6 | Optionally save tract→district for every Nth plan (e.g. 30 plans). | `saved_plans/plan_*.csv` |
| 7 | Script: given plan_id (or plan file), 2024 block/precinct votes → district totals. | Predicted 2024 by plan |
| 8 | Script or notebook: load actual 2024 results, compare to predicted. | Validation table / plots |

---

## 9. Code layout (as implemented)

- **`src/tract_graph.py`** — Build tract GeoDataFrame from blocks (dissolve by tract), build adjacency graph (libpysal Queen), attach population and optional initial CD116 assignment. Returns graph + tract_gdf.
- **`run_ensemble.py`** — Top-level: load blocks, build graph (and either CD116 or random initial partition via `--random-start`), run GerryChain ReCom chain. At each step: get partition (tract→district), map blocks to districts, call `aggregate_to_districts`, `compute_*` in metrics/compactness/population; write one row to **ensemble_metrics.csv** (append if file exists so batches don’t overwrite). Optionally save tract→district CSVs (`--save-plans-every N`) and/or export district .gpkg (`--export-geopackage N`).
- **`export_plan_to_geopackage.py`** — Given a saved plan CSV (tract_geoid, district_id), build tract polygons from blocks, merge assignment, dissolve by district, write one GeoPackage for QGIS.
- **`validate_2024.py`** — Not yet implemented. Intended: load saved plans, 2024 vote data, assign to districts, compare to actual 2024 results.

---

## 10. Dependencies

- **gerrychain** — ReCom, Partition, MarkovChain, contiguity constraint.
- **networkx** — Graph (often pulled in by gerrychain).
- **libpysal** (optional) — Tract adjacency from shapefile (e.g. `libpysal.weights.Queen.from_dataframe(gdf)`).
- Your existing stack: **geopandas**, **pandas**, **numpy**, and your **src/** modules.

---

## 11. Epsilon and chain length

- **Population tolerance:** `epsilon=0.01` → ±1% is common and legally defensible. Tighter (e.g. 0.005) is more restrictive; looser (e.g. 0.02) allows more plans.
- **Chain length:** 3,000 steps give 3,000 plans. They are serially correlated. For a more “independent” sample, run 15,000 steps and take every 5th, or run 3 short chains (1,000 steps each) from different seeds and pool. For a first pass, 3,000 consecutive steps is fine; you can thin later.

---

**Code in this project:**  
- **`SIMULATION_DESIGN.md`** (this file) — full pipeline and 2024 validation plan.  
- **`src/tract_graph.py`** — build tract polygons from blocks, adjacency graph, population, and optional CD116 or random initial assignment.  
- **`run_ensemble.py`** — ReCom chain: `--steps`, `--epsilon`, `--random-start` (random initial partition), `--save-plans-every N` (tract→district CSVs), `--export-geopackage N` (district .gpkg for QGIS). Writes **`outputs/ensemble_metrics.csv`**; if that file already exists, **appends** new rows and continues plan_id from the last (run in batches without losing previous plans).  
- **`export_plan_to_geopackage.py`** — turn a saved plan CSV into one .gpkg of district polygons for QGIS.  
- **`requirements.txt`** — includes `gerrychain`, `networkx`, `libpysal`.

**Next steps:**  
1. Ensure your block layer has **TRACT_GEOID20** (or STATEFP20+COUNTYFP20+TRACTCE20; `load_blocks()` builds TRACT_GEOID20 automatically).  
2. `pip install gerrychain networkx libpysal`.  
3. Short test: `python run_ensemble.py --steps 10 --epsilon 0.05 --save-plans-every 1`.  
4. Full or batched run: `python run_ensemble.py --steps 3000 --epsilon 0.01 --save-plans-every 100`. Use **`--random-start`** for more variation from the current map.  
5. Use **`outputs/ensemble_metrics.csv`** to pick plans; export chosen plan_ids with `export_plan_to_geopackage.py outputs/saved_plans/plan_000042.csv`. See **ENSEMBLE_OUTPUTS_GUIDE.md** for workflow and QGIS export.
