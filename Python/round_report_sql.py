import duckdb
import math
import pandas as pd

DB_PATH = r"C:\Users\gragg\Projects\enhanced_garmin_golf_analytics\DB\golf.duckdb"

con = duckdb.connect(DB_PATH)

holes_gold = con.execute(
 """
SELECT 
    h.round_id,
    h.hole, 
    h.par, 
    h.strokes,
    h.putts,
    h.penalties,
    h.hole_handicap,
    h.fairway_outcome,
    CASE WHEN strokes - h.putts <= h.par-2 THEN 1 ELSE 0 END AS GIR,
    CASE WHEN strokes - h.putts <= h.par-1 THEN 1 ELSE 0 END AS BGIR, 
    CASE
    WHEN course_handicap <= 18 THEN
        CASE
            WHEN hole_handicap <= course_handicap THEN 1
            ELSE 0
        END

    ELSE
        FLOOR(course_handicap / 18)
        +
        CASE
            WHEN hole_handicap <= MOD(course_handicap, 18)
            THEN 1
            ELSE 0
        END
    END AS strokes_received
FROM holes_stage h 
JOIN handicap_history hh
USING (round_id)
;
        """
    ).fetchdf()


round_gold = con.execute(
 """
 WITH init AS (
SELECT 
   r.*,
   SUM(h.strokes) AS total_score, 
FROM rounds_stage r
JOIN holes_stage h 
USING (round_id)
GROUP BY ALL)

SELECT    r.round_id, 
   r.course_id, 
   r.course,
   r.city,
   r.state,
   r.start_time,
   r.end_time,
   r.tee_box,
   r.tee_rating,
   r.tee_slope,
   r.holes_completed,
   r.temp_f,
   r.wind_speed_mph,
   r.precip_mm,
   r.steps, 
   r.total_score,
    (r.total_score - r.tee_rating)*(113/r.tee_slope) AS handicap_diff,
   RANK() OVER(PARTITION BY course ORDER BY total_score) as course_rank, 
   RANK() OVER(ORDER BY handicap_diff), 
   hh.handicap_before, 
   hh.handicap_after
FROM init r
JOIN handicap_history hh
ORDER BY handicap_diff
;
        """
    ).fetchdf()

print(round_gold.to_string())
