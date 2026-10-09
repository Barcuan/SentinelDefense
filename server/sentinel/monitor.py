"""Supervision du PC serveur : charge CPU/RAM et journal du broker MQTT (connexions acceptées et refusées)."""

import re
import time
from pathlib import Path
from typing import Any

import psutil

_PROCESS = psutil.Process()
_STARTED = time.time()
_LINE = re.compile(r"^(\d{9,11}): (.*)$")
_IP = re.compile(r"\[?(\d{1,3}(?:\.\d{1,3}){3}):\d+\]?")
LOG_TYPES = ("error", "warning", "notice", "information")
psutil.cpu_percent(interval=None)  # amorce : le premier appel ne mesure rien


def runtime_conf(conf: str, log_file: Path) -> str:
    """Même configuration, mais le journal va dans un fichier que le dashboard peut lire."""
    lines = [line for line in conf.splitlines() if not line.startswith(("log_dest", "log_type"))]
    lines += [f"log_dest file {log_file.as_posix()}"] + [f"log_type {t}" for t in LOG_TYPES]
    return "\n".join(lines) + "\n"


def parse_broker_line(line: str) -> dict[str, Any] | None:
    """Traduit une ligne du journal Mosquitto en événement lisible, ou None si c'est du bruit."""
    match = _LINE.match(line.strip())
    if not match:
        return None
    at, message = int(match.group(1)), match.group(2)
    ip_match = _IP.search(message)
    ip = ip_match.group(1) if ip_match else None
    if "not authorised" in message:
        return {"at": at, "level": "refus", "ip": ip, "text": "Connexion refusée : mot de passe absent ou faux"}
    if "protocol error" in message or ("SSL" in message and "disconnected" in message):
        return {"at": at, "level": "refus", "ip": ip, "text": "Connexion refusée : pas de chiffrement TLS valide"}
    if "Denied" in message:
        return {"at": at, "level": "refus", "ip": ip, "text": "Action interdite par les droits : " + message}
    if message.startswith("New client connected"):
        user = re.search(r"u'([^']*)'", message)
        who = user.group(1) if user else "?"
        return {"at": at, "level": "ok", "ip": ip, "text": f"Client accepté (compte {who})"}
    if "disconnected" in message or "closed its connection" in message:
        return {"at": at, "level": "info", "ip": ip, "text": "Client déconnecté"}
    if "running" in message:
        return {"at": at, "level": "info", "ip": None, "text": "Broker démarré"}
    return None


def tail(path: Path, count: int) -> list[str]:
    """Dernières lignes d'un fichier, sans le lire en entier."""
    if not path.exists():
        return []
    with path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 64 * 1024))
        data = f.read().decode("utf-8", errors="replace")
    return [line for line in data.splitlines() if line.strip()][-count:]


def system_stats() -> dict[str, float]:
    memory = psutil.virtual_memory()
    return {
        "cpu": psutil.cpu_percent(interval=None),
        "ram": memory.percent,
        "ram_used_gb": round(memory.used / 1e9, 1),
        "ram_total_gb": round(memory.total / 1e9, 1),
        "process_mb": round(_PROCESS.memory_info().rss / 1e6),
        "uptime_s": round(time.time() - _STARTED),
    }
