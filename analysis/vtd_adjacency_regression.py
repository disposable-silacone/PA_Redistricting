"""
VTD adjacency regression: how likely are nearby VTDs to vote similarly?

Uses data/Final Working VTD With Vote Totals.csv (congressional vote proportions).
VTDs have no polygon geometry in the CSV, so adjacency is defined by K-nearest
neighbors of VTD centroids (INTPTLAT20, INTPTLON20) in projected space.
Run from project root: python analysis/vtd_adjacency_regression.py
"""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point

from src import config

try:
    from libpysal.weights import KNN
except ImportError:
    KNN = None
try:
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools.tools import add_constant
except ImportError:
    OLS = None
    add_constant = None
try:
    from esda import Moran
except ImportError:
    Moran = None

# Default path to VTD CSV (relative to project root)
DEFAULT_VTD_CSV = PROJECT_ROOT / "data" / "Final Working VTD With Vote Totals.csv"


def _load_vtd_csv(path):
    """Load VTD CSV and derive two-party dem_share; return DataFrame with geometry."""
    df = pd.read_csv(path, dtype={"GEOID20": str, "COUNTYFP20": str})
    # Use dem_votes/rep_votes when present, else dem_votes_2/rep_votes_2
    dem = df["dem_votes"].fillna(df["dem_votes_2"])
    rep = df["rep_votes"].fillna(df["rep_votes_2"])
    df["two_party"] = dem + rep
    df["dem_share"] = np.where(df["two_party"] > 0, dem / df["two_party"], np.nan)
    df = df.loc[df["two_party"] > 0].dropna(subset=["dem_share"]).copy()
    return df


def _vtd_to_geodataframe(df):
    """Build GeoDataFrame from VTD CSV: point geometry from INTPTLAT20/INTPTLON20, project to UTM."""
    geom = [Point(lon, lat) for lon, lat in zip(df["INTPTLON20"], df["INTPTLAT20"])]
    gdf = gpd.GeoDataFrame(df, geometry=geom, crs="EPSG:4326")
    return gdf.to_crs("EPSG:26918")


def _build_analysis_df(vtd_gdf, w, ids):
    """One row per VTD: dem_share_vtd, mean_neighbor_dem_share, etc."""
    vtd_idx = vtd_gdf.set_index(vtd_gdf["GEOID20"].astype(str))
    share_by_id = vtd_idx["dem_share"]
    rows = []
    for i, geoid in enumerate(ids):
        if i % 2000 == 0 and i:
            print(f"  Processing VTD {i:,} / {len(ids):,}...")
        neighbors = w.neighbors.get(geoid, [])
        if not neighbors:
            continue
        neighbor_shares = [share_by_id.get(n) for n in neighbors]
        neighbor_shares = [x for x in neighbor_shares if pd.notna(x)]
        if not neighbor_shares:
            continue
        row = vtd_idx.loc[geoid]
        rows.append({
            "GEOID20": geoid,
            "dem_share_vtd": row["dem_share"],
            "mean_neighbor_dem_share": np.mean(neighbor_shares),
            "two_party_vote": row["two_party"],
            "n_neighbors": len(neighbor_shares),
            "COUNTYFP20": row.get("COUNTYFP20", ""),
            "NAME20": row.get("NAME20", ""),
        })
    return pd.DataFrame(rows)


def _run_regression(df):
    """OLS and optional cluster-robust SE by county; print summaries.

    Returns the fitted OLS model.
    """
    if OLS is None or add_constant is None:
        raise SystemExit("statsmodels is required: pip install statsmodels")
    y = df["dem_share_vtd"]
    X = add_constant(df[["mean_neighbor_dem_share"]])
    model = OLS(y, X).fit()
    print("\n--- OLS: dem_share_vtd ~ mean_neighbor_dem_share ---")
    print(model.summary())
    if "COUNTYFP20" in df.columns and df["COUNTYFP20"].notna().all() and df["COUNTYFP20"].astype(str).str.len().gt(0).all():
        try:
            model_cl = model.get_robustcov_results(
                cov_type="cluster", cov_kwds={"groups": df["COUNTYFP20"]}
            )
            print("\n--- Same model, cluster-robust SE (by county) ---")
            print(model_cl.summary())
        except Exception as e:
            print(f"\nCluster-robust SE skipped: {e}")
    return model


def _write_plot(df, out_dir):
    """Scatter: VTD dem_share vs mean neighbor dem_share."""
    try:
        import matplotlib.pyplot as plt
        plot_path = out_dir / "vtd_adjacency_scatter.png"
        plt.figure(figsize=(6, 5))
        plt.scatter(
            df["mean_neighbor_dem_share"],
            df["dem_share_vtd"],
            alpha=0.3,
            s=8,
        )
        plt.xlabel("Mean neighbor Democratic share")
        plt.ylabel("VTD Democratic share")
        plt.title("VTD vs. mean neighbor Dem share (k=8 nearest VTDs)")
        # Vote shares are in [0,1]; lock axes to that range so the origin is at 0,0.
        plt.xlim(0, 1)
        plt.ylim(0, 1)
        plt.plot([0, 1], [0, 1], "k--", alpha=0.5, label="y=x")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plot_path, dpi=150)
        plt.close()
        print(f"Wrote {plot_path}")
    except Exception as e:
        print(f"Plot skipped: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="VTD-level adjacency regression (vote similarity).")
    parser.add_argument(
        "--vtd-csv",
        type=Path,
        default=DEFAULT_VTD_CSV,
        help="Path to VTD CSV with vote totals (default: data/Final Working VTD With Vote Totals.csv)",
    )
    parser.add_argument(
        "-k",
        type=int,
        default=8,
        metavar="K",
        help="Number of nearest-neighbor VTDs (default: 8)",
    )
    args = parser.parse_args()

    out_dir = config.OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.vtd_csv.exists():
        raise SystemExit(f"VTD CSV not found: {args.vtd_csv}")

    print("Loading VTD data...")
    vtd_df = _load_vtd_csv(args.vtd_csv)
    print(f"  VTDs with valid two-party vote: {len(vtd_df):,}")

    vtd_gdf = _vtd_to_geodataframe(vtd_df)
    ids = vtd_gdf["GEOID20"].astype(str).tolist()

    if KNN is None:
        raise SystemExit("libpysal is required: pip install libpysal")
    print(f"Building VTD adjacency (KNN, k={args.k})...")
    w = KNN.from_dataframe(vtd_gdf, ids=ids, k=args.k)
    print(f"  Done. {w.n} units, {w.nonzero} links.")

    # Global Moran's I on VTD Democratic share
    moran_i = None
    moran_p = None
    if Moran is None:
        print("esda is not installed; skipping Moran's I (pip install esda).")
    else:
        try:
            y = vtd_gdf["dem_share"].to_numpy()
            mi = Moran(y, w)
            moran_i = float(mi.I)
            moran_p = float(mi.p_sim)
            print(f"\nGlobal Moran's I: I = {moran_i:.4f}, p_sim = {moran_p:.4g}")
        except Exception as e:
            print(f"\nMoran's I computation skipped due to error: {e}")

    df = _build_analysis_df(vtd_gdf, w, ids)
    print(f"  VTDs with at least one neighbor with valid share: {len(df):,}")

    model = _run_regression(df)

    # Per-VTD dataset
    csv_path = out_dir / "vtd_adjacency_regression_data.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nWrote {csv_path}")
    _write_plot(df, out_dir)

    # Summary row combining regression and Moran's I
    summary = {
        "k_neighbors": args.k,
        "n_vtds": int(len(df)),
        "reg_intercept": float(model.params.get("const", float("nan"))),
        "reg_slope_mean_neighbor_dem_share": float(
            model.params.get("mean_neighbor_dem_share", float("nan"))
        ),
        "reg_r2": float(model.rsquared),
        "moran_I": moran_i,
        "moran_p_sim": moran_p,
    }
    summary_df = pd.DataFrame([summary])
    summary_path = out_dir / "vtd_adjacency_regression_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
