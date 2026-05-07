"""SQLite storage for vehicle listings."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "cars.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS vehicles (
    vin              TEXT PRIMARY KEY,
    stock_number     INTEGER,
    make             TEXT,
    model            TEXT,
    year             INTEGER,
    trim             TEXT,
    mileage          INTEGER,
    price            INTEGER,
    exterior_color   TEXT,
    interior_color   TEXT,
    drivetrain       TEXT,
    engine           TEXT,
    transmission     TEXT,
    cab_style        TEXT,
    bed_length       TEXT,
    location         TEXT,
    features_json    TEXT,
    listed_date      TEXT,
    ingested_at      TEXT NOT NULL,
    source_file      TEXT
);

CREATE INDEX IF NOT EXISTS idx_vehicles_model_year ON vehicles(model, year);
"""

COLUMNS = [
    "vin", "stock_number", "make", "model", "year", "trim", "mileage", "price",
    "exterior_color", "interior_color", "drivetrain", "engine",
    "transmission", "cab_style", "bed_length", "location",
    "features_json", "listed_date", "ingested_at", "source_file",
]


def connect(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Migration for older DBs that predate stock_number.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(vehicles)")}
    if "stock_number" not in cols:
        conn.execute("ALTER TABLE vehicles ADD COLUMN stock_number INTEGER")
    return conn


def upsert_vehicles(conn: sqlite3.Connection, records: Iterable[Mapping]) -> int:
    """Insert or replace vehicles by VIN. Returns count written."""
    now = datetime.utcnow().isoformat(timespec="seconds")
    rows = []
    for r in records:
        if not r.get("vin"):
            continue
        features = r.get("features")
        if isinstance(features, (list, dict)):
            features_json = json.dumps(features)
        else:
            features_json = features
        rows.append((
            r.get("vin"), r.get("stock_number"),
            r.get("make"), r.get("model"), r.get("year"),
            r.get("trim"), r.get("mileage"), r.get("price"),
            r.get("exterior_color"), r.get("interior_color"),
            r.get("drivetrain"), r.get("engine"), r.get("transmission"),
            r.get("cab_style"), r.get("bed_length"), r.get("location"),
            features_json, r.get("listed_date"), now, r.get("source_file"),
        ))
    if not rows:
        return 0
    placeholders = ",".join("?" * len(COLUMNS))
    conn.executemany(
        f"INSERT OR REPLACE INTO vehicles ({','.join(COLUMNS)}) VALUES ({placeholders})",
        rows,
    )
    conn.commit()
    return len(rows)


def load_dataframe(conn: sqlite3.Connection, model: str | None = None):
    import pandas as pd
    sql = "SELECT * FROM vehicles"
    params: tuple = ()
    if model:
        sql += " WHERE model = ?"
        params = (model,)
    return pd.read_sql_query(sql, conn, params=params)
