"""
Block adjacency regression: how likely are adjacent blocks to vote similarly?

Uses data/block_level_data.gpkg: for each block we compute mean neighbor
Democratic share (Queen adjacency) and regress block dem_share on that.
Run from project root: python analysis/block_adjacency_regression.py
"""
from pathlib import Path
import sys

# Allow importing src from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np

from src import load_data, config

# Optional: libpysal for Queen adjacency, statsmodels for OLS
try:
    from libpysal.weights import Queen
except ImportError:
    Queen = None
try:
    import statsmodels.api as sm
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools.tools import add_constant
except ImportError:
    sm = None
    OLS = None
    add_constant = None


def _prepare_blocks(blocks_path):
    """Load blocks, ensure CRS, derive dem_share; return filtered GeoDataFrame."""
    blocks = load_data.load_blocks(blocks_path)
    blocks = load_data.ensure_crs(blocks, epsg=26918)
    for c in ["GEOID20", "block_pop", "dem_block", "rep_block", "geometry"]:
        if c not in blocks.columns:
            raise SystemExit(f"Block layer missing required column: {c}")
    blocks["two_party"] = blocks["dem_block"] + blocks["rep_block"]
    blocks["dem_share"] = np.where(
        blocks["two_party"] > 0,
        blocks["dem_block"] / blocks["two_party"],
        np.nan,
    )
    blocks = blocks.loc[blocks["two_party"] > 0].copy()
    blocks = blocks.dropna(subset=["dem_share"])
    return blocks


def _build_analysis_df(blocks, w, ids):
    """One row per block: dem_share_block, mean_neighbor_dem_share, etc."""
    blocks_idx = blocks.set_index(blocks["GEOID20"].astype(str))
    share_by_id = blocks_idx["dem_share"]
    rows = []
    for i, geoid in enumerate(ids):
        if i % 50_000 == 0 and i:
            print(f"  Processing block {i:,} / {len(ids):,}...")
        neighbors = w.neighbors.get(geoid, [])
        if not neighbors:
            continue
        neighbor_shares = [share_by_id.get(n) for n in neighbors]
        neighbor_shares = [x for x in neighbor_shares if pd.notna(x)]
        if not neighbor_shares:
            continue
        row = blocks_idx.loc[geoid]
        rows.append({
            "GEOID20": geoid,
            "dem_share_block": row["dem_share"],
            "mean_neighbor_dem_share": np.mean(neighbor_shares),
            "block_pop": row["block_pop"],
            "two_party_vote": row["two_party"],
            "n_neighbors": len(neighbor_shares),
            "TRACT_GEOID20": row.get("TRACT_GEOID20", ""),
        })
    return pd.DataFrame(rows)


def _run_regression(df):
    """OLS and optional cluster-robust SE; print summaries."""
    if OLS is None or add_constant is None:
        raise SystemExit("statsmodels is required: pip install statsmodels")
    y = df["dem_share_block"]
    X = add_constant(df[["mean_neighbor_dem_share"]])
    model = OLS(y, X).fit()
    print("\n--- OLS: dem_share_block ~ mean_neighbor_dem_share ---")
    print(model.summary())
    if "TRACT_GEOID20" in df.columns and df["TRACT_GEOID20"].notna().all():
        try:
            model_cl = model.get_robustcov_results(
                cov_type="cluster", cov_kwds={"groups": df["TRACT_GEOID20"]}
            )
            print("\n--- Same model, cluster-robust SE (by tract) ---")
            print(model_cl.summary())
        except Exception as e:
            print(f"\nCluster-robust SE skipped: {e}")


def _write_plot(df, out_dir):
    """Scatter: block dem_share vs mean neighbor dem_share (sample if huge)."""
    try:
        import matplotlib.pyplot as plt
        plot_path = out_dir / "block_adjacency_scatter.png"
        n_plot = min(50_000, len(df))
        sample = df.sample(n=n_plot, random_state=42) if len(df) > n_plot else df
        plt.figure(figsize=(6, 5))
        plt.scatter(
            sample["mean_neighbor_dem_share"],
            sample["dem_share_block"],
            alpha=0.15,
            s=4,
        )
        plt.xlabel("Mean neighbor Democratic share")
        plt.ylabel("Block Democratic share")
        plt.title("Block vs. mean neighbor Dem share (adjacent blocks)")
        plt.axis("equal")
        xlim = plt.xlim()
        plt.plot(xlim, xlim, "k--", alpha=0.5, label="y=x")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plot_path, dpi=150)
        plt.close()
        print(f"Wrote {plot_path}")
    except Exception as e:
        print(f"Plot skipped: {e}")


def main():
    out_dir = config.OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading blocks...")
    blocks = _prepare_blocks(config.BLOCKS_PATH)
    print(f"  Blocks with valid two-party vote: {len(blocks):,}")

    if Queen is None:
        raise SystemExit("libpysal is required: pip install libpysal")
    print("Building block adjacency (Queen)...")
    ids = blocks["GEOID20"].astype(str).tolist()
    w = Queen.from_dataframe(blocks, ids=ids)
    print(f"  Done. {w.n} units, {w.nonzero} links.")

    df = _build_analysis_df(blocks, w, ids)
    print(f"  Blocks with at least one neighbor with valid share: {len(df):,}")

    _run_regression(df)

    csv_path = out_dir / "block_adjacency_regression_data.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nWrote {csv_path}")
    _write_plot(df, out_dir)


if __name__ == "__main__":
    main()
