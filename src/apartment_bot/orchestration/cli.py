from __future__ import annotations

import json
from pathlib import Path

from apartment_bot.config import Settings
from apartment_bot.geo.loader import load_geo_dataset


def main() -> None:
    settings = Settings.from_env()
    geo = load_geo_dataset(settings.geo_data_dir)
    summary = {
        "sf_polygons": len(geo.sf_polygons),
        "sf_gyms": len(geo.sf_gyms),
        "peninsula_gyms": len(geo.peninsula_gyms),
        "geo_data_dir": str(Path(settings.geo_data_dir).resolve()),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
