import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ParsedHole:
    hole: int
    par: int
    strokes: int

    putts: int | None
    penalties: int
    handicap_score: int | None
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


def parse_holes(
    scorecard: dict,
    course_snapshot: dict
) -> list[ParsedHole]:
    """
    Parse all completed holes for a scorecard.
    """

    holes = []
    hole_pars = course_snapshot["holePars"]

    for hole in scorecard["holes"]:

        if "strokes" not in hole:
            continue

        hole_number = hole["number"]

        par = int(hole_pars[hole_number - 1])

        holes.append(
            ParsedHole(
                hole=hole_number,
                par=par,
                strokes=hole["strokes"],
                putts=hole.get("putts"),
                penalties=hole.get("penalties", 0),
                handicap_score=hole.get("handicapScore"),
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

        tee_rating=scorecard["teeBoxRating"],
        tee_slope=scorecard["teeBoxSlope"],

        holes_completed=scorecard["holesCompleted"],

        holes=parse_holes(
            scorecard,
            course
),
    )


def parse_export(json_path: str) -> list[ParsedRound]:
    """Parse an entire Garmin export."""

    data = read_raw_json(json_path)

    course_lookup = build_course_lookup(data)

    return [
        parse_round(detail, course_lookup)
        for detail in data["scorecardDetails"]
    ]

def round_to_dict(r: ParsedRound) -> dict:
    return {
        "round_id": r.round_id,
        "course_id": r.course_id,
        "course": r.course,
        "city": r.city,
        "state": r.state,
        "start_time": r.start_time,
        "end_time": r.end_time,
        "tee_box": r.tee_box,
        "tee_rating": r.tee_rating,
        "tee_slope": r.tee_slope,
        "holes_completed": r.holes_completed,
    }


def holes_to_dicts(r: ParsedRound) -> list[dict]:
    return [
        {
            "round_id": r.round_id,
            "hole": h.hole,
            "par": h.par,
            "strokes": h.strokes,
            "putts": h.putts,
            "penalties": h.penalties,
            "handicap_score": h.handicap_score,
            "fairway_outcome": h.fairway_outcome,
        }
        for h in r.holes
    ]

def main():

    data_dir = Path(
        r"C:\Users\gragg\Projects\enhanced_garmin_golf_analytics\Data"
    )

    json_files = sorted(data_dir.glob("*.json"))

    if not json_files:
        raise FileNotFoundError(
            f"No JSON files found in {data_dir}"
        )

    for json_file in json_files:

        rounds = parse_export(json_file)

        print(
            f"Parsed {len(rounds)} rounds from {json_file.name}"
        )


if __name__ == "__main__":
    main()