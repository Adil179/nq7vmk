from pathlib import Path
from zoneinfo import ZoneInfo

ELEXON_BASE = "https://data.elexon.co.uk/bmrs/api/v1"
LONDON = ZoneInfo("Europe/London")

# EPEX SPOT GB 60-minute day-ahead auction order-book close (clock time, D-1).
DA_GATE_HOUR = 9
DA_GATE_MINUTE = 20

DELIVERY_START = "2026-01-01"
DELIVERY_END = "2026-01-31"
PUBLISH_FROM = "2025-12-30T00:00:00Z"
PUBLISH_TO = "2026-01-31T23:59:59Z"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_PATH = DATA_DIR / "processed.json"

# Average of two FUELHH periods is treated as the hourly actual matching WINDFOR.
HOURLY_MINUTES = 60
