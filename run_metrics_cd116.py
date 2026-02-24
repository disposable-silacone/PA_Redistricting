"""
Run the PA Redistricting Fairness pipeline for a given map/plan.
Load blocks + districts -> assign -> aggregate -> metrics -> export.
Usage: python run_metrics_cd116.py [map_id]
  e.g. python run_metrics_cd116.py cd116
       python run_metrics_cd116.py cd113
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from src import config
from src.load_data import load_blocks, load_cds, ensure_crs
from src.assignments import assign_blocks_to_districts
from src.aggregate import aggregate_to_districts
from src.metrics import (
    compute_efficiency_gap,
    compute_mean_median,
    compute_seat_vote_gap,
    compute_uniform_swing_bias,
    compute_competitiveness,
    compute_safe_seats,
)
from src.compactness import compute_compactness
from src.population import compute_population_deviation


def _json_serialize(obj):
    """Convert dict values: nan/inf -> None for valid JSON."""
    if isinstance(obj, dict):
        return {k: _json_serialize(v) for k, v in obj.items()}
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def main(map_id: str, districts_path_override: Path | None = None):
    if map_id not in config.PLANS:
        raise SystemExit(
            f"Unknown map_id: {map_id}. Choose from: {list(config.PLANS.keys())}. "
            f"Add new plans in src/config.py PLANS."
        )
    plan = config.PLANS[map_id]
    districts_path = Path(districts_path_override) if districts_path_override else plan["path"]
    district_col = plan["district_col"]
    paths = config.output_paths(map_id)

    if not districts_path.exists():
        expected = plan["path"]
        raise SystemExit(
            f"Districts file not found: {districts_path}\n"
            f"For map_id '{map_id}', config expects: {expected}\n"
            f"Either place the shapefile there (with .shx, .dbf) or run:\n"
            f"  python run_metrics_cd116.py {map_id} --districts path/to/your_cd113.shp"
        )

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Load
    blocks_gdf = load_blocks()
    cds_gdf = load_cds(path=districts_path)
    blocks_gdf = ensure_crs(blocks_gdf, epsg=26918)
    cds_gdf = ensure_crs(cds_gdf, epsg=26918)

    # 2) Assign blocks to districts
    joined = assign_blocks_to_districts(blocks_gdf, cds_gdf, district_col=district_col)
    missing = joined[district_col].isna().sum()
    pct_assigned = (1 - missing / len(joined)) * 100
    print(f"[{map_id}] Blocks assigned: {pct_assigned:.2f}% ({missing} missing)")
    if missing > 0 and paths.get("missing_blocks_csv"):
        joined[joined[district_col].isna()][["GEOID20"]].to_csv(
            paths["missing_blocks_csv"], index=False
        )

    # 3) Aggregate to districts
    district_df = aggregate_to_districts(joined, district_col=district_col)
    compact = compute_compactness(cds_gdf, id_col=district_col)
    district_df["polsby_hopper"] = district_df[district_col].map(
        compact["compactness_by_district"]
    )
    pop_dev = compute_population_deviation(district_df, id_col=district_col)
    district_df["pop_deviation_pct"] = district_df[district_col].map(
        pop_dev["population_deviation_pct_by_district"]
    )
    district_df.to_csv(paths["district_csv"], index=False)
    print(f"Wrote {paths['district_csv']}")

    # 4) Statewide and metrics
    statewide_dem = district_df["dem_total"].sum()
    statewide_rep = district_df["rep_total"].sum()
    statewide_two_party = statewide_dem + statewide_rep
    statewide_dem_share = statewide_dem / statewide_two_party if statewide_two_party else None
    n_seats = len(district_df)
    seats_dem = (district_df["winner"] == "D").sum()
    seats_rep = (district_df["winner"] == "R").sum()
    seat_share_dem = seats_dem / n_seats if n_seats else None

    metrics = {
        "map_id": map_id,
        "district_col": district_col,
        "statewide_dem": float(statewide_dem),
        "statewide_rep": float(statewide_rep),
        "statewide_two_party": float(statewide_two_party),
        "statewide_dem_share": float(statewide_dem_share) if statewide_dem_share is not None else None,
        "seats_dem": int(seats_dem),
        "seats_rep": int(seats_rep),
        "seat_share_dem": float(seat_share_dem) if seat_share_dem is not None else None,
        "efficiency_gap": compute_efficiency_gap(district_df),
        "mean_median": compute_mean_median(district_df),
        "seat_vote_gap": compute_seat_vote_gap(district_df, statewide_dem_share)
        if statewide_dem_share is not None
        else None,
        "partisan_bias_at_50": compute_uniform_swing_bias(
            district_df, statewide_dem_share, n_seats=n_seats
        )
        if statewide_dem_share is not None
        else None,
        **compute_competitiveness(district_df),
        **compute_safe_seats(district_df),
        "ideal_pop": pop_dev["ideal_pop"],
        "max_pop_deviation_pct": pop_dev["max_deviation_pct"],
        "min_pop_deviation_pct": pop_dev["min_deviation_pct"],
        "pop_deviation_range_pct": pop_dev["deviation_range_pct"],
        "pop_deviation_std_pct": pop_dev["deviation_std_pct"],
        "compactness_mean": compact["compactness_mean"],
        "compactness_min": compact["compactness_min"],
        "compactness_max": compact["compactness_max"],
        "compactness_median": compact["compactness_median"],
        "notes": "EG: positive = Democratic advantage (more R votes wasted). Uniform swing bias at 50%. Polsby-Popper: 1=circle, 0=irregular. Pop deviation % = (district_pop - ideal) / ideal * 100.",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    with open(paths["metrics_json"], "w") as f:
        json.dump(_json_serialize(metrics), f, indent=2)
    print(f"Wrote {paths['metrics_json']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run fairness metrics for a PA redistricting map. Outputs include map_id."
    )
    parser.add_argument(
        "map_id",
        nargs="?",
        default="cd116",
        help="Map/plan identifier (e.g. cd116, cd113). Must exist in config.PLANS.",
    )
    parser.add_argument(
        "--districts",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to district shapefile. Overrides config so you can use any filename (e.g. for cd113).",
    )
    args = parser.parse_args()
    main(args.map_id, districts_path_override=args.districts)
