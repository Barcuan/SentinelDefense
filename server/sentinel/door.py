"""La porte : décide avec guard.decide et n'envoie à l'ESP que ce qui change."""

import time
from collections.abc import Callable
from typing import Protocol

from sentinel.guard import Command, Face, State, decide
from sentinel.mqtt import T_FIRE, T_LED


class Publisher(Protocol):
    def publish(self, topic: str, payload: str, retain: bool = False) -> None: ...


def pick_face(faces: list[Face]) -> Face | None:
    """Un inconnu dans l'image l'emporte : un membre ne fait pas entrer quelqu'un d'autre avec lui."""
    return next((f for f in faces if not f.authorized), faces[0] if faces else None)


class Door:
    def __init__(self, link: Publisher, wall_clock: Callable[[], float] = time.time) -> None:
        self.link = link
        self.wall_clock = wall_clock
        self.armed = False  # toujours désarmé au démarrage
        self.state = State()
        self.command: Command = self.state.command
        self._led: str | None = None
        self._last_shot = 0
        self.on_fire: Callable[[], None] | None = None

    def step(self, face: Face | None, now: float) -> Command:
        self.state, self.command = decide(self.state, face, self.armed, now)
        if self.command.state != self._led:
            self._led = self.command.state
            self.link.publish(T_LED, self._led, retain=True)  # retenu : l'ESP retrouve l'état s'il redémarre
        if self.command.fire:
            # Numéro de tir en secondes (tient dans un long de l'ESP), toujours croissant, jamais retenu.
            self._last_shot = max(self._last_shot + 1, int(self.wall_clock()))
            self.link.publish(T_FIRE, str(self._last_shot))
            if self.on_fire:
                self.on_fire()
        return self.command
