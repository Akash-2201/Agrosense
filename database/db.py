import sqlite3
import json
from datetime import datetime

DB_PATH = "database/agrosense.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS soil_readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_id     TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL,
            moisture    REAL,
            category    TEXT,
            image_path  TEXT
        );
        CREATE TABLE IF NOT EXISTS disease_scans (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_id     TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL,
            plant_type  TEXT,
            disease     TEXT,
            confidence  REAL,
            image_path  TEXT
        );
        CREATE TABLE IF NOT EXISTS farms (
            id          TEXT PRIMARY KEY,
            name        TEXT,
            location    TEXT,
            crops       TEXT
        );
    """)
    conn.commit()
    conn.close()

def save_soil_reading(farm_id, moisture, category, image_path):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO soil_readings (farm_id, timestamp, moisture, category, image_path) VALUES (?,?,?,?,?)",
        (farm_id, datetime.utcnow().isoformat(), moisture, category, image_path)
    )
    conn.commit()
    conn.close()

def get_soil_history(farm_id, days=30):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT timestamp, moisture, category FROM soil_readings "
        "WHERE farm_id=? ORDER BY timestamp DESC LIMIT ?",
        (farm_id, days)
    ).fetchall()
    conn.close()
    return [{"timestamp": r[0], "moisture": r[1], "category": r[2]} for r in rows]