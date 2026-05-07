"""Parse saved vehicle-listing pages into normalized records.

Supports three input formats:

- HTML — saved search-results page. The source site embeds the first
  page of listings as an inline JSON array.
- HAR — Safari/Chrome network export. Captures every listings API
  response as you scroll, so a single HAR can yield hundreds of
  listings.
- JSON — a raw API response body saved manually.

In every case we locate listing-shaped objects (vin + basePrice) and
dedupe by VIN.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

# Marker for a JSON array of listings: opening "[" then an object with stockNumber.
_LISTING_ARRAY_RE = re.compile(r'\[\s*\{\s*"stockNumber"\s*:')


def _scan_balanced_array(text: str, start: int) -> str | None:
    """Return the JSON array starting at text[start] (which must be '['),
    respecting string literals and escapes. Returns None if unbalanced."""
    if text[start] != "[":
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _looks_like_vehicle(d: dict) -> bool:
    return (
        isinstance(d, dict)
        and isinstance(d.get("vin"), str)
        and len(d["vin"]) >= 11
        and isinstance(d.get("basePrice"), (int, float))
        and d["basePrice"] > 1000
    )


def _normalize_body(body: str | None) -> str | None:
    """'4D Crew Cab' -> 'Crew Cab'. Strip leading door-count token like '4D' or '2D'."""
    if not body:
        return body
    return re.sub(r"^\s*\d+D\s+", "", body).strip() or body


def _normalize_drivetrain(dt: str | None) -> str | None:
    if not dt:
        return dt
    m = {
        "four wheel drive": "4WD",
        "all wheel drive": "AWD",
        "rear wheel drive": "RWD",
        "front wheel drive": "FWD",
        "two wheel drive": "2WD",
    }
    return m.get(dt.strip().lower(), dt)


def _engine_string(d: dict) -> str | None:
    size = d.get("engineSize")
    cyl = d.get("cylinders")
    fuel = d.get("engineType")  # 'Gas', 'Hybrid', etc.
    parts = [str(p) for p in (size, f"{cyl}cyl" if cyl else None, fuel) if p]
    return " ".join(parts) or None


def _normalize(d: dict, source_file: str) -> dict:
    return {
        "vin": d.get("vin"),
        "stock_number": d.get("stockNumber"),
        "make": d.get("make"),
        "model": d.get("model"),
        "year": d.get("year"),
        "trim": d.get("trim"),
        "mileage": d.get("mileage"),
        "price": int(d["basePrice"]) if isinstance(d.get("basePrice"), (int, float)) else None,
        "exterior_color": d.get("exteriorColor"),
        "interior_color": d.get("interiorColor"),
        "drivetrain": _normalize_drivetrain(d.get("driveTrain")),
        "engine": _engine_string(d),
        "transmission": d.get("transmission"),
        "cab_style": _normalize_body(d.get("body")),
        "bed_length": d.get("bedLength"),
        "location": ", ".join(
            p for p in (d.get("storeCity"), d.get("stateAbbreviation")) if p
        ) or d.get("storeName"),
        "features": d.get("features") or d.get("packages"),
        "listed_date": d.get("lastMadeSaleableDate"),
        "source_file": source_file,
    }


def _walk(obj: Any) -> Iterable[dict]:
    """Yield every dict nested anywhere inside obj."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _records_from_text(text: str, source_file: str,
                       seen: set[str]) -> list[dict]:
    """Find every inline JSON listings array in `text` and normalize."""
    out: list[dict] = []
    for match in _LISTING_ARRAY_RE.finditer(text):
        raw = _scan_balanced_array(text, match.start())
        if raw is None:
            continue
        try:
            arr = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(arr, list):
            continue
        for item in arr:
            if not _looks_like_vehicle(item):
                continue
            rec = _normalize(item, source_file=source_file)
            vin = rec["vin"]
            if not vin or vin in seen:
                continue
            seen.add(vin)
            out.append(rec)
    return out


def _records_from_json(data: Any, source_file: str,
                       seen: set[str]) -> list[dict]:
    """Walk a parsed-JSON value and pull out every listing-shaped dict."""
    out: list[dict] = []
    for d in _walk(data):
        if not _looks_like_vehicle(d):
            continue
        rec = _normalize(d, source_file=source_file)
        vin = rec["vin"]
        if not vin or vin in seen:
            continue
        seen.add(vin)
        out.append(rec)
    return out


def parse_html_file(path: Path) -> list[dict]:
    """Listings from a saved search-results HTML page."""
    return _records_from_text(
        path.read_text(encoding="utf-8", errors="ignore"),
        source_file=path.name,
        seen=set(),
    )


def parse_json_file(path: Path) -> list[dict]:
    """Listings from a raw API response body saved as .json."""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return []
    return _records_from_json(data, source_file=path.name, seen=set())


def parse_har_file(path: Path) -> list[dict]:
    """Listings from a Safari/Chrome HAR network export.

    Walks every captured response body, parsing each as JSON and pulling
    listing-shaped objects out. A single HAR captured while scrolling
    typically yields all the listings the user loaded in the browser.
    """
    try:
        har = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return []
    seen: set[str] = set()
    records: list[dict] = []
    for entry in har.get("log", {}).get("entries", []):
        body = (entry.get("response") or {}).get("content", {}).get("text") or ""
        if not body or "stockNumber" not in body:
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            # Some HAR exports embed non-JSON; fall back to text scan.
            records.extend(_records_from_text(body, path.name, seen))
            continue
        records.extend(_records_from_json(data, path.name, seen))
    return records


def parse_directory(dir_path: Path) -> list[dict]:
    """Parse every .html / .htm / .har / .json file in dir_path."""
    records: list[dict] = []
    for path in sorted(dir_path.iterdir()):
        suffix = path.suffix.lower()
        if suffix in (".html", ".htm"):
            records.extend(parse_html_file(path))
        elif suffix == ".har":
            records.extend(parse_har_file(path))
        elif suffix == ".json":
            records.extend(parse_json_file(path))
    return records
