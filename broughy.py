"""
broughy.py — loads Broughy1322's CSV data and provides vehicle stat lookups.
CSVs live in the data/ folder and are not committed to the repo.
"""
import csv
import os
import re

CSV_DIR = os.path.join(os.path.dirname(__file__), "data")

# ─── Unicode normalisation ────────────────────────────────────────────────────

def _normalise(name: str) -> str:
    """Lowercase, strip manufacturer prefix, normalise special chars."""
    name = name.strip()
    # Normalise unicode chars: × -> x, – -> -, etc.
    name = name.replace("\u00d7", "x").replace("\u2013", "-").replace("\u2014", "-")
    name = name.replace("\u00e9", "e").replace("\u00fc", "u").replace("\u00f6", "o")
    name = re.sub(r"\s+", " ", name).strip().lower()
    return name


def _name_candidates(full_name: str) -> list[str]:
    """Return name variants to try when looking up a vehicle."""
    norm = _normalise(full_name)
    words = norm.split()
    candidates = [norm]  # full normalised name
    if len(words) >= 2:
        candidates.append(" ".join(words[1:]))   # drop manufacturer
    if len(words) >= 3:
        candidates.append(" ".join(words[-2:]))  # last 2 words
    if len(words) >= 2:
        candidates.append(words[-1])             # last word only
    return candidates


# ─── CSV loader ───────────────────────────────────────────────────────────────

def _load_csv(filename: str, header_row: int = 1) -> tuple[list[str], list[dict]]:
    """Load a Broughy CSV with merged two-row headers."""
    path = os.path.join(CSV_DIR, filename)
    if not os.path.exists(path):
        return [], []
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    h1 = rows[header_row] if len(rows) > header_row else []
    h2 = rows[header_row + 1] if len(rows) > header_row + 1 else [""] * len(h1)
    headers = []
    for a, b in zip(h1, h2):
        a, b = a.strip(), b.strip()
        if a and b:
            headers.append(f"{a}|{b}")
        elif a:
            headers.append(a)
        else:
            headers.append(b)
    data = []
    for row in rows[header_row + 2:]:
        if any(cell.strip() for cell in row):
            data.append(dict(zip(headers, [c.strip() for c in row])))
    return headers, data


# ─── Lookup tables (loaded once) ─────────────────────────────────────────────

_speed_lookup: dict[str, dict] | None = None
_info_lookup: dict[str, dict] | None = None
_handling_lookup: dict[str, dict] | None = None


def _build_lookup(data: list[dict], key_field: str = "Vehicle") -> dict[str, dict]:
    """Build lookup keyed by normalised vehicle name.
    For entries with year suffixes like 'Police Bike (2025)' and 'Police Bike (2013)',
    strip the year and keep the most recent (highest year) entry.
    """
    import re as _re
    lookup = {}
    year_re = _re.compile(r"\s*\((\d{4})\)\s*$")
    for row in data:
        raw_name = row.get(key_field, "").strip()
        if not raw_name:
            continue
        year_m = year_re.search(raw_name)
        year = int(year_m.group(1)) if year_m else 0
        base_name = year_re.sub("", raw_name).strip()
        key = _normalise(base_name)
        # Keep entry with highest year (most recent)
        existing = lookup.get(key)
        if existing is None:
            lookup[key] = row
        else:
            existing_year_m = year_re.search(existing.get(key_field, ""))
            existing_year = int(existing_year_m.group(1)) if existing_year_m else 0
            if year > existing_year:
                lookup[key] = row
    return lookup


def _get_speed_lookup() -> dict[str, dict]:
    global _speed_lookup
    if _speed_lookup is None:
        _, data = _load_csv("speed_tiers.csv")
        _speed_lookup = _build_lookup(data)
    return _speed_lookup


def _get_info_lookup() -> dict[str, dict]:
    global _info_lookup
    if _info_lookup is None:
        _, data = _load_csv("vehicle_info.csv")
        _info_lookup = _build_lookup(data)
    return _info_lookup


def _get_handling_lookup() -> dict[str, dict]:
    global _handling_lookup
    if _handling_lookup is None:
        _, data = _load_csv("handling_data.csv")
        _handling_lookup = _build_lookup(data)
    return _handling_lookup


def _find(lookup: dict, full_name: str) -> dict | None:
    for candidate in _name_candidates(full_name):
        if candidate in lookup:
            return lookup[candidate]
    return None


# ─── Public API ───────────────────────────────────────────────────────────────

def get_vehicle_stats(name: str) -> dict:
    """Return a stats dict for a vehicle, sourced from Broughy's CSVs.

    Returns:
        {
            "top_speed_mph":     float | None,
            "top_speed_kph":     float | None,
            "top_speed_rank_class":   int | None,
            "lap_time":          str | None,   # "1:32.093"
            "lap_time_rank_class":    int | None,
            "vehicle_class":     str | None,
            "seats":             int | None,
            "drivetrain":        str | None,   # "RWD", "FWD", "AWD (30F/70R)"
        }
    """
    speed_row = _find(_get_speed_lookup(), name)
    info_row  = _find(_get_info_lookup(), name)
    hdl_row   = _find(_get_handling_lookup(), name)

    result = {
        "top_speed_mph": None,
        "top_speed_kph": None,
        "top_speed_rank_class": None,
        "lap_time": None,
        "lap_time_rank_class": None,
        "vehicle_class": None,
        "seats": None,
        "drivetrain": None,
        "price_csv": None,
    }

    # ── Speed & lap time ──────────────────────────────────────────────────────
    if speed_row:
        result["vehicle_class"] = speed_row.get("Class") or None

        mph_raw = speed_row.get("Top Speed (mph)", "").strip()
        if mph_raw and mph_raw not in ("-", ""):
            try:
                mph = float(mph_raw)
                result["top_speed_mph"] = mph
                result["top_speed_kph"] = round(mph * 1.60934, 1)
            except ValueError:
                pass

        lap_raw = speed_row.get("Lap Time (m:ss.000)", "").strip()
        if lap_raw and lap_raw not in ("-", ""):
            result["lap_time"] = lap_raw

        rank_class_raw = speed_row.get("Lap Time Position|In Class", "").strip()
        if rank_class_raw and rank_class_raw not in ("-", ""):
            try:
                result["lap_time_rank_class"] = int(rank_class_raw)
            except ValueError:
                pass

        speed_rank_raw = speed_row.get("Top Speed Position|In Class", "").strip()
        if speed_rank_raw and speed_rank_raw not in ("-", ""):
            try:
                result["top_speed_rank_class"] = int(speed_rank_raw)
            except ValueError:
                pass

    # ── Seats & Price ────────────────────────────────────────────────────────
    if info_row:
        if not result["vehicle_class"]:
            result["vehicle_class"] = info_row.get("Class") or None
        seats_raw = info_row.get("Seats", "").strip()
        if seats_raw and seats_raw not in ("-", ""):
            try:
                result["seats"] = int(seats_raw)
            except ValueError:
                pass
        cost_raw = info_row.get("Cost", "").strip()
        if cost_raw and cost_raw not in ("-", ""):
            result["price_csv"] = "$" + cost_raw

    # ── Drivetrain ────────────────────────────────────────────────────────────
    if hdl_row:
        if not result["vehicle_class"]:
            result["vehicle_class"] = hdl_row.get("Class") or None
        drive = hdl_row.get("Acceleration|Drivetrain", "").strip()
        front_pct_raw = hdl_row.get("Power To Front", "").strip().replace("%", "")
        if drive == "AWD" and front_pct_raw and front_pct_raw not in ("-", ""):
            try:
                front = int(float(front_pct_raw))
                rear = 100 - front
                result["drivetrain"] = f"AWD ({front}F/{rear}R)"
            except ValueError:
                result["drivetrain"] = "AWD"
        elif drive:
            result["drivetrain"] = drive

    return result


def csvs_available() -> bool:
    """Return True if at least the speed tiers CSV exists."""
    return os.path.exists(os.path.join(CSV_DIR, "speed_tiers.csv"))