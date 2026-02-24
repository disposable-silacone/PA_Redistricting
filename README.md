<<<<<<< HEAD
# PA Redistricting Fairness Pipeline

Score Pennsylvania congressional district maps on **partisan fairness**, **compactness**, and **population equality**, and optionally **generate** many legal alternative maps (contiguity + population balance) and score them.

**Data:** Block-level votes and population (`block_level_data.gpkg`), district boundaries (e.g. CD116, CD113 shapefiles in `data/`). Same vote data is used for all maps.

---

## Two pipelines

### 1. Score existing maps (CD116, CD113, or any plan in `config.PLANS`)

**Script:** `run_metrics_cd116.py`  
**Inputs:** Block GeoPackage + district shapefile (path set in `src/config.py` PLANS).  
**Outputs:** `outputs/district_totals_<map_id>.csv`, `outputs/metrics_<map_id>.json` (and optional missing_blocks CSV). Each JSON includes `map_id`, partisan metrics, compactness, and population deviation.

```bash
python run_metrics_cd116.py              # default: cd116
python run_metrics_cd116.py cd113       # score CD113 map
python run_metrics_cd116.py cd113 --districts "data\other.shp"   # custom path
```

**Docs:** [FIRST_STEPS.md](FIRST_STEPS.md) (setup, config, comparing maps), [METRICS_GUIDE.md](METRICS_GUIDE.md) (what each metric means).

---

### 2. Generate and score many alternative maps (ensemble)

**Script:** `run_ensemble.py`  
**Inputs:** Same block data; tract-level graph built from blocks (by dissolving on `TRACT_GEOID20`). Optional: start from CD116 (small changes) or from a random partition (`--random-start`) for more variation.  
**Outputs:** `outputs/ensemble_metrics.csv` (one row per plan: plan_id + fairness/compactness/pop metrics). Optionally `outputs/saved_plans/plan_*.csv` (tract→district) for chosen plans. Export selected plans to GeoPackage for QGIS via `export_plan_to_geopackage.py`.

```bash
python run_ensemble.py --steps 50 --save-plans-every 1
python run_ensemble.py --steps 20 --random-start --save-plans-every 1   # more variation
# Append mode: if ensemble_metrics.csv exists, new plan_ids continue from last (no overwrite)
```

**Docs:** [SIMULATION_DESIGN.md](SIMULATION_DESIGN.md) (pipeline, ReCom, 2024 validation), [ENSEMBLE_OUTPUTS_GUIDE.md](ENSEMBLE_OUTPUTS_GUIDE.md) (understanding metrics CSV, QGIS export, workflow, append, variation).

---

## Where to start

- **Score one or two existing maps (e.g. CD116 vs CD113):** [FIRST_STEPS.md](FIRST_STEPS.md) and [METRICS_GUIDE.md](METRICS_GUIDE.md).  
- **Generate many plans and pick/export some:** [ENSEMBLE_OUTPUTS_GUIDE.md](ENSEMBLE_OUTPUTS_GUIDE.md) and [SIMULATION_DESIGN.md](SIMULATION_DESIGN.md).  
- **Tech spec (MVP + extensions):** `PROJECT PA Redistricting Fairness P.txt`.

**Requirements:** Python 3.11+, `geopandas`, `pandas`, `numpy`, `shapely`, `pyogrio`; for ensemble add `gerrychain`, `networkx`, `libpysal`. See `requirements.txt`.
=======
# PA_Redistricting
PA congressional redistricting: score maps (fairness/compactness/pop) and generate 17/18-district ensembles with GerryChain
>>>>>>> 5606d21d761f01b6e7e38b3b987416bd5e95cb85
