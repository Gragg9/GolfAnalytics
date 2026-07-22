import meteostat as ms
from datetime import datetime, timedelta


def semicircles_to_degrees(semicircles: int) -> float:
    """Convert Garmin semicircle format to decimal degrees."""
    return semicircles * (180 / 2**31)


def parse_garmin_timestamp(ts) -> datetime:
    """Accepts a 'YYYY-MM-DD HH:MM:SS' string or an existing datetime."""
    if isinstance(ts, datetime):
        return ts
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")


def c_to_f(temp_c):
    return None if temp_c is None else round(temp_c * 9 / 5 + 32, 1)


def kmh_to_mph(speed_kmh):
    return None if speed_kmh is None else round(speed_kmh * 0.621371, 1)


def get_weather_near_point(lat_semicircles: int, lon_semicircles: int, start) -> dict:
    """
    Get temp (F), wind speed (mph), and precip (mm) nearest to a given
    time, for the station nearest to a Garmin lat/lon pair (semicircles).

    start: 'YYYY-MM-DD HH:MM:SS' string, or a naive local datetime.
    """
    lat = semicircles_to_degrees(lat_semicircles)
    lon = semicircles_to_degrees(lon_semicircles)
    start_dt = parse_garmin_timestamp(start)

    # Pull the full day so there's an hour on each side to find "nearest" against
    day_start = datetime.combine(start_dt.date(), datetime.min.time())
    day_end = day_start + timedelta(hours=23, minutes=59)

    point = ms.Point(lat, lon)
    stations = ms.stations.nearby(point, limit=5)

    if stations.empty:
        raise ValueError(f"No weather stations found near ({lat:.4f}, {lon:.4f})")

    hourly_row = None
    for station_id in stations.index:
        candidate = ms.hourly(ms.Station(id=station_id), day_start, day_end).fetch()
        if not candidate.empty:
            closest_idx = candidate.index.get_indexer([start_dt], method="nearest")[0]
            hourly_row = candidate.iloc[closest_idx]
            break

    if hourly_row is None:
        raise ValueError(
            f"No hourly weather data available near ({lat:.4f}, {lon:.4f}) "
            f"for {start_dt.date()}"
        )

    return {
        "temp_f": c_to_f(hourly_row.get("temp")),
        "wind_speed_mph": kmh_to_mph(hourly_row.get("wspd")),
        "precip_mm": hourly_row.get("prcp"),
    }