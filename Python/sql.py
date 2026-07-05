import duckdb

DB_PATH = r"C:\Users\gragg\Projects\enhanced_garmin_golf_analytics\DB\golf.duckdb"

con = duckdb.connect(DB_PATH)

print(
    con.execute(
        """
        WITH holes_scores AS (
            SELECT
                hole,
                course,
                AVG(strokes) AS avg_strokes,
                par,
                COUNT(*) AS played_count
            FROM holes
            JOIN rounds
                ON holes.round_id = rounds.round_id
            WHERE putts IS NOT NULL
            GROUP BY hole, course, par
            HAVING played_count >=3
        )
        SELECT
            hole,
            course,
            (avg_strokes - par) AS net_avg
        FROM holes_scores
        ORDER BY avg_strokes - par
        """
    ).fetchdf()
)

