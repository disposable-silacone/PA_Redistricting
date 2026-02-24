# Redistricting Fairness Metrics — Plain-English Guide

Using your current CD116 run: D got **49.13%** of the two-party vote but **50%** of seats (9 of 18). The metrics below quantify how “fair” or “biased” that map is.

---

## What You Already Have

### 1. **Statewide totals & vote share**
- **statewide_dem / statewide_rep** — Total two-party votes by party.
- **statewide_dem_share** — D’s share of the two-party vote (e.g. 0.491 ≈ 49.1%).

*Use:* Baseline. “In a perfectly proportional world, D would get 49.1% of seats.”

---

### 2. **Seat share**
- **seats_dem / seats_rep** — Number of districts won by each party.
- **seat_share_dem** — D’s share of seats (e.g. 9/18 = 0.5).

*Use:* Outcome. Compare to statewide_dem_share to see if the map over- or under-rewards one party.

---

### 3. **Efficiency gap (EG)**
- **Formula:** `(total wasted R votes − total wasted D votes) / total two-party votes`.
- **Wasted votes:** In a district, votes for the loser are “wasted”; votes for the winner above 50% are also “wasted” (surplus).
- **Your convention:** **Positive EG ⇒ Democratic advantage** (more Republican votes wasted than Democratic).

*Interpretation (rule of thumb):*
- |EG| &lt; 0.02 → often considered “acceptable.”
- |EG| &gt; 0.08 → often cited as strong gerrymander (in litigation).
- Your **0.020** → slight D advantage: R votes are wasted a bit more than D votes across the map.

*Use:* Single number for “how much does the map waste one party’s votes more than the other?”

---

### 4. **Mean–median difference**
- **Formula:** `mean(district D share) − median(district D share)`.
- If the **mean** is above the **median**, the distribution of district D shares is right-skewed (a few very D-heavy districts pull the mean up).

*Interpretation:*
- **Positive** → a few very safe D districts; many districts below the median (can indicate “packing” of D voters).
- **Negative** → opposite (packing of R voters).
- **Near 0** → symmetric.
- Your **0.002** → very small; distribution is almost symmetric.

*Use:* Detects **asymmetry in the shape** of the vote-share distribution (packing vs spread).

---

### 5. **Seat–vote gap**
- **Formula:** `seat_share_dem − statewide_dem_share`.
- **Positive** → D gets a larger share of seats than of votes (D advantage).
- **Negative** → R gets more seats than votes (R advantage).

Your **0.0087** → D gets about 0.9 percentage points more in seat share than in vote share.

*Use:* Direct “proportionality” check: do seats match votes?

---

### 6. **Partisan bias at 50% (uniform swing)**
- **Idea:** Shift the statewide vote to exactly 50% D / 50% R (same swing in every district), then count how many seats D would win.
- **Formula:** `(seats_D at 50% vote) / 18 − 0.5`. So **0** = symmetric (at 50% vote, 9–9 split); **positive** = D bias; **negative** = R bias.
- Your **0** → at a hypothetical 50/50 vote, the map would yield 9 D and 9 R seats.

*Use:* “If the state were perfectly tied, would the map favor one side?” (Assumes uniform swing; doesn’t capture every kind of bias.)

---

## Added in This Project

### 7. **Competitiveness**
- **competitive_count** — Number of districts where D’s share is between 45% and 55%.
- **competitive_pct** — That count as a share of all districts.

*Use:* “How many districts are in play?” More competitive districts often mean a more responsive map.

### 8. **Safe seats**
- **safe_d_count / safe_r_count** — Districts where D (or R) has ≥ 60% of the two-party vote.
- **safe_d_pct / safe_r_pct** — Those counts as a share of all districts.

*Use:* “How many districts are packed?” Many safe seats and few competitive ones can indicate packing.

---

## Compactness (shape)

### 9. **Polsby-Popper (Polsby-Hopper)**
- **Formula:** `(4 × π × area) / perimeter²`. Value between 0 and 1.
- **1** = perfect circle (most compact). **0** = very elongated or irregular (e.g. thin tendrils).
- **polsby_hopper** is computed per district (after dissolving multi-part districts into one polygon).
- **compactness_mean / min / max / median** — summary across districts.

*Use:* “Are districts compact or oddly shaped?” Low compactness can suggest gerrymandering. Courts and guidelines sometimes cite a minimum (e.g. mean &gt; 0.2).

---

## Population equality

### 10. **Population deviation**
- **ideal_pop** — Total state population in your block data ÷ number of districts (e.g. PA ÷ 18).
- **Per district:** `pop_deviation_pct = (district_pop - ideal_pop) / ideal_pop × 100`.
- **max_pop_deviation_pct / min_pop_deviation_pct** — largest above and below ideal.
- **pop_deviation_range_pct** — max − min (total spread).
- **pop_deviation_std_pct** — standard deviation of deviation %.

*Use:* “Are districts equally populated?” One-person-one-vote requires roughly equal population; courts often allow small deviations (e.g. &lt; 1% or &lt; 10% total range). Your district CSV has **pop_deviation_pct** per row.

---

## Optional Metrics You Could Add (not yet implemented)

| Metric | What it measures | Use case |
|--------|-------------------|----------|
| **Declination** | Similar to mean–median but uses a different formula (vote-weighted “tail” of the distribution). | Alternative skew measure; sometimes preferred in academic work. |
| **Responsiveness** | Slope of the seat–vote curve near the current vote share (how much seat share changes per 1% vote change). | “How sensitive is the map to small vote swings?” |
| **Gallagher index** | Proportionality index: deviation of seat shares from vote shares (like a least-squares measure). | Single “how proportional?” number. |
| **Partisan symmetry (bias at other points)** | Same as “bias at 50%” but evaluated at 45%, 55%, etc. | Richer picture of symmetry across the seat–vote curve. |

*Note:* **Competitiveness** and **safe seats** are already implemented (sections 7 and 8 above). If you want any of the optional metrics above (e.g. “competitiveness and declination”), they can be added to `src/metrics.py` and to the JSON output.
