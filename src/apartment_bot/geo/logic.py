from __future__ import annotations

import math

from apartment_bot.config import Settings
from apartment_bot.core.models import GeoDataset, GeoMode, GeoQualificationResult, Listing, Point, Polygon


EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1_rad, lng1_rad = math.radians(lat1), math.radians(lng1)
    lat2_rad, lng2_rad = math.radians(lat2), math.radians(lng2)
    delta_lat = lat2_rad - lat1_rad
    delta_lng = lng2_rad - lng1_rad
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def point_in_polygon(lat: float, lng: float, polygon: Polygon) -> bool:
    inside = False
    points = polygon.coordinates
    j = len(points) - 1
    for i, (lat_i, lng_i) in enumerate(points):
        lat_j, lng_j = points[j]
        intersects = ((lng_i > lng) != (lng_j > lng)) and (
            lat < (lat_j - lat_i) * (lng - lng_i) / ((lng_j - lng_i) or 1e-12) + lat_i
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def nearest_point_distance(lat: float, lng: float, points: list[Point]) -> tuple[float | None, Point | None]:
    best_distance: float | None = None
    best_point: Point | None = None
    for point in points:
        distance = haversine_miles(lat, lng, point.lat, point.lng)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_point = point
    return best_distance, best_point


def qualifies_sf(listing: Listing, geo: GeoDataset, settings: Settings) -> GeoQualificationResult:
    if listing.lat is None or listing.lng is None:
        return GeoQualificationResult(False, None, "missing coordinates")

    in_sf_polygon = any(point_in_polygon(listing.lat, listing.lng, polygon) for polygon in geo.sf_polygons)
    if not in_sf_polygon:
        return GeoQualificationResult(False, None, "outside approved SF polygons")

    nearest_distance, nearest_gym = nearest_point_distance(listing.lat, listing.lng, geo.sf_gyms)
    within_gym_radius = nearest_distance is not None and nearest_distance <= settings.sf_gym_threshold_miles

    if within_gym_radius or listing.has_fitness_center:
        reason = "inside SF polygon and near SF gym" if within_gym_radius else "inside SF polygon with on-site fitness"
        return GeoQualificationResult(
            True,
            GeoMode.SAN_FRANCISCO,
            reason,
            distance_to_supporting_gym_miles=nearest_distance,
            supporting_gym_name=nearest_gym.name if nearest_gym else None,
        )

    return GeoQualificationResult(False, None, "inside SF polygon but no nearby SF gym or on-site fitness")


def qualifies_peninsula(listing: Listing, geo: GeoDataset, settings: Settings) -> GeoQualificationResult:
    if listing.lat is None or listing.lng is None:
        return GeoQualificationResult(False, None, "missing coordinates")

    nearest_distance, nearest_gym = nearest_point_distance(listing.lat, listing.lng, geo.peninsula_gyms)
    if nearest_distance is None:
        return GeoQualificationResult(False, None, "no Peninsula gyms configured")

    if nearest_distance <= settings.peninsula_gym_threshold_miles:
        return GeoQualificationResult(
            True,
            GeoMode.PENINSULA,
            "within Peninsula gym threshold",
            distance_to_supporting_gym_miles=nearest_distance,
            supporting_gym_name=nearest_gym.name if nearest_gym else None,
        )

    return GeoQualificationResult(False, None, "outside Peninsula gym threshold")


def qualify_geography(listing: Listing, geo: GeoDataset, settings: Settings) -> GeoQualificationResult:
    sf_result = qualifies_sf(listing, geo, settings)
    if sf_result.qualifies:
        return sf_result
    return qualifies_peninsula(listing, geo, settings)
