"""Alertes environnement : fuite de gaz (par rapport à l'air habituel de la pièce) et surchauffe."""

import os
import statistics
from collections import deque
from dataclasses import dataclass

GAS_RISE = float(os.environ.get("SENTINEL_GAS_RISE", "80"))  # au-dessus de la valeur habituelle (0–1023)
TEMP_MAX = float(os.environ.get("SENTINEL_TEMP_MAX", "45"))  # °C : au-delà, surchauffe
BASELINE_S = 600  # valeur habituelle du gaz = médiane des 10 dernières minutes
MIN_SAMPLES = 30  # ~1 min de mesures avant de juger le gaz (le capteur chauffe au démarrage)


@dataclass(frozen=True)
class Alert:
    at: float
    kind: str  # "gas", "temp", ou le type envoyé à l'API
    message: str
    value: float | None
    source: str  # "capteurs" ou "api"


class AlertMonitor:
    def __init__(self) -> None:
        self._gas: deque[tuple[float, float]] = deque()
        self.active: dict[str, Alert] = {}

    def push(self, reading: dict[str, float], now: float) -> list[Alert]:
        """Renvoie les alertes qui commencent maintenant (une seule par épisode)."""
        started = []
        gas = reading.get("gas")
        if gas is not None:
            baseline = self._baseline(now)
            if baseline is not None:
                high = gas >= baseline + GAS_RISE
                back = gas < baseline + GAS_RISE / 2  # hystérésis : pas de clignotement autour du seuil
                started += self._update("gas", high, back, gas, now,
                                        f"Fuite de gaz : {gas:.0f} (habituel {baseline:.0f})")
            if "gas" not in self.active:  # une fuite ne doit pas devenir la nouvelle valeur habituelle
                self._gas.append((now, gas))
        temp = reading.get("temp")
        if temp is not None:
            started += self._update("temp", temp >= TEMP_MAX, temp < TEMP_MAX - 2, temp, now,
                                    f"Surchauffe : {temp:.1f} °C")
        return started

    def external(self, kind: str, message: str, value: float | None, now: float) -> Alert:
        alert = Alert(now, kind, message, value, "api")
        self.active[kind] = alert
        return alert

    def clear(self, kind: str) -> None:
        self.active.pop(kind, None)

    def _baseline(self, now: float) -> float | None:
        while self._gas and self._gas[0][0] < now - BASELINE_S:
            self._gas.popleft()
        if len(self._gas) < MIN_SAMPLES:
            return None
        return statistics.median(v for _, v in self._gas)

    def _update(self, kind: str, high: bool, back: bool, value: float, now: float, message: str) -> list[Alert]:
        if kind in self.active:
            if back:
                del self.active[kind]
            return []
        if high:
            self.active[kind] = Alert(now, kind, message, value, "capteurs")
            return [self.active[kind]]
        return []
