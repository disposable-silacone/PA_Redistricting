"""
Population equality across districts.
"""
import pandas as pd


def compute_population_deviation(district_df, pop_col="pop_total", id_col="CD116FP"):
    """
    Ideal population = total_pop / n_districts.
    Deviation % = (district_pop - ideal) / ideal * 100.
    Returns dict with ideal_pop, per-district deviation, and summary stats.
    """
    total_pop = district_df[pop_col].sum()
    n = len(district_df)
    if n == 0:
        return {
            "ideal_pop": None,
            "population_deviation_pct_by_district": {},
            "max_deviation_pct": None,
            "min_deviation_pct": None,
            "deviation_range_pct": None,
            "deviation_std_pct": None,
        }
    ideal = total_pop / n
    dev_pct = (district_df[pop_col] - ideal) / ideal * 100
    by_district = district_df[id_col].astype(str).str.zfill(2)
    dev_series = pd.Series(dev_pct.values, index=by_district)
    return {
        "ideal_pop": float(ideal),
        "population_deviation_pct_by_district": dev_series.to_dict(),
        "max_deviation_pct": float(dev_pct.max()),
        "min_deviation_pct": float(dev_pct.min()),
        "deviation_range_pct": float(dev_pct.max() - dev_pct.min()),
        "deviation_std_pct": float(dev_pct.std()) if n > 1 else None,
    }
