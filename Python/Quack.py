import duckdb

# Replace with your path
DATABASE_PATH = r"C:\Users\gragg\Projects\GolfAnalytics\DB\quack.duckdb"

# Create (or open) the database
con = duckdb.connect(DATABASE_PATH)

con.execute("""CREATE TABLE IF NOT EXISTS holes (
    round_id        VARCHAR,
    course          VARCHAR,
    date            DATE,
    tees            VARCHAR,

    hole            INTEGER,
    par             INTEGER,
    score           INTEGER,
    net             INTEGER,
    putts           INTEGER,

    penalty         INTEGER,
    gir             INTEGER,
    bgir            INTEGER
);""")

# Close the connection
con.close()

print("Connection closed.")
