import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder

from weather import semicircles_to_degrees, get_weather_near_point

_tf = TimezoneFinder()  # expensive to init — module-level, not per-call


@dataclass
class ParsedHole:
    hole: int
    par: int
    strokes: int

    putts: int | None
    penalties: int
    fairway_outcome: str | None
    hole_handicap: int

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
    
    steps: int

    holes: list[ParsedHole]

    # Weather at hole 1 / tee time
    temp_f: float | None = None
    wind_speed_mph: float | None = None
    precip_mm: float | None = None


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

def parse_course_handicaps(course_handicap_str: str) -> list[int]:
    """Parse Garmin's fixed-width course handicap string."""

    if len(course_handicap_str) % 2 != 0:
        raise ValueError(
            f"Invalid handicap string length: {len(course_handicap_str)}"
        )

    return [
        int(course_handicap_str[i:i + 2])
        for i in range(0, len(course_handicap_str), 2)
    ]

def parse_holes(scorecard: dict, course_snapshot: dict) -> list[ParsedHole]:
    """Parse all completed holes for a scorecard."""
    holes = []
    hole_pars = course_snapshot["holePars"]
    hole_handicaps = parse_course_handicaps(
        scorecard["courseHandicapStr"]
    )

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
                fairway_outcome=hole.get("fairwayShotOutcome"),
                hole_handicap= hole_handicaps[hole_number - 1],
            )
        )

    return holes


def get_hole_one_pin(scorecard: dict) -> tuple[int, int] | None:
    """Get (lat, lon) in Garmin semicircle format from hole 1, if present."""
    for hole in scorecard["holes"]:
        if hole["number"] == 1:
            lat = hole.get("pinPositionLat")
            lon = hole.get("pinPositionLon")
            if lat is not None and lon is not None:
                return lat, lon
            return None
    return None


def fetch_round_weather(scorecard: dict, start_time: datetime) -> dict:
    """Look up weather at hole 1's pin location around tee time. Never raises."""
    pin = get_hole_one_pin(scorecard)
    if pin is None:
        return {"temp_f": None, "wind_speed_mph": None, "precip_mm": None}

    lat_semicircles, lon_semicircles = pin
    lat = semicircles_to_degrees(lat_semicircles)
    lon = semicircles_to_degrees(lon_semicircles)

    tz_name = _tf.timezone_at(lat=lat, lng=lon)
    if tz_name is None:
        print(f"Could not resolve timezone for round {scorecard.get('id')} at ({lat:.4f}, {lon:.4f})")
        return {"temp_f": None, "wind_speed_mph": None, "precip_mm": None}

    # start_time is tz-aware UTC; convert to the course's actual local time
    local_start = start_time.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None)

    try:
        return get_weather_near_point(lat_semicircles, lon_semicircles, local_start)
    except ValueError as e:
        print(f"Weather lookup failed for round {scorecard.get('id')}: {e}")
        return {"temp_f": None, "wind_speed_mph": None, "precip_mm": None}

def parse_round(detail: dict, course_lookup: dict[int, dict]) -> ParsedRound:
    """Parse one scorecard."""
    scorecard = detail["scorecard"]
    course = course_lookup[scorecard["courseGlobalId"]]

    start_time = datetime.fromisoformat(scorecard["startTime"].replace("Z", "+00:00"))
    end_time = datetime.fromisoformat(scorecard["endTime"].replace("Z", "+00:00"))

    weather = fetch_round_weather(scorecard, start_time)

    return ParsedRound(
        round_id=scorecard["id"],
        course_id=scorecard["courseGlobalId"],

        course=course["name"],
        city=course["city"],
        state=course["state"],

        start_time=start_time,
        end_time=end_time,

        tee_box=scorecard["teeBox"],

        tee_rating=scorecard["teeBoxRating"],
        tee_slope=scorecard["teeBoxSlope"],

        holes_completed=scorecard["holesCompleted"],

        holes=parse_holes(scorecard, course),

        temp_f=weather["temp_f"],
        wind_speed_mph=weather["wind_speed_mph"],
        precip_mm=weather["precip_mm"],

        steps=scorecard["stepsTaken"]
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
        "temp_f": r.temp_f,
        "wind_speed_mph": r.wind_speed_mph,
        "precip_mm": r.precip_mm,
        "steps": r.steps,
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
            "hole_handicap": h.hole_handicap,
            "fairway_outcome": h.fairway_outcome,
        }
        for h in r.holes
    ]


def main():
    data_dir = Path(r"C:\Users\gragg\Projects\enhanced_garmin_golf_analytics\Data")
    json_files = sorted(data_dir.glob("scorecard_*.json"))

    if not json_files:
        raise FileNotFoundError(f"No JSON files found in {data_dir}")

    for json_file in json_files:
        rounds = parse_export(json_file)
        print(f"Parsed {len(rounds)} rounds from {json_file.name}")


if __name__ == "__main__":
    main()