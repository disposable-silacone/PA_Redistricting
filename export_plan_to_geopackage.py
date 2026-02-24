"""
Export a single saved plan (tract→district CSV) to a GeoPackage of district polygons for QGIS.

Usage:
  python export_plan_to_geopackage.py outputs/saved_plans/plan_000100.csv --out outputs/plan_000100.gpkg
  python export_plan_to_geopackage.py outputs/saved_plans/plan_000100.csv

If --out is omitted, writes to outputs/ensemble_plans/<stem of csv>.gpkg
"""
import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd

from src import config
from src.load_data import load_blocks, ensure_crs
from src.tract_graph import tract_geoms_from_blocks, tract_pop_from_blocks


def main():
    parser = argparse.ArgumentParser(description="Export a plan CSV to district polygons GeoPackage for QGIS.")
    parser.add_argument("plan_csv", type=Path, help="Path to plan CSV (tract_geoid, district_id)")
    parser.add_argument("--out", type=Path, default=None, help="Output .gpkg path")
    args = parser.parse_args()

    plan_csv = Path(args.plan_csv)
    if not plan_csv.exists():
        raise SystemExit(f"Plan CSV not found: {plan_csv}")

    assignment = pd.read_csv(plan_csv, dtype={"tract_geoid": str})
    if "tract_geoid" not in assignment.columns or "district_id" not in assignment.columns:
        raise SystemExit("Plan CSV must have columns: tract_geoid, district_id")
    assignment["tract_geoid"] = assignment["tract_geoid"].astype(str)
    tract_to_dist = assignment.set_index("tract_geoid")["district_id"].astype(str).str.zfill(2).to_dict()

    blocks_gdf = load_blocks()
    blocks_gdf = ensure_crs(blocks_gdf, epsg=26918)
    tract_gdf = tract_geoms_from_blocks(blocks_gdf, tract_col="TRACT_GEOID20")
    if not hasattr(tract_gdf, "geometry") or tract_gdf.geometry.is_empty.all():
        raise SystemExit("Tract layer has no geometry. Check block_level_data.gpkg has polygon geometry.")
    tract_gdf["population"] = tract_gdf["TRACT_GEOID20"].map(
        tract_pop_from_blocks(blocks_gdf, tract_col="TRACT_GEOID20")
    ).fillna(0)

    gdf = tract_gdf[["TRACT_GEOID20", "geometry"]].copy()
    gdf["district_id"] = gdf["TRACT_GEOID20"].astype(str).map(tract_to_dist)
    gdf = gdf.dropna(subset=["district_id"])
    if gdf.empty:
        raise SystemExit(
            "No tracts matched the plan CSV (tract_geoid mismatch?). "
            "Plan CSV tract_geoid must match TRACT_GEOID20 in your block layer (e.g. 42001030101)."
        )
    dissolved = gdf.dissolve(by="district_id").reset_index()
    dissolved = dissolved.set_geometry("geometry")
    if dissolved.geometry.is_empty.any():
        dissolved = dissolved[~dissolved.geometry.is_empty].copy()

    out_path = args.out or config.OUTPUT_DIR / "ensemble_plans" / f"{plan_csv.stem}.gpkg"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dissolved.to_crs(4326).to_file(out_path, driver="GPKG", layer="districts")
    print(f"Wrote {out_path} ({len(dissolved)} district polygons)")


if __name__ == "__main__":
    main()
