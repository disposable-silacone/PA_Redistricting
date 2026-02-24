# Understanding ensemble_metrics.csv and plan maps

This guide describes the **ensemble pipeline**: generating many legal district plans with GerryChain ReCom, scoring each in `ensemble_metrics.csv`, and exporting chosen plans to GeoPackage for QGIS. For project overview and the two main pipelines (score existing maps vs generate ensemble), see **README.md**.

---

## What’s in ensemble_metrics.csv

One **row per plan** (one per ReCom step). Each column is a metric for that plan.

| Column | Meaning |
|--------|--------|
| **plan_id** | Plan index (0, 1, 2, …). Use this to match a row to an exported map. |
| **efficiency_gap** | Partisan fairness: &gt;0 = D advantage, &lt;0 = R advantage. Near 0 is more neutral. |
| **mean_median** | Skew of district vote shares. Near 0 = symmetric. |
| **seat_vote_gap** | (D seat share) − (D vote share). &gt;0 = D gets more seats than votes. |
| **partisan_bias_at_50** | At 50/50 statewide vote, seat share − 0.5. 0 = symmetric. |
| **seats_dem** / **seats_rep** | Number of districts won by each party under that plan. |
| **competitive_count** | Number of districts with D share in 45–55%. |
| **compactness_mean** | Polsby–Popper (0–1). Higher = rounder districts. |
| **pop_deviation_range_pct** | Max − min district population deviation from ideal (%). |

### How to use it

- **Sort/filter** in Excel or pandas to pick plans (e.g. lowest |efficiency_gap|, highest compactness_mean, or “middle” plans).
- **Compare to CD116/CD113:** Your `metrics_cd116.json` has the same kind of metrics; compare a chosen plan’s row to those numbers.
- **plan_id** links each row to a saved plan CSV: plan 0 → `saved_plans/plan_000000.csv`, plan 5 → `saved_plans/plan_000005.csv`, etc. (when you use `--save-plans-every`).

---

## Maps for QGIS (.gpkg, no .shp)

The pipeline does **not** write a map by default. You can get **GeoPackage** layers (open in QGIS like any vector layer) in two ways:

### Option 1: Export during the ensemble run

Re-run with `--export-geopackage N` to write one **.gpkg per exported plan**:

```bash
python run_ensemble.py --steps 20 --export-geopackage 1
```

- Writes `outputs/ensemble_plans/plan_000000.gpkg`, `plan_000001.gpkg`, … (every plan when N=1).
- Use `--export-geopackage 5` to export only every 5th plan (e.g. 0, 5, 10, 15).
- Each file has one layer: **18 district polygons** (tracts dissolved by district), in WGS84 (EPSG:4326) for QGIS.

In QGIS: **Layer → Add Layer → Add Vector Layer**, choose the .gpkg file. Style by the `district_id` column if you like.

### Option 2: Export from a saved plan CSV

If you already have tract→district CSVs from `--save-plans-every` (e.g. `outputs/saved_plans/plan_000005.csv` for plan_id 5), turn one into a .gpkg:

```bash
python export_plan_to_geopackage.py outputs/saved_plans/plan_000005.csv --out outputs/plan_000005.gpkg
```

Omit `--out` to write to `outputs/ensemble_plans/plan_000005.gpkg`. The CSV filename matches **plan_id** in ensemble_metrics.csv (plan_000005.csv = the plan in row plan_id 5).

**There is no .shp written;** GeoPackage (.gpkg) is used instead (QGIS opens it the same way).

---

## Workflow: measure many plans, then export only the ones you want

1. **Run the ensemble and save every plan’s assignment** (e.g. 10 or 100 plans):
   ```bash
   python run_ensemble.py --steps 10 --save-plans-every 1
   ```
   You get **outputs/ensemble_metrics.csv** (one row per plan) and **outputs/saved_plans/plan_000000.csv**, **plan_000001.csv**, … (tract→district for each plan).  
   **Append mode:** If **ensemble_metrics.csv** already exists, the script resumes plan_id from the last row (e.g. after 0–9, the next run writes plan_id 10–19 and **plan_000010.csv** … **plan_000019.csv**). So you can run in batches of 10 without losing previous plans.

2. **Use the metrics to choose plans**  
   Open **ensemble_metrics.csv** in Excel or pandas. Sort/filter by what you care about (e.g. lowest |efficiency_gap|, highest compactness_mean, or a mix). Note the **plan_id** values (e.g. 0, 3, 7).

3. **Export only those plans to .gpkg for QGIS**  
   For each chosen plan_id, run:
   ```bash
   python export_plan_to_geopackage.py outputs/saved_plans/plan_000003.csv
   ```
   So you only create map files for the plans you care about, not all of them.

---

## Getting more variation (plans that look different from the current map)

By default the chain **starts from the current CD116 map** and each ReCom step only changes two districts. So after 10 steps you get small “edge” changes. To get plans that look **much different**:

1. **Start from a random map**  
   Use **`--random-start`** so the first plan is built by recursively splitting the state at random (not from CD116). Later steps then explore from that random start:
   ```bash
   python run_ensemble.py --steps 50 --save-plans-every 1 --random-start
   ```
   Plan 0 will already look very different from CD116; later plans stay varied.

2. **Run longer and sample from the end**  
   Even starting from CD116, after many steps the chain “forgets” the start. Run 2,000–3,000 steps and save only the last 50–100 plans (e.g. `--save-plans-every 50` and use the highest plan_ids). Those will be more varied than the first 10.
