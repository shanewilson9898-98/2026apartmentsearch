from __future__ import annotations

import csv
import json
from pathlib import Path

from apartment_bot.core.models import GeoDataset, Point, Polygon


def _load_points_csv(path: Path) -> list[Point]:
    if not path.exists():
        raise FileNotFoundError(f"Missing geo file: {path}")

    points: list[Point] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            lat = row.get("lat") or row.get("latitude")
            lng = row.get("lng") or row.get("lon") or row.get("longitude")
            if lat is None or lng is None:
                raise ValueError(f"{path} row {index} is missing lat/lng columns")
            points.append(
                Point(
                    name=row.get("name") or row.get("gym") or f"{path.stem}_{index}",
                    lat=float(lat),
                    lng=float(lng),
                )
            )
    return points


def _normalize_polygon_coordinates(rings: list[list[list[float]]]) -> list[tuple[float, float]]:
    outer_ring = rings[0]
    return [(float(latlng[1]), float(latlng[0])) for latlng in outer_ring]


def _load_geojson_polygons(path: Path) -> list[Polygon]:
    if not path.exists():
        raise FileNotFoundError(f"Missing geo file: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    polygons: list[Polygon] = []

    for index, feature in enumerate(features, start=1):
        geometry = feature.get("geometry", {})
        geometry_type = geometry.get("type")
        properties = feature.get("properties", {})
        name = properties.get("name") or properties.get("id") or f"sf_polygon_{index}"

        if geometry_type == "Polygon":
            polygons.append(
                Polygon(name=name, coordinates=_normalize_polygon_coordinates(geometry["coordinates"]))
            )
            continue

        if geometry_type == "MultiPolygon":
            for part_index, coords in enumerate(geometry["coordinates"], start=1):
                polygons.append(
                    Polygon(
                        name=f"{name}_{part_index}",
                        coordinates=_normalize_polygon_coordinates(coords),
                    )
                )
            continue

        raise ValueError(f"Unsupported geometry type in {path}: {geometry_type}")

    return polygons


def load_geo_dataset(base_dir: Path) -> GeoDataset:
    return GeoDataset(
        sf_polygons=_load_geojson_polygons(base_dir / "sf_polygons.geojson"),
        sf_gyms=_load_points_csv(base_dir / "sf_gyms.csv"),
        peninsula_gyms=_load_points_csv(base_dir / "peninsula_gyms.csv"),
    )
