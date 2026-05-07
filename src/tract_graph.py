"""
Build tract-level graph and initial partition for GerryChain.
Tracts = nodes; adjacency = rook/queen from tract geometry.
Population and initial district assignment (from CD116) attached to nodes.
"""
from pathlib import Path
import geopandas as gpd
import pandas as pd

# Optional: libpysal for adjacency; gerrychain for Graph
try:
    import networkx as nx
except ImportError:
    nx = None
try:
    from libpysal.weights import Queen
except ImportError:
    Queen = None


def tract_geoms_from_blocks(blocks_gdf, tract_col="TRACT_GEOID20"):
    """Dissolve block polygons by tract to get one polygon per tract. CRS should be projected."""
    if tract_col not in blocks_gdf.columns:
        raise ValueError(f"Block layer missing tract column: {tract_col}")
    gdf = blocks_gdf[[tract_col, "geometry"]].copy()
    gdf[tract_col] = gdf[tract_col].astype(str)
    try:
        tract_gdf = gdf.dissolve(by=tract_col, method="coverage").reset_index()
    except TypeError:
        tract_gdf = gdf.dissolve(by=tract_col).reset_index()
    except Exception:
        gdf = gdf.copy()
        gdf["geometry"] = gdf.geometry.buffer(0)
        tract_gdf = gdf.dissolve(by=tract_col).reset_index()
    return tract_gdf


def tract_pop_from_blocks(blocks_gdf, tract_col="TRACT_GEOID20", pop_col="block_pop"):
    """Sum population by tract."""
    df = blocks_gdf[[tract_col, pop_col]].copy()
    df[tract_col] = df[tract_col].astype(str)
    return df.groupby(tract_col)[pop_col].sum().reindex(index=None)


def graph_from_tract_gdf(tract_gdf, id_col="TRACT_GEOID20"):
    """
    Build adjacency graph from tract GeoDataFrame (rook/queen via libpysal).
    Returns networkx Graph. Node attributes (e.g. population) are set by the caller.
    """
    if Queen is None:
        raise ImportError("libpysal is required: pip install libpysal")
    if nx is None:
        raise ImportError("networkx is required: pip install networkx")
    ids = tract_gdf[id_col].tolist()
    w = Queen.from_dataframe(tract_gdf, ids=ids)
    G = w.to_networkx()
    # libpysal.to_networkx() uses 0,1,2,... as node IDs; relabel to tract GEOIDs
    G = nx.relabel_nodes(G, dict(enumerate(w.id_order)))
    return G


def initial_assignment_from_cd116(tract_gdf, cds_gdf, tract_id_col="TRACT_GEOID20", district_col="CD116FP"):
    """
    Assign each tract to the CD116 district that contains its centroid.
    Returns Series: tract_id -> district (zero-padded string).
    """
    tract_gdf = tract_gdf.to_crs(cds_gdf.crs)
    centroids = tract_gdf.copy()
    centroids["geometry"] = centroids.geometry.centroid
    joined = gpd.sjoin(centroids[[tract_id_col, "geometry"]], cds_gdf[[district_col, "geometry"]], predicate="within", how="left")
    if "index_right" in joined.columns:
        joined = joined.drop(columns=["index_right"])
    joined[district_col] = joined[district_col].astype(str).str.zfill(2)
    return joined.set_index(tract_id_col)[district_col]


def build_tract_graph_and_assignment(
    blocks_gdf,
    cds_gdf,
    tract_col="TRACT_GEOID20",
    pop_col="block_pop",
    district_col="CD116FP",
):
    """
    One-shot: tract polygons from blocks, population by tract, adjacency graph,
    initial CD116 assignment. Returns (tract_gdf, G, tract_pop_series, initial_assignment).
    tract_gdf has geometry and population; G has node attr 'population' and optional 'assignment'.
    """
    tract_gdf = tract_geoms_from_blocks(blocks_gdf, tract_col=tract_col)
    tract_gdf = tract_gdf.set_index(tract_col)
    pop_series = tract_pop_from_blocks(blocks_gdf, tract_col=tract_col, pop_col=pop_col)
    tract_gdf["population"] = tract_gdf.index.map(pop_series).fillna(0).astype(int)
    tract_gdf = tract_gdf.reset_index()
    G = graph_from_tract_gdf(tract_gdf, id_col=tract_col)
    # Node attributes: population (and optionally assignment)
    for _, row in tract_gdf.iterrows():
        n = row[tract_col]
        if G.has_node(n):
            G.nodes[n]["population"] = row["population"]
    initial = initial_assignment_from_cd116(tract_gdf, cds_gdf, tract_id_col=tract_col, district_col=district_col)
    for n in G.nodes():
        G.nodes[n]["assignment"] = initial.get(n, initial.get(str(n), None))
    return tract_gdf, G, pop_series, initial
