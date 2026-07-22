import duckdb
import pandas as pd

DB_PATH = r"C:\Users\gragg\Projects\enhanced_garmin_golf_analytics\DB\golf.duckdb"

con = duckdb.connect(DB_PATH)

df = con.execute(
 """
WITH inter AS(
SELECT
    rounds_stage.round_id,
    end_time,
    course_id,
    tee_rating,
    tee_slope,
    SUM(holes_stage.par) AS course_par,
    SUM(holes_stage.strokes) AS total_handi_score
FROM rounds_stage
JOIN holes_stage
ON holes_stage.round_id = rounds_stage.round_id
GROUP BY ALL)

SELECT *, 
(total_handi_score - tee_rating) * 113.0 / tee_slope AS handicap_diff
FROM inter
ORDER BY end_time
;
        """
    ).fetchdf()

WHS_BEST = {
    3: 1,
    4: 1,
    5: 1,
    6: 2,
    7: 2,
    8: 2,
    9: 3,
    10: 3,
    11: 3,
    12: 4,
    13: 4,
    14: 4,
    15: 5,
    16: 5,
    17: 6,
    18: 6,
    19: 7,
    20: 8,
}


def calculate_handicap(previous_diffs):
    """
    Returns the handicap index BEFORE the next round.
    """

    count = min(len(previous_diffs), 20)

    if count < 3:
        return None

    recent = previous_diffs[-20:]

    best_to_use = WHS_BEST[count]

    best = sorted(recent)[:best_to_use]

    return round(sum(best) / len(best), 1)



previous_diffs = []

handicap_before = []
handicap_after = []

for _, row in df.iterrows():

    hi_before = calculate_handicap(previous_diffs)

    handicap_before.append(hi_before)

    previous_diffs.append(row.handicap_diff)

    hi_after = calculate_handicap(previous_diffs)

    handicap_after.append(hi_after)

df["handicap_before"] = handicap_before
df["handicap_after"] = handicap_after

df["course_handicap"] = pd.NA

mask = df["handicap_before"].notna()

df.loc[mask, "course_handicap"] = (
    (
        df.loc[mask, "handicap_before"]
        * df.loc[mask, "tee_slope"]
        / 113
    )
    + (
        df.loc[mask, "tee_rating"]
        - df.loc[mask, "course_par"]
    )
).round().astype(int)

con.register("handicap_df", df)

con.execute("""
CREATE OR REPLACE TABLE handicap_history AS

SELECT
    round_id,
    handicap_before,
    handicap_after,
    course_handicap
FROM handicap_df
""")

print(
    df[
        [
            "round_id",
            "handicap_diff",
            "handicap_before",
            "handicap_after",
            "course_handicap",
        ]
    ].tail(10)
)


df = con.execute("""
SELECT
    h.round_id,
    h.hole,
    h.par,
    h.strokes,
    h.hole_handicap,
    hh.course_handicap
FROM holes_stage h
JOIN handicap_history hh
    USING (round_id)
ORDER BY
    round_id,
    hole
""").fetchdf()

# ------------------------------------------------------------------
# Calculate strokes received on each hole
# ------------------------------------------------------------------

def strokes_received(course_handicap, hole_handicap):
    """
    Number of handicap strokes received on this hole.
    """

    if pd.isna(course_handicap):
        return 0

    course_handicap = int(course_handicap)

    base = course_handicap // 18
    extra = course_handicap % 18

    received = base

    if extra > 0 and hole_handicap <= extra:
        received += 1

    return received


df["strokes_received"] = df.apply(
    lambda r: strokes_received(
        r.course_handicap,
        r.hole_handicap
    ),
    axis=1
)

# ------------------------------------------------------------------
# Net Double Bogey limit
# ------------------------------------------------------------------

df["max_score"] = (
    df["par"]
    + 2
    + df["strokes_received"]
)

# ------------------------------------------------------------------
# Adjusted score
# ------------------------------------------------------------------

df["adjusted_strokes"] = df[
    ["strokes", "max_score"]
].min(axis=1)

# ------------------------------------------------------------------
# Summarize to one row per round
# ------------------------------------------------------------------

round_summary = (
    df.groupby("round_id", as_index=False)
      .agg(
          gross_score=("strokes", "sum"),
          adjusted_score=("adjusted_strokes", "sum")
      )
)

# ------------------------------------------------------------------
# Join ratings back on
# ------------------------------------------------------------------

ratings = con.execute("""
SELECT
    round_id,
    tee_rating,
    tee_slope
FROM rounds_stage
""").fetchdf()

round_summary = round_summary.merge(
    ratings,
    on="round_id",
    how="left"
)

# ------------------------------------------------------------------
# Calculate adjusted handicap differential
# ------------------------------------------------------------------

round_summary["adjusted_handicap_diff"] = (
    (round_summary["adjusted_score"] - round_summary["tee_rating"])
    * 113
    / round_summary["tee_slope"]
).round(1)

# ------------------------------------------------------------------
# Save results
# ------------------------------------------------------------------

con.register("round_summary_df", round_summary)

con.execute("""
CREATE OR REPLACE TABLE adjusted_round_scores AS

SELECT *
FROM round_summary_df
""")

print(round_summary.head())