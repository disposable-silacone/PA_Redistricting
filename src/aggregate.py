"""
Aggregate block-level votes and population to district totals.
"""
import pandas as pd


def aggregate_to_districts(blocks_joined_df, district_col="CD116FP"):
    """
    Group by district_col and sum pop/votes; compute dem_share, winner, margin.
    Drops rows with missing district_col.
    """
    df = blocks_joined_df.dropna(subset=[district_col])
    agg = df.groupby(district_col).agg(
        pop_total=("block_pop", "sum"),
        dem_total=("dem_block", "sum"),
        rep_total=("rep_block", "sum"),
    ).reset_index()
    agg["two_party_total"] = agg["dem_total"] + agg["rep_total"]
    agg["dem_share"] = agg["dem_total"] / agg["two_party_total"].replace(0, float("nan"))
    agg["rep_share"] = agg["rep_total"] / agg["two_party_total"].replace(0, float("nan"))
    def _winner(dem_share):
        if pd.isna(dem_share):
            return ""
        return "D" if dem_share > 0.5 else "R"
    agg["winner"] = agg["dem_share"].apply(_winner)
    agg["margin"] = agg["dem_share"] - 0.5
    return agg
