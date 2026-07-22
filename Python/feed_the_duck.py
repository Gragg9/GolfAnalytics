import duckdb
from pathlib import Path

from json_ingest import parse_export, round_to_dict, holes_to_dicts


DATABASE_PATH = r"C:\Users\gragg\Projects\enhanced_garmin_golf_analytics\DB\golf.duckdb"
DATA_DIR = Path(r"C:\Users\gragg\Projects\enhanced_garmin_golf_analytics\Data")


def load_rounds(con, rounds_stage):
    """Insert rounds into DuckDB."""

    rows = [round_to_dict(r) for r in rounds_stage]

    con.executemany(
        """
        INSERT OR REPLACE INTO rounds_stage (
            round_id,
            course_id,
            course,
            city,
            state,
            start_time,
            end_time,
            tee_box,
            tee_rating,
            tee_slope,
            holes_completed,
            temp_f,
            wind_speed_mph,
            precip_mm, 
            steps
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                r["round_id"],
                r["course_id"],
                r["course"],
                r["city"],
                r["state"],
                r["start_time"],
                r["end_time"],
                r["tee_box"],
                r["tee_rating"],
                r["tee_slope"],
                r["holes_completed"],
                r["temp_f"],
                r["wind_speed_mph"],
                r["precip_mm"],
                r["steps"],
            )
            for r in rows
        ],
    )


def load_holes(con, rounds_stage):
    """Insert holes into DuckDB."""

    hole_rows = []

    for r in rounds_stage:
        hole_rows.extend(holes_to_dicts(r))

    con.executemany(
        """
        INSERT OR REPLACE INTO holes_stage (
            round_id,
            hole,
            par,
            strokes,
            putts,
            penalties,
            hole_handicap,
            fairway_outcome
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                h["round_id"],
                h["hole"],
                h["par"],
                h["strokes"],
                h["putts"],
                h["penalties"],
                h["hole_handicap"],
                h["fairway_outcome"],
            )
            for h in hole_rows
        ],
    )


def main():

    con = duckdb.connect(DATABASE_PATH)

    json_files = sorted(DATA_DIR.glob("scorecard_*.json"))

    if not json_files:
        raise FileNotFoundError(
            f"No JSON files found in {DATA_DIR}"
        )

    try:

        con.execute("BEGIN TRANSACTION")

        total_rounds = 0
        total_holes = 0

        for file in json_files:

            print(f"Loading {file.name}...")

            rounds = parse_export(str(file))

            total_rounds += len(rounds)
            total_holes += sum(len(r.holes) for r in rounds)

            load_rounds(con, rounds)
            load_holes(con, rounds)

        con.execute("COMMIT")

    except Exception:
        con.execute("ROLLBACK")
        raise

    finally:
        con.close()

    print("Load complete.")


if __name__ == "__main__":
    main()