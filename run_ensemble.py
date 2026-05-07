"""
Generate an ensemble of ~3,000 district plans with GerryChain (ReCom), score each
with your existing metrics, and write outputs/ensemble_metrics.csv.

Prerequisites:
  - Tract column in block layer (e.g. TRACT_GEOID20)
  - pip install gerrychain networkx libpysal

Usage:
  python run_ensemble.py --steps 3000 --epsilon 0.01
  python run_ensemble.py --steps 500 --epsilon 0.02 --out outputs/ensemble_small.csv
  python run_ensemble.py --steps 3000 --num-districts 17 --random-start --out outputs/ensemble_metrics_17.csv

For 17 districts (post-2020 PA), use --num-districts 17 and --random-start (CD116 has 18).
Use a different --out (e.g. outputs/ensemble_metrics_17.csv) so 17- and 18-district runs stay separate.

See SIMULATION_DESIGN.md for full pipeline and 2024 validation.
"""
import argparse
import csv
from pathlib import Path

import pandas as pd

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


def partition_to_district_df(blocks_gdf, tract_assignment, district_col="district_id"):
    """
    tract_assignment: dict or Series tract_geoid -> district_id (e.g. "01".."18").
    Blocks must have tract column (e.g. TRACT_GEOID20).
    Returns district_df with same columns as aggregate_to_districts().
    """
    tract_col = "TRACT_GEOID20"  # or detect from blocks_gdf
    if tract_col not in blocks_gdf.columns:
        raise ValueError(f"Block layer needs tract column {tract_col}")
    blocks = blocks_gdf.copy()
    blocks[district_col] = blocks[tract_col].astype(str).map(tract_assignment)
    blocks = blocks.dropna(subset=[district_col])
    return aggregate_to_districts(blocks, district_col=district_col)


def score_partition(blocks_gdf, tract_gdf, partition_assignment, district_col="district_id"):
    """
    partition_assignment: dict tract_geoid -> district_id (strings "01".."18").
    Returns dict of metrics (efficiency_gap, mean_median, compactness_mean, ...).
    """
    district_df = partition_to_district_df(blocks_gdf, partition_assignment, district_col=district_col)
    if len(district_df) == 0:
        return None
    statewide_dem = district_df["dem_total"].sum()
    statewide_rep = district_df["rep_total"].sum()
    two_party = statewide_dem + statewide_rep
    statewide_dem_share = statewide_dem / two_party if two_party else None
    n_seats = len(district_df)
    compact_gdf = tract_gdf.copy()
    tract_id_col = "TRACT_GEOID20" if "TRACT_GEOID20" in tract_gdf.columns else tract_gdf.columns[0]
    compact_gdf[district_col] = compact_gdf[tract_id_col].astype(str).map(partition_assignment)
    compact_gdf = compact_gdf.dropna(subset=[district_col])
    # Dissolve tracts by district for compactness
    from geopandas import GeoDataFrame
    try:
        dissolved = compact_gdf.dissolve(by=district_col, method="coverage").reset_index()
    except TypeError:
        dissolved = compact_gdf.dissolve(by=district_col).reset_index()
    except Exception:
        compact_gdf = compact_gdf.copy()
        compact_gdf["geometry"] = compact_gdf.geometry.buffer(0)
        dissolved = compact_gdf.dissolve(by=district_col).reset_index()
    compact_metrics = compute_compactness(
        dissolved.rename(columns={district_col: "district_id"}),
        id_col="district_id",
    )
    pop_dev = compute_population_deviation(district_df, id_col=district_col)
    metrics = {
        "efficiency_gap": compute_efficiency_gap(district_df),
        "mean_median": compute_mean_median(district_df),
        "seat_vote_gap": compute_seat_vote_gap(district_df, statewide_dem_share) if statewide_dem_share is not None else None,
        "partisan_bias_at_50": compute_uniform_swing_bias(district_df, statewide_dem_share, n_seats=n_seats) if statewide_dem_share is not None else None,
        "seats_dem": int((district_df["winner"] == "D").sum()),
        "seats_rep": int((district_df["winner"] == "R").sum()),
        "competitive_count": compute_competitiveness(district_df)["competitive_count"],
        "compactness_mean": compact_metrics["compactness_mean"],
        "pop_deviation_range_pct": pop_dev["deviation_range_pct"],
    }
    return metrics


def _export_plan_gpkg(tract_gdf, tract_to_dist, out_path, district_col="district_id"):
    """Write one plan as a GeoPackage of district polygons (tracts dissolved by district) for QGIS."""
    tract_id_col = "TRACT_GEOID20" if "TRACT_GEOID20" in tract_gdf.columns else tract_gdf.columns[0]
    gdf = tract_gdf.copy()
    gdf[district_col] = gdf[tract_id_col].astype(str).map(tract_to_dist)
    gdf = gdf.dropna(subset=[district_col])
    try:
        dissolved = gdf.dissolve(by=district_col, method="coverage").reset_index()
    except TypeError:
        dissolved = gdf.dissolve(by=district_col).reset_index()
    except Exception:
        gdf = gdf.copy()
        gdf["geometry"] = gdf.geometry.buffer(0)
        dissolved = gdf.dissolve(by=district_col).reset_index()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dissolved.to_crs(4326).to_file(out_path, driver="GPKG")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generate ensemble of plans and score with fairness metrics.")
    parser.add_argument("--steps", type=int, default=3000, help="Number of ReCom steps (plans) to generate")
    parser.add_argument("--epsilon", type=float, default=0.01, help="Population tolerance (e.g. 0.01 = ±1%%)")
    parser.add_argument("--out", type=Path, default=None, help="Output CSV path (default: outputs/ensemble_metrics.csv)")
    parser.add_argument("--save-plans-every", type=int, default=0, help="Save tract-to-district CSV every N plans (0 = do not save)")
    parser.add_argument("--export-geopackage", type=int, default=0, metavar="N", help="Export every Nth plan as district polygons to outputs/ensemble_plans/plan_*.gpkg for QGIS (0 = do not export)")
    parser.add_argument("--random-start", action="store_true", help="Start from a random partition instead of CD116 for much more variation (first plan can look very different)")
    parser.add_argument("--num-districts", type=int, default=18, metavar="N", help="Number of districts (default: 18). For 17 (post-2020 PA) use --num-districts 17 and --random-start.")
    args = parser.parse_args()

    num_districts = args.num_districts
    if num_districts != 18 and not args.random_start:
        raise SystemExit(
            "CD116 has 18 districts. For --num-districts 17 (or any value other than 18) you must use --random-start.\n"
            "Example: python run_ensemble.py --num-districts 17 --random-start --out outputs/ensemble_metrics_17.csv --steps 3000"
        )

    out_path = args.out or config.OUTPUT_DIR / "ensemble_metrics.csv"
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if num_districts != 18:
        print(f"Generating {num_districts}-district plans (using random initial partition).")

    # 1) Load data and build tract graph (and optional CD116 initial assignment for 18 districts) (and optional CD116 initial assignment)
    blocks_gdf = load_blocks()
    blocks_gdf = ensure_crs(blocks_gdf, epsg=26918)
    try:
        from src.tract_graph import build_tract_graph_and_assignment
        if args.random_start or num_districts != 18:
            # Random start, or 17 districts (CD116 has 18 so we must use random partition)
            from src.tract_graph import tract_geoms_from_blocks, tract_pop_from_blocks, graph_from_tract_gdf
            tract_gdf = tract_geoms_from_blocks(blocks_gdf, tract_col="TRACT_GEOID20")
            tract_gdf = tract_gdf.set_index("TRACT_GEOID20")
            tract_gdf["population"] = tract_gdf.index.map(
                tract_pop_from_blocks(blocks_gdf, tract_col="TRACT_GEOID20")
            ).fillna(0).astype(int)
            tract_gdf = tract_gdf.reset_index()
            G = graph_from_tract_gdf(tract_gdf, id_col="TRACT_GEOID20")
            for _, row in tract_gdf.iterrows():
                n = row["TRACT_GEOID20"]
                if G.has_node(n):
                    G.nodes[n]["population"] = row["population"]
            initial_assignment = None  # will use random partition
        else:
            cds_gdf = load_cds(path=config.PLANS["cd116"]["path"])
            cds_gdf = ensure_crs(cds_gdf, epsg=26918)
            tract_gdf, G, _, initial_assignment = build_tract_graph_and_assignment(
                blocks_gdf, cds_gdf,
                tract_col="TRACT_GEOID20",
                district_col="CD116FP",
            )
    except Exception as e:
        raise SystemExit(
            f"Tract graph build failed (do you have TRACT_GEOID20 in blocks?): {e}\n"
            "See SIMULATION_DESIGN.md and src/tract_graph.py."
        ) from e

    # 2) GerryChain ReCom chain
    try:
        from gerrychain import Graph, Partition
        from gerrychain.constraints import contiguous
        from gerrychain.proposals import recom
        from gerrychain import MarkovChain
        from gerrychain.accept import always_accept
        from gerrychain.updaters import Tally
        from gerrychain.tree import bipartition_tree
        from functools import partial
    except ImportError as e:
        raise SystemExit(
            "GerryChain not installed. Run: pip install gerrychain networkx libpysal\n"
            "See SIMULATION_DESIGN.md."
        ) from e

    # GerryChain Graph.from_networkx takes only the graph; node attributes stay on G.
    try:
        gc_graph = Graph.from_networkx(G)
    except Exception:
        # Fallback: build from GeoDataFrame (index = node id; adjacency is keyword)
        gdf_for_graph = tract_gdf.set_index("TRACT_GEOID20").copy()
        gdf_for_graph["assignment"] = initial_assignment if initial_assignment is not None else 0
        gc_graph = Graph.from_geodataframe(
            gdf_for_graph, adjacency="queen", cols_to_add=["population", "assignment"]
        )

    ideal_pop = tract_gdf["population"].sum() / num_districts
    # More attempts and tree restarts so ReCom finds balanced splits (tract-level is chunky)
    bipartition_method = partial(bipartition_tree, max_attempts=50_000, node_repeats=10)
    proposal = partial(
        recom,
        pop_col="population",
        pop_target=ideal_pop,
        epsilon=args.epsilon,
        node_repeats=10,
        method=bipartition_method,
    )
    if args.random_start or num_districts != 18:
        # Random initial partition (required for 17 districts; CD116 has 18)
        initial_partition = Partition.from_random_assignment(
            gc_graph,
            n_parts=num_districts,
            epsilon=args.epsilon,
            pop_col="population",
            updaters={"population": Tally("population")},
        )
    else:
        # Start from current CD116 map (18 districts, small local variation)
        initial_partition = Partition(
            gc_graph,
            assignment="assignment",
            updaters={"population": Tally("population")},
        )
    chain = MarkovChain(
        proposal=proposal,
        constraints=[contiguous],
        accept=always_accept,
        initial_state=initial_partition,
        total_steps=args.steps,
    )

    # 3) Resume plan_id from existing metrics CSV so batches append instead of overwrite
    starting_plan_id = 0
    if out_path.exists() and out_path.stat().st_size > 0:
        try:
            existing = pd.read_csv(out_path, usecols=["plan_id"])
            starting_plan_id = int(existing["plan_id"].max()) + 1
        except Exception:
            pass
    if starting_plan_id > 0:
        print(f"Appending to existing metrics (next plan_id: {starting_plan_id})")

    # 4) Run chain and write one row per plan
    fieldnames = [
        "plan_id", "efficiency_gap", "mean_median", "seat_vote_gap", "partisan_bias_at_50",
        "seats_dem", "seats_rep", "competitive_count", "compactness_mean", "pop_deviation_range_pct",
    ]
    write_header = starting_plan_id == 0
    with open(out_path, "a" if starting_plan_id > 0 else "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for i, partition in enumerate(chain):
            assignment = partition.assignment
            tract_to_dist = {str(n): str(assignment[n]).zfill(2) for n in partition.graph.nodes()}
            row = score_partition(blocks_gdf, tract_gdf, tract_to_dist)
            if row is None:
                continue
            plan_id = starting_plan_id + i
            row["plan_id"] = plan_id
            writer.writerow(row)
            if (i + 1) % 100 == 0:
                print(f"Plans scored: {i + 1}/{args.steps}")
            if args.save_plans_every and (i + 1) % args.save_plans_every == 0:
                plans_dir = config.OUTPUT_DIR / ("saved_plans" if num_districts == 18 else f"saved_plans_{num_districts}")
                save_path = plans_dir / f"plan_{plan_id:06d}.csv"
                save_path.parent.mkdir(parents=True, exist_ok=True)
                pd.DataFrame(list(tract_to_dist.items()), columns=["tract_geoid", "district_id"]).to_csv(save_path, index=False)
            if args.export_geopackage and ((i + 1) % args.export_geopackage == 0 or i == 0):
                gpkg_dir = config.OUTPUT_DIR / ("ensemble_plans" if num_districts == 18 else f"ensemble_plans_{num_districts}")
                _export_plan_gpkg(tract_gdf, tract_to_dist, gpkg_dir / f"plan_{plan_id:06d}.gpkg")
    print(f"Wrote {out_path} (plan_id {starting_plan_id}..{starting_plan_id + args.steps - 1})")


if __name__ == "__main__":
    main()
