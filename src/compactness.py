"""
District shape compactness metrics.
Geometry must be in a projected CRS (e.g. EPSG:26918) so area and perimeter are in consistent units.
"""
import math
import geopandas as gpd
import pandas as pd


def _polsby_hopper(area, perimeter):
    """Polsby-Popper = (4 * pi * area) / perimeter^2. 1 = circle, 0 = very irregular."""
    if perimeter is None or perimeter <= 0 or area is None or area < 0:
        return float("nan")
    return (4 * math.pi * area) / (perimeter ** 2)


def compute_compactness(cds_gdf, id_col="CD116FP"):
    """
    Compute Polsby-Popper compactness per district.
    Districts are dissolved by id_col so multi-part districts become one polygon each.
    Returns dict with per-district compactness and summary stats.
    """
    gdf = cds_gdf[[id_col, "geometry"]].copy()
    # Normalize ID to string for consistency
    gdf[id_col] = gdf[id_col].astype(str).str.zfill(2)
    dissolved = gdf.dissolve(by=id_col).reset_index()
    dissolved["_area"] = dissolved.geometry.area
    dissolved["_perimeter"] = dissolved.geometry.length
    dissolved["polsby_hopper"] = dissolved.apply(
        lambda r: _polsby_hopper(r["_area"], r["_perimeter"]), axis=1
    )
    comp = dissolved[[id_col, "polsby_hopper"]].set_index(id_col)["polsby_hopper"]
    valid = comp.dropna()
    return {
        "compactness_by_district": comp.to_dict(),
        "compactness_mean": float(valid.mean()) if len(valid) else None,
        "compactness_min": float(valid.min()) if len(valid) else None,
        "compactness_max": float(valid.max()) if len(valid) else None,
        "compactness_median": float(valid.median()) if len(valid) else None,
    }
