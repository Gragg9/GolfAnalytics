import pandas as pd


def read_raw_csv(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path, header=None)



df = read_raw_csv(
    r"C:\Users\gragg\Projects\GolfAnalytics\Data\GolfStatsdata.csv"
)

print(df.head())


