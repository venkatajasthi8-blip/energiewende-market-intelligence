import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("EMI_DB", ROOT / "data" / "energy.db"))
START_DATE = os.getenv("EMI_START", "2024-01-01")
DATA_URL = os.getenv("EMI_DATA_URL", "")  # where the deployed app downloads the database from
TZ = "Europe/Berlin"

# key -> (SMARD filter id, display name, category, min allowed, max allowed)
# The min/max values are only there to catch broken data, not unusual market days.
# -500 / 4000 EUR/MWh are the official price limits of the day-ahead auction.
SERIES = {
    "price":              (4169, "Day-ahead price", "price", -500, 4000),
    "load":               (410, "Grid load", "demand", 20_000, 100_000),
    "residual_load":      (4359, "Residual load", "demand", -40_000, 100_000),
    "wind_onshore":       (4067, "Wind onshore", "renewable", 0, 80_000),
    "wind_offshore":      (1225, "Wind offshore", "renewable", 0, 15_000),
    "solar":              (4068, "Solar", "renewable", 0, 90_000),
    "biomass":            (4066, "Biomass", "renewable", 0, 10_000),
    "hydro":              (1226, "Hydro", "renewable", 0, 6_000),
    "other_renewables":   (1228, "Other renewables", "renewable", 0, 3_000),
    "lignite":            (1223, "Lignite", "conventional", 0, 25_000),
    "hard_coal":          (4069, "Hard coal", "conventional", 0, 25_000),
    "gas":                (4071, "Gas", "conventional", 0, 35_000),
    "nuclear":            (1224, "Nuclear", "conventional", 0, 12_000),
    "other_conventional": (1227, "Other conventional", "conventional", 0, 10_000),
    "pumped_storage":     (4070, "Pumped storage", "storage", 0, 12_000),
}

RENEWABLES = [k for k, v in SERIES.items() if v[2] == "renewable"]
CONVENTIONAL = [k for k, v in SERIES.items() if v[2] == "conventional"]
GENERATION = RENEWABLES + CONVENTIONAL + ["pumped_storage"]