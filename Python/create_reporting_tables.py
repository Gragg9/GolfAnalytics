import duckdb

DATABASE_PATH = r"C:\Users\gragg\Projects\enhanced_garmin_golf_analytics\DB\golf.duckdb"

con = duckdb.connect(DATABASE_PATH)

# ------------------------------------------------------------------
# Create rounds table
# ------------------------------------------------------------------

con.execute("""
CREATE TABLE IF NOT EXISTS rounds (
    round_id        BIGINT PRIMARY KEY,
    course_id       BIGINT NOT NULL,

    course          VARCHAR NOT NULL,
    city            VARCHAR,
    state           VARCHAR,

    start_time      TIMESTAMP NOT NULL,
    end_time        TIMESTAMP NOT NULL,

    tee_box         VARCHAR,

    tee_rating      DOUBLE,
    tee_slope       INTEGER,

    holes_completed INTEGER NOT NULL,

    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# ------------------------------------------------------------------
# Create holes table
# ------------------------------------------------------------------

con.execute("""
CREATE TABLE IF NOT EXISTS holes (
    round_id         BIGINT NOT NULL,

    hole             INTEGER NOT NULL,
    par              INTEGER NOT NULL,
    strokes          INTEGER NOT NULL,

    putts            INTEGER,
    penalties        INTEGER,
    handicap_score   INTEGER,
    fairway_outcome  VARCHAR,

    loaded_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (round_id, hole)
);
""")

print("Database schema created successfully.")

con.close()