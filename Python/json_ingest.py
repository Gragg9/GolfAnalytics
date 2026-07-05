import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ParsedHole:
    hole: int
    strokes: int

    putts: int | None
    penalties: int
    fairway_outcome: str | None


@dataclass
class ParsedRound:
    """Represents one Garmin scorecard."""

    round_id: int
    course_id: int

    course: str
    city: str
    state: str

    start_time: datetime
    end_time: datetime

    tee_box: str
    score_type: str

    tee_rating: float
    tee_slope: int

    holes_completed: int

    holes: list[ParsedHole]

def read_raw_json(json_path: str) -> dict:
    """Load the Garmin export."""

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_course_lookup(data: dict) -> dict[int, dict]:
    """Build a lookup of course metadata."""

    return {
        course["courseGlobalId"]: course
        for course in data["courseSnapshots"]
    }


def parse_holes(scorecard: dict) -> list[ParsedHole]:
    """
    Parse all completed holes for a scorecard.
    """

    holes = []

    for hole in scorecard["holes"]:

        # Skip holes that were not played
        if "strokes" not in hole:
            continue

        holes.append(
            ParsedHole(
                hole=hole["number"],
                strokes=hole["strokes"],
                putts=hole.get("putts"),
                penalties=hole.get("penalties", 0),
                fairway_outcome=hole.get("fairwayShotOutcome"),
            )
        )

    return holes


def parse_round(
    detail: dict,
    course_lookup: dict[int, dict],
) -> ParsedRound:
    """Parse one scorecard."""

    scorecard = detail["scorecard"]

    course = course_lookup[scorecard["courseGlobalId"]]

    return ParsedRound(
        round_id=scorecard["id"],
        course_id=scorecard["courseGlobalId"],

        course=course["name"],
        city=course["city"],
        state=course["state"],

        start_time=datetime.fromisoformat(
            scorecard["startTime"].replace("Z", "+00:00")
        ),
        end_time=datetime.fromisoformat(
            scorecard["endTime"].replace("Z", "+00:00")
        ),

        tee_box=scorecard["teeBox"],
        score_type=scorecard["scoreType"],

        tee_rating=scorecard["teeBoxRating"],
        tee_slope=scorecard["teeBoxSlope"],

        holes_completed=scorecard["holesCompleted"],

        holes=parse_holes(scorecard),
    )


def parse_export(json_path: str) -> list[ParsedRound]:
    """Parse an entire Garmin export."""

    data = read_raw_json(json_path)

    course_lookup = build_course_lookup(data)

    return [
        parse_round(detail, course_lookup)
        for detail in data["scorecardDetails"]
    ]

def main():

    data_dir = Path(
        r"C:\Users\gragg\Projects\GolfAnalytics\Data"
    )

    json_files = sorted(data_dir.glob("*.json"))

    if not json_files:
        raise FileNotFoundError(
            f"No JSON files found in {data_dir}"
        )

    all_rounds = []

    for json_file in json_files:

        print(f"\nParsing {json_file.name}...")

        rounds = parse_export(json_file)

        all_rounds.extend(rounds)

    print(f"\nParsed {len(all_rounds)} rounds.\n")

    for round_data in all_rounds:

        print(f"Round ID : {round_data.round_id}")
        print(f"Course   : {round_data.course}")
        print(f"Date     : {round_data.start_time.date()}")
        print(f"Holes    : {len(round_data.holes)}")
        print()

main()