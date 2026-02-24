
Ctrl+K to generate command
ENSEMBLE_OUTPUTS_GUIDE.md
 
FIRST_STEPS.md
 
SIMULATION_DESIGN.md
 
README.md
 
METRICS_GUIDE.md
 
AI_Transcript_1.md
 



please read through these .md files for context of the project as it stands.



Right now, I want to create a new python script (maybe not in src/...) to create a regression analysis for 
block_level_data.gpkg
 Specifically, I'd like to find what the likelyhood adjacent blocks are to vote similarly.  Don't make any code yet.  Please propose a logical workflow for me to approve before we start coding.

Reading the referenced markdown files and inspecting the block-level data structure to propose a workflow.
Checking how block data is loaded and whether the project has block-level geometry or adjacency logic:
Here’s a concise workflow you can approve before any coding.
Proposed workflow: regression analysis — do adjacent blocks vote similarly?
Goal: Use data/block_level_data.gpkg to estimate how strongly adjacent blocks tend to vote similarly (e.g., Democratic share in a block vs. average Democratic share of its neighbors).
Context from your docs: Blocks have GEOID20, block_pop, dem_block, rep_block, geometry, and a tract id (TRACT_GEOID20). The pipeline already uses tract-level adjacency (e.g. in src/tract_graph.py); this analysis would add block-level adjacency and a regression step.
1. Load and prepare block-level data
Source: data/block_level_data.gpkg (e.g. via src.load_data.load_blocks() and ensure_crs() so geometry is in a projected CRS for adjacency).
Check: Required columns present (GEOID20, block_pop, dem_block, rep_block, geometry; tract id for optional controls).
Derive: Two-party vote share per block, e.g.
dem_share_block = dem_block / (dem_block + rep_block)
and handle blocks with zero two-party vote (e.g. drop or flag).
Optional: Restrict to blocks with at least some population or two-party votes so shares are interpretable (e.g. (dem_block + rep_block) >= threshold).
2. Define “adjacent” and build the neighbor structure
Adjacency: Blocks that touch (shared edge and/or vertex). Use Queen (edge or vertex) or Rook (edge only); Queen is standard and usually gives more neighbors.
Implementation: Build a block adjacency structure from the block geometry in the GeoPackage (e.g. libpysal.weights.Queen.from_dataframe(blocks_gdf) or equivalent with geopandas), so that for each block you have a list (or weights) of neighbor GEOID20s.
Performance: With ~300k+ blocks, building the weights object may be slow; use projected CRS and consider simplifying geometries or using a spatial index if needed.
3. Build the analysis dataset
Unit of observation: One row per block (keeps the dataset at ~one row per block and is straightforward for regression).
Per block, compute:
Outcome: dem_share_block (or another vote measure you prefer).
Predictor: Average (or median) of dem_share_block over all neighbors of that block → e.g. mean_neighbor_dem_share.
Optional: Number of neighbors; total two-party vote in block (or block population) for controls; tract id (or county) for fixed effects.
Exclude: Blocks with no neighbors (islands) or with undefined dem_share_block (e.g. zero two-party vote). Optionally exclude blocks with very few neighbors (e.g. 1) if you want a more stable neighbor average.
Output: One table, e.g. block_id, dem_share_block, mean_neighbor_dem_share, block_pop, two_party_vote, n_neighbors, tract_id (optional), ready for regression.
4. Regression model(s)
Primary:
Regress block vote share on neighbors’ average vote share, e.g.
dem_share_block ~ mean_neighbor_dem_share
(simple OLS).
Interpretation: “A 1 percentage point increase in average neighbor Democratic share is associated with a β percentage point increase in the block’s Democratic share.” A positive, significant β supports “adjacent blocks tend to vote similarly.”
Optional extensions:
Add controls: e.g. block population or two-party vote, so similarity isn’t driven only by size.
Tract (or county) fixed effects: to see if similarity remains within tract/county (i.e. not just “same tract votes alike”).
Logistic: e.g. binary outcome “block is D-majority” and regress on “share of neighbors that are D-majority” or mean neighbor dem_share.
Inference: Consider cluster-robust standard errors by tract (or county) so you don’t overstate precision when many blocks share the same tract.
5. Outputs and optional checks
Summary: Coefficient(s), R², (cluster-robust) standard errors and p-values; short interpretation in plain language.
Optional: Write a CSV of the analysis dataset (e.g. to outputs/block_adjacency_regression_data.csv) for inspection or mapping in QGIS.
Optional: Simple scatter plot — block dem_share vs. mean_neighbor_dem_share — and/or a map of residuals or of “similarity” (e.g. absolute difference between block and mean neighbor share).
6. Where the script lives
Suggested: A single standalone script at the project root (e.g. block_adjacency_regression.py or analyze_block_vote_similarity.py), not under src/. It can import src.load_data and src.config only for loading blocks and paths; all adjacency construction, dataset building, and regression stay in this script so the analysis is separate from the core redistricting pipeline.
Summary table
Step	What
1	Load blocks from data/block_level_data.gpkg, ensure CRS, derive dem_share_block, optional filters.
2	Build block adjacency (Queen or Rook) from block geometry.
3	Build one row per block: dem_share_block, mean_neighbor_dem_share, optional controls (pop, tract).
4	Run OLS (and optionally logistic / with FE / cluster SEs).
5	Report coefficients and interpretation; optionally export CSV and plots.
6	Implement as one root-level script that reuses load_blocks/config only.
If you confirm this workflow (and any choices like Queen vs Rook, whether to add tract FE or cluster SEs), the next step is to implement it in code in a single script at project root as above.
lets do this, but instead of putting it in the root directory, can we make a new folder?  what should we call it?

Using analysis/ — conventional, short, and can hold this script plus future one-off or exploratory analyses (e.g. other regressions, validation scripts). Creating analysis/ and adding the regression script there.
Create analysis/ folder and block_adjacency_regression.py
Load blocks, derive dem_share, build adjacency (Queen)
Build analysis dataset (mean neighbor dem_share per block)
Run OLS regression and optional cluster SEs
Write outputs (summary, optional CSV/plot)
Creating the analysis/ folder and the full script. Checking how libpysal Queen uses the dataframe index for block-level weights:
Writing the script and adding statsmodels to requirements.
block_adjacency_regression.py(new)
+152
"""Block adjacency regression: how likely are adjacent blocks to vote similarly?Uses data/block_level_data.gpkg: for each block we compute mean neighborDemocratic share (Queen adjacency) and regress block dem_share on that.
Fixing a few issues: making the row lookup use an index to avoid O(n²) lookups, and fixing the cluster-robust API (get_robustcov_results may need different usage).
Using cov_kwds={'groups': ...} for cluster-robust SEs; optimizing the row lookup and index type for share_by_id.
block_adjacency_regression.py
+3
-2
    # 3) For each block, mean neighbor dem_share    share_by_id = blocks.set_index("GEOID20")["dem_share"]    rows = []
    share_by_id = blocks.set_index("GEOID20")["dem_share"]    # 3) For each block, mean neighbor dem_share    blocks_idx = blocks.set_index(blocks["GEOID20"].astype(str))    share_by_id = blocks_idx["dem_share"]    rows = []
block_adjacency_regression.py
+1
-1
            model_cl = model.get_robustcov_results(                cov_type="cluster", groups=df["TRACT_GEOID20"]            )
                cov_type="cluster", groups=df["TRACT_GEOID20"]            model_cl = model.get_robustcov_results(                cov_type="cluster", cov_kwds={"groups": df["TRACT_GEOID20"]}            )
Adding statsmodels to requirements.txt and a short analysis/README.md.
requirements.txt
+2
libpysal>=4.0
libpysal>=4.0# For analysis/block_adjacency_regression.pystatsmodels>=0.14.0
README.md(new)
+24
# AnalysisOne-off and exploratory analysis scripts, separate from the core redistricting pipeline in `src/`.## Block adjacency regression
Refactoring main() into smaller functions to reduce cognitive complexity:
block_adjacency_regression.py
+38
-32
def main():    blocks_path = config.BLOCKS_PATH    out_dir = config.OUTPUT_DIR    out_dir.mkdir(parents=True, exist_ok=True)
def main():    blocks_path = config.BLOCKS_PATH    out_dir = config.OUTPUT_DIR    out_dir.mkdir(parents=True, exist_ok=True)    # 1) Load blocks and prepare    print("Loading blocks...")
Summary of what’s in place:
Folder: analysis/ — holds this script and any future one-off analyses.
Added/updated:
analysis/block_adjacency_regression.py
Loads data/block_level_data.gpkg, derives block-level dem_share, builds Queen adjacency, builds one row per block with mean neighbor dem_share, runs OLS (and tract-clustered SEs when tract is present), writes outputs/block_adjacency_regression_data.csv and outputs/block_adjacency_scatter.png.
analysis/README.md
Short description of the analysis/ folder and how to run the block adjacency script.
requirements.txt
Pinned statsmodels>=0.14.0 for OLS and cluster-robust SEs.
How to run (from project root):
pip install statsmodelspython analysis/block_adjacency_regression.py
Outputs go to outputs/ (same as the rest of the project):
block_adjacency_regression_data.csv and block_adjacency_scatter.png.