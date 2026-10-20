"""Seeded illustrative synthetic datasets; these are not experimental findings."""

import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

rng = random.Random(42)
root = Path(__file__).resolve().parents[1] / "sample_data"
root.mkdir(exist_ok=True)
with (root / "plant_growth_synthetic.csv").open("w", newline="") as f:
    writer = csv.writer(f, lineterminator="\n")
    writer.writerow(
        [
            "observation_date",
            "treatment_group",
            "temperature_c",
            "light_hours",
            "plant_height_cm",
        ]
    )
    for day in range(60):
        for group, effect in [("Control", 0), ("Nutrient A", 4), ("Nutrient B", 7)]:
            temp = round(21 + 3 * math.sin(day / 8) + rng.gauss(0, 1.4), 2)
            light = round(rng.uniform(9, 15), 1)
            height = round(
                6
                + day * 0.38
                + effect
                + 0.28 * (temp - 21)
                + 0.35 * (light - 12)
                + rng.gauss(0, 1.8),
                2,
            )
            writer.writerow(
                [
                    (datetime(2026, 3, 1) + timedelta(days=day)).date(),
                    group,
                    temp,
                    "" if day % 23 == 0 else light,
                    "" if day % 29 == 0 and group == "Control" else max(height, 1),
                ]
            )
with (root / "environment_synthetic.csv").open("w", newline="") as f:
    writer = csv.writer(f, lineterminator="\n")
    writer.writerow(
        ["timestamp", "location", "temperature_c", "humidity_percent", "co2_ppm"]
    )
    for hour in range(168):
        for location, offset in [
            ("Forest station", -2),
            ("Urban station", 2),
            ("Coastal station", 0),
        ]:
            temp = round(
                16 + offset + 5 * math.sin(hour / 24 * 2 * math.pi) + rng.gauss(0, 0.8),
                2,
            )
            humidity = round(min(99, max(15, 90 - temp * 1.6 + rng.gauss(0, 5))), 2)
            co2 = round(
                420 + (90 if location == "Urban station" else 0) + rng.gauss(0, 18), 1
            )
            writer.writerow(
                [
                    (datetime(2026, 5, 1) + timedelta(hours=hour)).isoformat(),
                    location,
                    temp,
                    "" if hour % 31 == 0 else humidity,
                    co2,
                ]
            )
