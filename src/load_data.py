"""
Load block and CD116 layers and normalize CRS.
Ensures TRACT_GEOID20 exists on blocks (built from STATEFP20+COUNTYFP20+TRACTCE20 if missing).
"""
import geopandas as gpd
from . import config


def _ensure_tract_geoid(gdf):
    """
    If TRACT_GEOID20 is missing but STATEFP20, COUNTYFP20, TRACTCE20 exist,
    build TRACT_GEOID20 = state(2) + county(3) + tract(6) = 11 chars.
    """
    if "TRACT_GEOID20" in gdf.columns:
        return gdf
    for col in ("STATEFP20", "COUNTYFP20", "TRACTCE20"):
        if col not in gdf.columns:
            return gdf
    state = gdf["STATEFP20"].astype(str).str.zfill(2)
    county = gdf["COUNTYFP20"].astype(str).str.zfill(3)
    tract = gdf["TRACTCE20"].astype(str).str.replace(r"\.\d*$", "", regex=True).str.zfill(6)
    gdf = gdf.copy()
    gdf["TRACT_GEOID20"] = state + county + tract
    return gdf


def load_blocks(path=None):
    """Load block-level GeoPackage into a GeoDataFrame. Ensures TRACT_GEOID20 exists."""
    path = path or config.BLOCKS_PATH
    try:
        gdf = gpd.read_file(path, engine="pyogrio")
    except Exception:
        gdf = gpd.read_file(path)
    return _ensure_tract_geoid(gdf)


def load_cds(path=None):
    """Load CD116 district boundaries into a GeoDataFrame."""
    path = path or config.CD116_PATH
    try:
        gdf = gpd.read_file(path, engine="pyogrio")
    except Exception:
        # Shapefiles need .shp + .shx + .dbf (and often .prj). If .shx is missing
        # or pyogrio fails, use fiona which can be more forgiving.
        try:
            gdf = gpd.read_file(path, engine="fiona")
        except Exception:
            gdf = gpd.read_file(path)
    return gdf


def ensure_crs(gdf, epsg=26918):
    """Reproject to projected CRS if currently geographic (e.g. 4269/4326).
    If CRS is missing (e.g. shapefile without .prj), assume NAD83 (EPSG:4269) for US data."""
    if gdf.crs is None:
        # Census TIGER shapefiles are typically NAD83; assume that so we can reproject
        gdf = gdf.set_crs(epsg=4269)
    crs = gdf.crs
    if crs.is_geographic:
        return gdf.to_crs(epsg=epsg)
    return gdf
