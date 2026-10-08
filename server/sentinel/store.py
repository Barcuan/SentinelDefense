"""Historique : passages devant la porte et mesures des capteurs (SQLite, dans data/, jamais dans git)."""

import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

from sentinel.alerts import Alert
from sentinel.face_id import ROOT

DB = ROOT / "data" / "sentinel.db"
SNAPSHOTS = ROOT / "data" / "snapshots"
KEEP_READINGS_S = 24 * 3600  # une mesure toutes les 2 s : 24 h ≈ 43 000 lignes
SNAPSHOT_RE = re.compile(r"\d{10,16}\.jpg")


def valid_snapshot(name: str) -> bool:
    return bool(SNAPSHOT_RE.fullmatch(name))


class Store:
    """Utilisé par le thread caméra, le thread MQTT et les requêtes web : une connexion, un verrou."""

    def __init__(self, path: Path = DB) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS passages (
                    id INTEGER PRIMARY KEY, started REAL NOT NULL, name TEXT, score REAL NOT NULL,
                    snapshot TEXT, fired INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS readings (at REAL NOT NULL, temp REAL, hum REAL, gas REAL);
                CREATE INDEX IF NOT EXISTS readings_at ON readings (at);
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY, at REAL NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL,
                    value REAL, source TEXT NOT NULL);
            """)

    def add_passage(self, started: float, name: str | None, score: float, snapshot: str | None) -> int:
        with self._lock, self._db:
            cursor = self._db.execute(
                "INSERT INTO passages (started, name, score, snapshot) VALUES (?, ?, ?, ?)",
                (started, name, score, snapshot))
            return int(cursor.lastrowid or 0)

    def mark_fired(self, passage_id: int) -> None:
        with self._lock, self._db:
            self._db.execute("UPDATE passages SET fired = 1 WHERE id = ?", (passage_id,))

    def passages(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, started, name, score, snapshot, fired FROM passages ORDER BY started DESC, id DESC LIMIT ?",
                (limit,)).fetchall()
        return [{"id": r[0], "started": r[1], "name": r[2], "score": r[3], "snapshot": r[4], "fired": bool(r[5])}
                for r in rows]

    def add_reading(self, at: float, reading: dict[str, float]) -> None:
        with self._lock, self._db:
            self._db.execute("INSERT INTO readings (at, temp, hum, gas) VALUES (?, ?, ?, ?)",
                             (at, reading.get("temp"), reading.get("hum"), reading.get("gas")))

    def readings(self, since: float) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT at, temp, hum, gas FROM readings WHERE at >= ? ORDER BY at", (since,)).fetchall()
        return [{"at": r[0], "temp": r[1], "hum": r[2], "gas": r[3]} for r in rows]

    def prune(self, now: float) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM readings WHERE at < ?", (now - KEEP_READINGS_S,))

    def add_alert(self, alert: Alert) -> None:
        with self._lock, self._db:
            self._db.execute("INSERT INTO alerts (at, kind, message, value, source) VALUES (?, ?, ?, ?, ?)",
                             (alert.at, alert.kind, alert.message, alert.value, alert.source))

    def alerts(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT at, kind, message, value, source FROM alerts ORDER BY at DESC, id DESC LIMIT ?",
                (limit,)).fetchall()
        return [{"at": r[0], "kind": r[1], "message": r[2], "value": r[3], "source": r[4]} for r in rows]
