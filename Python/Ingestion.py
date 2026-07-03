from dataclasses import dataclass
import pandas as pd
import re

DATE_PATTERN = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}$")
RATIO_PATTERN = re.compile(r"^\d+/\d+$")

# Garmin exports each statistic at a fixed offset after an
# Out/In/Total hole segment terminator.
PAR_OFFSET = 2
SCORE_OFFSET = 13
PUTT_OFFSET = 28


@dataclass
class HoleSegment:
    """Represents a contiguous 9-hole section of the scorecard."""

    holes: list[int]
    end_row: int


def read_raw_csv(csv_path: str) -> pd.DataFrame:
    """Read the raw Garmin CSV."""
    return pd.read_csv(csv_path, header=None)


def is_ratio(value: str) -> bool:
    """Return True if the value is in the form X/Y."""
    return bool(RATIO_PATTERN.match(str(value).strip()))


def extract_date(column: pd.Series) -> tuple[str, int]:
    """
    Locate the round date.

    Returns:
        (date_string, row_index)
    """

    for idx, value in enumerate(column):
        value = str(value).strip()

        if DATE_PATTERN.match(value):
            return value, idx

    raise ValueError("No valid date found in column.")


def extract_course(column: pd.Series, date_row: int) -> str:
    """
    Construct the course name from all populated rows before the date.
    """

    course_lines = []

    for i in range(date_row):
        value = str(column.iloc[i]).strip()

        if value and value.lower() != "nan":
            course_lines.append(value)

    if not course_lines:
        raise ValueError("No course name found before date.")

    return " ".join(course_lines)


def extract_tees(column: pd.Series, date_row: int) -> str:
    """
    Extract the tee designation located two rows after the date.
    """

    tees = str(column.iloc[date_row + 2]).strip()

    if "tees" not in tees.lower():
        raise ValueError(
            f"Expected tee name at row {date_row + 2}, found '{tees}'"
        )

    return tees


def extract_hole_segments(column: pd.Series) -> list[HoleSegment]:
    """
    Locate every 9-hole segment.

    A segment is identified by a terminator (Out, In, or Total)
    immediately following 9 consecutive hole numbers.
    """

    segments = []

    for idx, value in enumerate(column):
        value = str(value).strip()

        if value not in ("Out", "In", "Total"):
            continue

        holes = []

        try:
            for i in range(idx - 9, idx):
                holes.append(int(column.iloc[i]))
        except ValueError:
            continue

        if holes != list(range(holes[0], holes[0] + 9)):
            continue

        segments.append(HoleSegment(
            holes=holes,
            end_row=idx
        ))

    return segments


def extract_stat_block(
    segment: HoleSegment,
    column: pd.Series,
    offset: int
) -> list[int]:
    """
    Extract a 9-value statistic block located at a fixed offset
    after a hole segment terminator.
    """

    start = segment.end_row + offset

    values = []

    for i in range(9):
        value = str(column.iloc[start + i]).strip()

        try:
            values.append(int(value))
        except ValueError:
            raise ValueError(
                f"Expected integer at row {start + i}, found '{value}'"
            )

    return values


def extract_fairways(column: pd.Series) -> list[str] | None:
    """
    Extract fairway statistics.

    Returns:
        ['front_ratio'] for 9-hole rounds
        ['front_ratio', 'back_ratio'] for 18-hole rounds
        None if fairways were not tracked.
    """

    ratios = []
    first_label_idx = None

    for idx, value in enumerate(column):
        value = str(value).strip()

        if value.lower() == "fairway" and first_label_idx is None:
            first_label_idx = idx

        if is_ratio(value):
            ratios.append(value)

    if first_label_idx is None:
        return None

    expected = str(column.iloc[first_label_idx + 1]).strip()

    if not ratios or ratios[0] != expected:
        raise ValueError(
            "Fairway validation failed."
        )

    fairways = [ratios[0]]

    if len(ratios) >= 3:
        fairways.append(ratios[2])

    return fairways


def parse_round(column: pd.Series) -> dict:
    """
    Parse a single round from one CSV column.

    Returns:
        Dictionary containing the extracted round data.
    """

    date, date_row = extract_date(column)

    course = extract_course(column, date_row)
    tees = extract_tees(column, date_row)

    all_holes = []
    all_pars = []
    all_scores = []
    all_putts = []

    for segment in extract_hole_segments(column):

        all_holes.extend(segment.holes)

        all_pars.extend(
            extract_stat_block(segment, column, PAR_OFFSET)
        )

        all_scores.extend(
            extract_stat_block(segment, column, SCORE_OFFSET)
        )

        all_putts.extend(
            extract_stat_block(segment, column, PUTT_OFFSET)
        )

    return {
        "course": course,
        "date": date,
        "tees": tees,
        "holes": all_holes,
        "pars": all_pars,
        "scores": all_scores,
        "putts": all_putts,
        "fairways": extract_fairways(column),
    }


# ------------------------------------------------------------
# MAIN PIPELINE
# ------------------------------------------------------------

def main():

    df = read_raw_csv(
        r"C:\Users\gragg\Projects\GolfAnalytics\Data\GolfStatsdata.csv"
    )

    for col_idx in range(df.shape[1]):

        try:
            round_data = parse_round(df.iloc[:, col_idx])

            print(f"\n--- Round {col_idx} ---")
            print("Course    :", round_data["course"])
            print("Date      :", round_data["date"])
            print("Tees      :", round_data["tees"])
            print("Holes     :", round_data["holes"])
            print("Pars      :", round_data["pars"])
            print("Scores    :", round_data["scores"])
            print("Putts     :", round_data["putts"])
            print("Fairways  :", round_data["fairways"])

        except ValueError:
            # Skip blank or malformed columns.
            continue


if __name__ == "__main__":
    main()