"""
Assign each block to a district via spatial join (representative point).
"""
import geopandas as gpd


def assign_blocks_to_districts(blocks_gdf, cds_gdf, district_col="CD116FP"):
    """
    Join blocks to districts using block representative points (within district).
    Returns blocks GeoDataFrame with district_col added (e.g. CD116FP or CD113FP).
    """
    blocks_pts = blocks_gdf.copy()
    blocks_pts["geometry"] = blocks_pts.geometry.representative_point()
    cd_cols = [district_col, "geometry"]
    joined = gpd.sjoin(
        blocks_pts,
        cds_gdf[cd_cols],
        predicate="within",
        how="left",
    )
    if "index_right" in joined.columns:
        joined = joined.drop(columns=["index_right"])
    if district_col in joined.columns and joined[district_col].notna().any():
        joined[district_col] = joined[district_col].astype(str).str.zfill(2)
    return joined
