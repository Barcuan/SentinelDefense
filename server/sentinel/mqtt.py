"""Liaison chiffrée avec l'ESP : lance Mosquitto, s'y connecte en TLS, publie les ordres, reçoit les mesures."""

import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt

from sentinel.setup import MQTT_PORT, ROOT, load_env

T_LED = "sentinel/door/led"
T_FIRE = "sentinel/door/fire"
T_CLIMATE = "sentinel/door/climate"
T_STATUS = "sentinel/door/status"

LINK = ROOT / "link"
MOSQUITTO_PLACES = [
    Path(r"C:\Program Files\mosquitto\mosquitto.exe"),
    Path(r"C:\Program Files (x86)\mosquitto\mosquitto.exe"),
]
# Bornes physiques des capteurs : au-delà, la mesure est fausse et on l'ignore.
RANGES = {"temp": (-40.0, 85.0), "hum": (0.0, 100.0), "gas": (0.0, 1024.0)}


def parse_climate(payload: bytes) -> dict[str, float] | None:
    try:
        data = json.loads(payload)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    reading = {}
    for key, (low, high) in RANGES.items():
        if key in data:
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, int | float) or not low <= value <= high:
                return None
            reading[key] = float(value)
    return reading or None


def find_mosquitto(places: list[Path] | None = None) -> Path | None:
    if places is None:
        on_path = shutil.which("mosquitto")
        places = MOSQUITTO_PLACES + ([Path(on_path)] if on_path else [])
    return next((p for p in places if p.is_file()), None)


class Link:
    """Une seule connexion MQTT pour tout le serveur. Sans configuration ou sans Mosquitto, tout le reste marche."""

    def __init__(self) -> None:
        self.status = "liaison non configurée : lancez install.bat"
        self.connected = False
        self.esp_online = False
        self.climate: dict[str, float] = {}
        self.climate_at = 0.0
        self.on_climate: Callable[[dict[str, float]], None] | None = None
        self._broker: subprocess.Popen[bytes] | None = None
        self._client: mqtt.Client | None = None

    def start(self) -> None:
        conf, env = LINK / "mosquitto.conf", load_env(ROOT / ".env")
        if not conf.exists() or "MQTT_PASSWORD" not in env:
            return
        exe = find_mosquitto()
        if exe is None:
            self.status = "Mosquitto introuvable : lancez install.bat"
            return
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self._broker = subprocess.Popen([str(exe), "-c", str(conf)], stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, creationflags=flags)
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sentinel-server")
        client.tls_set(ca_certs=str(LINK / "certs" / "ca.crt"))
        client.username_pw_set(env["MQTT_USER"], env["MQTT_PASSWORD"])
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.reconnect_delay_set(1, 5)
        time.sleep(0.5)  # laisse Mosquitto ouvrir le port
        client.connect_async("localhost", MQTT_PORT, keepalive=10)
        client.loop_start()
        self._client = client
        self.status = "connexion au broker…"

    def stop(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        if self._broker:
            self._broker.terminate()

    def publish(self, topic: str, payload: str, retain: bool = False) -> None:
        if self._client:
            self._client.publish(topic, payload, qos=1, retain=retain)

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, reason: Any, _props: Any) -> None:
        if reason.is_failure:
            self.status = f"broker refuse la connexion : {reason}"
            return
        self.connected = True
        self.status = "liaison chiffrée active"
        client.subscribe([(T_CLIMATE, 0), (T_STATUS, 1)])

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, _flags: Any, _reason: Any, _props: Any) -> None:
        self.connected = False
        self.esp_online = False
        self.status = "broker déconnecté, reconnexion…"

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        if message.topic == T_STATUS:
            self.esp_online = message.payload == b"online"
        elif message.topic == T_CLIMATE:
            reading = parse_climate(message.payload)
            if reading:
                self.climate = {**self.climate, **reading}
                self.climate_at = time.time()
                if self.on_climate:
                    self.on_climate(reading)
