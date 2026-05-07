"""Synthetic Toyota Tacoma listings so the app is usable before you've saved real pages.

The pricing curve here is a rough approximation, not market truth — replace
with real listing data as you ingest it.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

TRIMS = {
    "SR":          {"base": 28000, "weight": 0.10},
    "SR5":         {"base": 32000, "weight": 0.30},
    "TRD Sport":   {"base": 36000, "weight": 0.20},
    "TRD Off-Road":{"base": 38000, "weight": 0.20},
    "Limited":     {"base": 42000, "weight": 0.10},
    "TRD Pro":     {"base": 48000, "weight": 0.05},
    "TRD Pro Hybrid":{"base":54000,"weight": 0.05},
}
DRIVETRAINS = ["4WD", "RWD"]
CAB_STYLES = ["Double Cab", "Access Cab", "CrewMax"]
COLORS = ["Magnetic Gray", "Cement", "Super White", "Midnight Black",
          "Barcelona Red", "Lunar Rock", "Solar Octane"]
LOCATIONS = ["Sacramento, CA", "San Jose, CA", "Fremont, CA", "Roseville, CA",
             "Concord, CA", "Modesto, CA"]


def _vin(seed: int) -> str:
    rng = random.Random(seed)
    chars = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    return "5TF" + "".join(rng.choices(chars, k=14))


def _depreciate(base: float, age: int) -> float:
    # 18% first year, then 10%/yr compounding.
    if age <= 0:
        return base
    val = base * 0.82
    for _ in range(age - 1):
        val *= 0.90
    return val


def generate(n: int = 200, *, current_year: int = 2026, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    trim_names = list(TRIMS.keys())
    weights = [TRIMS[t]["weight"] for t in trim_names]
    listed_after = datetime(current_year, 1, 1) - timedelta(days=120)

    records: list[dict] = []
    for i in range(n):
        trim = rng.choices(trim_names, weights=weights, k=1)[0]
        year = rng.randint(current_year - 7, current_year)
        age = current_year - year
        # Higher mileage on older trucks; some variance.
        mean_miles = age * 12000 + rng.randint(-4000, 6000)
        mileage = max(50, mean_miles)

        msrp_base = TRIMS[trim]["base"]
        # Newer trims (hybrid) didn't exist before 2024.
        if trim == "TRD Pro Hybrid" and year < 2024:
            trim = "TRD Pro"

        expected = _depreciate(msrp_base, age) - mileage * 0.08
        # Drivetrain adjustment.
        drivetrain = rng.choices(DRIVETRAINS, weights=[0.75, 0.25])[0]
        if drivetrain == "RWD":
            expected -= 1500
        cab = rng.choices(CAB_STYLES, weights=[0.55, 0.10, 0.35])[0]
        if cab == "CrewMax":
            expected += 1200
        elif cab == "Access Cab":
            expected -= 800

        # Listing noise.
        price = max(8000, int(expected + rng.gauss(0, 1500)))

        listed = listed_after + timedelta(days=rng.randint(0, 120))
        records.append({
            "vin": _vin(i),
            "make": "Toyota",
            "model": "Tacoma",
            "year": year,
            "trim": trim,
            "mileage": mileage,
            "price": price,
            "exterior_color": rng.choice(COLORS),
            "interior_color": rng.choice(["Black", "Cement", "Saddle Tan"]),
            "drivetrain": drivetrain,
            "engine": "3.5L V6" if year < 2024 else "2.4L i-FORCE Turbo",
            "transmission": "Automatic",
            "cab_style": cab,
            "bed_length": rng.choice(["5 ft", "6 ft"]),
            "location": rng.choice(LOCATIONS),
            "features": [],
            "listed_date": listed.date().isoformat(),
            "source_file": "seed",
        })
    return records
