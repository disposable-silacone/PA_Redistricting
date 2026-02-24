"""
Partisan fairness metrics: efficiency gap, mean-median, seat-vote gap, optional bias.
"""
import numpy as np


def compute_efficiency_gap(district_df):
    """
    Two-party efficiency gap.
    EG = (sum(wasted_R) - sum(wasted_D)) / sum(T).
    Positive EG => advantage to Democrats (more R votes wasted).
    """
    df = district_df.copy()
    T = df["two_party_total"]
    df["wasted_D"] = np.where(
        df["dem_share"] > 0.5,
        df["dem_total"] - 0.5 * T,
        df["dem_total"],
    )
    df["wasted_R"] = np.where(
        df["dem_share"] <= 0.5,
        df["rep_total"] - 0.5 * T,
        df["rep_total"],
    )
    total_votes = T.sum()
    if total_votes == 0:
        return float("nan")
    eg = (df["wasted_R"].sum() - df["wasted_D"].sum()) / total_votes
    return float(eg)


def compute_mean_median(district_df):
    """Mean of district dem_shares minus median."""
    s = district_df["dem_share"].dropna()
    if s.empty:
        return float("nan")
    return float(s.mean() - s.median())


def compute_seat_vote_gap(district_df, statewide_dem_share):
    """Seat share (D) minus statewide vote share (D)."""
    n = len(district_df)
    if n == 0:
        return float("nan")
    seats_dem = (district_df["winner"] == "D").sum()
    seat_share_dem = seats_dem / n
    return float(seat_share_dem - statewide_dem_share)


def compute_uniform_swing_bias(district_df, statewide_dem_share, n_seats=18):
    """
    Partisan bias at 50% (uniform swing). Simple proxy; document as such.
    """
    delta = 0.5 - statewide_dem_share
    dem_share_50 = (district_df["dem_share"] + delta).clip(0, 1)
    seats_at_50 = (dem_share_50 > 0.5).sum()
    return float(seats_at_50 / n_seats - 0.5)


def compute_competitiveness(district_df, low=0.45, high=0.55):
    """
    Count and share of districts in the swing band [low, high] of dem_share.
    """
    s = district_df["dem_share"].dropna()
    in_band = ((s >= low) & (s <= high)).sum()
    n = len(s)
    return {
        "competitive_count": int(in_band),
        "competitive_pct": float(in_band / n) if n else 0.0,
    }


def compute_safe_seats(district_df, threshold=0.6):
    """
    Count of safe D districts (dem_share >= threshold) and safe R districts
    (dem_share <= 1 - threshold). Default threshold 0.6 => 60%+ is "safe".
    """
    s = district_df["dem_share"].dropna()
    safe_d = (s >= threshold).sum()
    safe_r = (s <= (1 - threshold)).sum()
    return {
        "safe_d_count": int(safe_d),
        "safe_r_count": int(safe_r),
        "safe_d_pct": float(safe_d / len(s)) if len(s) else 0.0,
        "safe_r_pct": float(safe_r / len(s)) if len(s) else 0.0,
    }
