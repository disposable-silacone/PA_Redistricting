"""
PA Redistricting Fairness Pipeline — paths and constants.
Add entries to PLANS for each map you want to score; outputs are keyed by map_id.
"""
from pathlib import Path

# Project root (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Block-level data (same for all maps)
DATA_DIR = PROJECT_ROOT / "data"
BLOCKS_PATH = DATA_DIR / "block_level_data.gpkg"

# Map/plan definitions: map_id -> district shapefile path and district ID column name.
# Census TIGER: CD116 uses CD116FP, CD113 uses CD113FP. Put shapefiles in data/.
PLANS = {
    "cd116": {
        "path": DATA_DIR / "tl_2020_42_cd116.shp",
        "district_col": "CD116FP",
    },
    "cd113": {
        "path": DATA_DIR / "tl_2020_42_cd113.shp",
        "district_col": "CD113FP",
    },
}

# CRS: NAD83 / UTM zone 18N (Pennsylvania)
CRS_PROJECTED = "EPSG:26918"

# Outputs directory (files are named by map_id)
OUTPUT_DIR = PROJECT_ROOT / "outputs"


def output_paths(map_id: str) -> dict:
    """Return output file paths for a given map_id."""
    return {
        "district_csv": OUTPUT_DIR / f"district_totals_{map_id}.csv",
        "metrics_json": OUTPUT_DIR / f"metrics_{map_id}.json",
        "missing_blocks_csv": OUTPUT_DIR / f"missing_blocks_{map_id}.csv",
        "seat_vote_plot": OUTPUT_DIR / f"seat_vote_curve_{map_id}.png",
        "dem_share_hist": OUTPUT_DIR / f"district_dem_share_hist_{map_id}.png",
        "scored_gpkg": OUTPUT_DIR / f"{map_id}_scored.gpkg",
    }


# Legacy single-plan paths (for code that still references them)
DISTRICT_CSV = OUTPUT_DIR / "district_totals_cd116.csv"
METRICS_JSON = OUTPUT_DIR / "metrics_cd116.json"
MISSING_BLOCKS_CSV = OUTPUT_DIR / "missing_blocks_cd116.csv"
SEAT_VOTE_PLOT = OUTPUT_DIR / "seat_vote_curve_cd116.png"
DEM_SHARE_HIST_PLOT = OUTPUT_DIR / "district_dem_share_hist_cd116.png"
CD116_SCORED_GPKG = OUTPUT_DIR / "cd116_scored.gpkg"
