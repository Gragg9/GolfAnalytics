import duckdb
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


DB_PATH = r"C:\Users\gragg\Projects\enhanced_garmin_golf_analytics\DB\golf.duckdb"

st.set_page_config(
    page_title="Golf Analytics",
    layout="wide"
)

st.title("Round Report")

con = duckdb.connect(DB_PATH)

df = con.execute(
 """
        WITH latest_round AS(
            SELECT
                MAX(rounds.start_time) AS start_time
            FROM rounds_stage rounds
            JOIN holes_stage holes
                ON holes.round_id = rounds.round_id
            WHERE holes.putts IS NOT NULL
            GROUP BY ALL
            HAVING start_time = MAX(start_time)
        ),

        best_round AS (
            SELECT
                rounds.course,
                rounds.tee_box,
                rounds.round_id,
                SUM(holes.strokes) AS total_strokes
            FROM rounds_stage rounds
            LEFT JOIN latest_round
                ON latest_round.start_time = rounds.start_time
            JOIN holes_stage holes
                ON holes.round_id = rounds.round_id
            WHERE 1=1
                AND holes.putts IS NOT NULL
                AND latest_round.start_time IS NULL
            GROUP BY ALL
            ORDER BY total_strokes ASC
            LIMIT 1
        ),

        holes_scores AS (
            SELECT
                holes.hole,
                rounds.course,
                AVG(holes.strokes) AS avg_strokes,
                holes.par,
                COUNT(*) AS played_count
            FROM holes_stage holes
            JOIN rounds_stage rounds
                ON holes.round_id = rounds.round_id
            LEFT JOIN latest_round
                ON latest_round.start_time = rounds.start_time
                AND latest_round.start_time IS NULL
            WHERE 1=1
                AND holes.putts IS NOT NULL
            GROUP BY ALL
        ), 

        rounds_stats AS (
            SELECT
                rounds.course,
                rounds.tee_box,
                rounds.round_id, 
                holes.hole,
                holes.strokes, 
                holes.putts,
                holes.par,
                holes.penalties,
                rounds.tee_slope, 
                (SUM(holes.strokes) OVER (PARTITION BY rounds.round_id)
                 - rounds.tee_rating)*(113/rounds.tee_slope) AS handicap_diff
            FROM rounds_stage rounds
            JOIN holes_stage holes
                ON holes.round_id = rounds.round_id
            LEFT JOIN latest_round
                ON latest_round.start_time = rounds.start_time
            WHERE 1=1
                AND holes.putts IS NOT NULL
                AND latest_round.start_time = rounds.start_time
        ),

        comparison AS (
            SELECT 
                rounds.round_id, 
                rounds.course,
                rounds.tee_box,
                holes.hole,
                holes.strokes, 
                holes.putts,
                CASE WHEN holes.strokes - holes.putts <= holes.par-2 THEN 1 ELSE 0 END AS GIR,
                CASE WHEN holes.strokes - holes.putts <= holes.par-1 THEN 1 ELSE 0 END AS BGIR,
                holes.par,
                holes.penalties,
                holes.strokes - holes_scores.avg_strokes AS diff_from_avg, 
                holes.strokes - best_round_holes.strokes AS diff_from_best,
                rounds_stats.handicap_diff AS round_handicap_differential,
                rounds.start_time, 
                rounds.end_time, 
                rounds.temp_f,
                rounds.wind_speed_mph,
                COALESCE(rounds.precip_mm, 0) AS precip_mm,

                SUM(holes.strokes - holes_scores.avg_strokes)
                    OVER (PARTITION BY rounds.round_id ORDER BY holes.hole) AS running_diff_from_avg,
                
                SUM(holes.strokes - best_round_holes.strokes) 
                    OVER (PARTITION BY rounds.round_id ORDER BY holes.hole) AS running_diff_from_best, 

                rounds.steps

            FROM latest_round
            JOIN rounds_stage rounds
                ON latest_round.start_time = rounds.start_time
            JOIN holes_stage holes
                ON holes.round_id = rounds.round_id
            JOIN holes_scores
                ON holes.hole = holes_scores.hole
                AND rounds.course = holes_scores.course
            LEFT JOIN best_round 
                ON best_round.course = rounds.course
                AND best_round.tee_box = rounds.tee_box
            LEFT JOIN holes_stage AS best_round_holes
                ON best_round_holes.round_id = best_round.round_id
                AND best_round_holes.hole = holes.hole
            JOIN rounds_stats
                ON rounds_stats.round_id = rounds.round_id
                AND rounds_stats.hole = holes.hole
            WHERE 1=1
                AND holes.putts IS NOT NULL
            ORDER BY holes.hole)

        SELECT *
        FROM comparison
        """
).fetchdf()

# --------------------
# Top metrics
# --------------------

total_strokes = df["strokes"].sum()
total_par = df["par"].sum()

duration = df["end_time"].iloc[0] - df["start_time"].iloc[0]

minutes = int(duration.total_seconds() // 60)
hours = minutes // 60
minutes = minutes % 60

top1, top2 = st.columns([3, 1])
st.divider()
mid1, mid2, mid3, mid4, mid5 = st.columns(5)
bot1, bot2, bot3, bot4, bot5 = st.columns(5)

with top1:
    st.metric(
        "Course",
        df["course"].iloc[0]
    )

with top2:
    st.metric(
        "Tee Box",
        df["tee_box"].iloc[0]
    )

with mid1:
    st.metric(
        label="Strokes / Par",
        value=f"{total_strokes:.0f}/{total_par:.0f}"
    )

with mid2:
    st.metric(
        "Net Score",
        f"{df['strokes'].sum() - df['par'].sum():+.0f}"
    )

with mid3:
    st.metric(
        "Handicap Differential",
        f"{df.loc[df["round_handicap_differential"].idxmin(), "round_handicap_differential"]:.2f}"
    )


with mid4:
    st.metric(
        "Putts Avg.",
        f"{df['putts'].mean():.1f}"
    )

with mid5:
    st.metric(
        "GIR",
        f"{df['GIR'].sum():.0f}"
    )

with bot1:
    st.metric(
        "Round Duration",
        f"{hours}h {minutes}m"
    )

with bot2:
    st.metric(
        "Steps",
        df["steps"].iloc[0]
    )

with bot3:
    st.metric(
        "Temp",
        int(df["temp_f"].iloc[0])
    )

with bot4:
    st.metric(
        "Wind Speed",
        int(df["wind_speed_mph"].iloc[0])
    )

with bot5:
    st.metric(
        "Precipitation",
        int(df["precip_mm"].iloc[0])
    )

st.divider()

# --------------------
# Running totals
# --------------------

left, right = st.columns(2)



with left:
    st.subheader("Score vs Best Round")

    y = df["running_diff_from_best"].tolist()
    x = df["hole"].tolist()

    fig_best = go.Figure()

    # ---- Main line ----
    fig_best.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            line=dict(color="aliceblue", width=3),
            marker=dict(color="aliceblue", size=7),
            showlegend=False,
        )
    )

    # ---- Green fill (below zero) ----
    x_fill = []
    y_fill = []

    for i in range(len(x) - 1):
        x_fill.append(x[i])
        y_fill.append(min(y[i], 0))

        # Crossing zero?
        if (y[i] < 0 < y[i+1]) or (y[i] > 0 > y[i+1]):
            frac = abs(y[i]) / abs(y[i+1] - y[i])
            x_cross = x[i] + frac * (x[i+1] - x[i])

            x_fill.append(x_cross)
            y_fill.append(0)

    x_fill.append(x[-1])
    y_fill.append(min(y[-1], 0))

    fig_best.add_trace(
        go.Scatter(
            x=x_fill,
            y=y_fill,
            mode="lines",
            line=dict(width=0),
            fill="tozeroy",
            fillcolor="rgba(50,205,50,0.25)",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # ---- Red fill (above zero) ----
    x_fill = []
    y_fill = []

    for i in range(len(x) - 1):
        x_fill.append(x[i])
        y_fill.append(max(y[i], 0))

        if (y[i] < 0 < y[i+1]) or (y[i] > 0 > y[i+1]):
            frac = abs(y[i]) / abs(y[i+1] - y[i])
            x_cross = x[i] + frac * (x[i+1] - x[i])

            x_fill.append(x_cross)
            y_fill.append(0)

    x_fill.append(x[-1])
    y_fill.append(max(y[-1], 0))

    fig_best.add_trace(
        go.Scatter(
            x=x_fill,
            y=y_fill,
            mode="lines",
            line=dict(width=0),
            fill="tozeroy",
            fillcolor="rgba(255,0,0,0.25)",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # ---- Zero line ----
    fig_best.add_hline(
        y=0,
        line_dash="solid",
        line_color="darkolivegreen",
        line_width=3,
        annotation_text="Even Score",
        annotation_position="top left",
    )

    # ---- Last point label ----
    last = df.iloc[-1]

    fig_best.add_trace(
        go.Scatter(
            x=[last["hole"] + 0.1],
            y=[last["running_diff_from_best"]],
            mode="text",
            text=[f"{last['running_diff_from_best']:+.0f}"],
            textposition="middle right",
            textfont=dict(
                size=20,
                color="limegreen" if last["running_diff_from_best"] <= 0 else "red",
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig_best.update_layout(
        xaxis_title="Hole",
        yaxis_title="Running Difference",
        showlegend=False,
    )

    st.plotly_chart(fig_best, width="stretch")                          


with right:
    st.subheader("Score vs Average")

    y = df["running_diff_from_avg"].tolist()
    x = df["hole"].tolist()

    fig_avg = go.Figure()

    # ---- Main line ----
    fig_avg.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            line=dict(color="aliceblue", width=3),
            marker=dict(color="aliceblue", size=7),
            showlegend=False,
        )
    )

    # ---- Green fill (below zero) ----
    x_fill = []
    y_fill = []

    for i in range(len(x) - 1):
        x_fill.append(x[i])
        y_fill.append(min(y[i], 0))

        if (y[i] < 0 < y[i + 1]) or (y[i] > 0 > y[i + 1]):
            frac = abs(y[i]) / abs(y[i + 1] - y[i])
            x_cross = x[i] + frac * (x[i + 1] - x[i])

            x_fill.append(x_cross)
            y_fill.append(0)

    x_fill.append(x[-1])
    y_fill.append(min(y[-1], 0))

    fig_avg.add_trace(
        go.Scatter(
            x=x_fill,
            y=y_fill,
            mode="lines",
            line=dict(width=0),
            fill="tozeroy",
            fillcolor="rgba(50,205,50,0.25)",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # ---- Red fill (above zero) ----
    x_fill = []
    y_fill = []

    for i in range(len(x) - 1):
        x_fill.append(x[i])
        y_fill.append(max(y[i], 0))

        if (y[i] < 0 < y[i + 1]) or (y[i] > 0 > y[i + 1]):
            frac = abs(y[i]) / abs(y[i + 1] - y[i])
            x_cross = x[i] + frac * (x[i + 1] - x[i])

            x_fill.append(x_cross)
            y_fill.append(0)

    x_fill.append(x[-1])
    y_fill.append(max(y[-1], 0))

    fig_avg.add_trace(
        go.Scatter(
            x=x_fill,
            y=y_fill,
            mode="lines",
            line=dict(width=0),
            fill="tozeroy",
            fillcolor="rgba(255,0,0,0.25)",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # ---- Zero line ----
    fig_avg.add_hline(
        y=0,
        line_dash="solid",
        line_color="darkolivegreen",
        line_width=3,
        annotation_text="Average Score",
        annotation_position="top left",
    )

    # ---- Last point label ----
    last = df.iloc[-1]

    fig_avg.add_trace(
        go.Scatter(
            x=[last["hole"] + 0.1],
            y=[last["running_diff_from_avg"]],
            mode="text",
            text=[f"{last['running_diff_from_avg']:+.1f}"],
            textposition="bottom right" if last["running_diff_from_avg"] > 0 else "top right",
            textfont=dict(
                size=20,
                color="limegreen" if last["running_diff_from_avg"] <= 0 else "red",
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig_avg.update_layout(
        xaxis_title="Hole",
        yaxis_title="Running Difference",
        showlegend=False,
    )

    st.plotly_chart(fig_avg, width="stretch")

# --------------------
# Detail table
# --------------------
st.subheader("Scorecard Detail")

scorecard_df = (
    df[
        [
            "hole",
            "strokes",
            "putts",
            "GIR",
            "BGIR",
            "par",
            "penalties",
        ]
    ]
    .rename(
        columns={
            "hole": "Hole",
            "strokes": "Strokes",
            "putts": "Putts",
            "GIR": "GIR",
            "BGIR": "BGIR",
            "par": "Par",
            "penalties": "Penalties",
        }
    )
)

# Score relative to par
scorecard_df["Score"] = scorecard_df["Strokes"] - scorecard_df["Par"]

scorecard_df = scorecard_df[
    [
        "Hole",
        "Par",
        "Strokes",
        "Score",
        "Putts",
        "GIR",
        "BGIR",
        "Penalties",
    ]
]

scorecard_df["Strokes"] = scorecard_df["Strokes"].astype(str)

def highlight_gir(val):
    return "background-color: #1c7007; color: white;" if val else ""


def highlight_bgir(val):
    return "background-color: #55a142; color: white;" if val else ""

def highlight_penalty(val):
    return (
        "background-color: #d32f2f; color: white;"
        if val > 0
        else ""
    )

def highlight_score(val):
    colors = {
        -2: "background-color: #006100; color: white;", 
        -1: "background-color: #3B7D04; color: black;",  
         0: "background-color: #6BA409; color: white;", 
         1: "background-color: #ADB30B; color: black;",  
         2: "background-color: #98680B; color: black;",  
    }

    if val >= 3:
        return "background-color: #85230B; color: white;"  
    return colors.get(val, "")

styled = (
    scorecard_df.style
    .map(highlight_gir, subset=["GIR"])
    .map(highlight_bgir, subset=["BGIR"])
    .map(highlight_penalty, subset=["Penalties"])
    .map(highlight_score, subset=["Score"])
    .format({
        "Score": lambda x: f"+{x}" if x > 0 else str(x),
        "GIR": lambda x: "✓" if x else "",
        "BGIR": lambda x: "✓" if x else "",
    })
)

st.dataframe(
    styled,
    width="stretch",
    hide_index=True,
)

con.close()