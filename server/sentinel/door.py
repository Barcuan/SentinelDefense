"""La porte : décide avec guard.decide et n'envoie à l'ESP que ce qui change."""

import time
from collections import Counter, deque
from collections.abc import Callable
from typing import Protocol

from sentinel.guard import Command, Face, State, decide
from sentinel.mqtt import T_FIRE, T_LED


class Publisher(Protocol):
    def publish(self, topic: str, payload: str, retain: bool = False) -> None: ...


def pick_face(faces: list[Face]) -> Face | None:
    """Un membre dans l'image l'emporte : il accompagne l'inconnu, donc ni avertissement ni tir (choix de l'équipe)."""
    return next((f for f in faces if f.authorized), faces[0] if faces else None)


WINDOW_S = 0.6  # on juge sur ~0,6 s d'images, pas sur une seule
MIN_FRAMES = 4  # pas de verdict avant d'avoir vu au moins 4 images
MAJORITY = 0.7  # un verdict (prénom ou inconnu) doit tenir sur 70 % des images de la fenêtre


class Smoother:
    """Évite qu'une seule image « sosie » allume le vert, et qu'une personne clignote entre connu et inconnu."""

    def __init__(self) -> None:
        self._frames: deque[tuple[float, Face]] = deque()
        self._verdict: Face | None = None

    def push(self, face: Face | None, now: float) -> Face | None:
        if face is None:
            return None
        self._frames.append((now, face))
        while self._frames and self._frames[0][0] < now - WINDOW_S:
            self._frames.popleft()
        if len(self._frames) < MIN_FRAMES:
            return self._verdict if self._verdict and self._verdict.name == face.name else None
        name, count = Counter(f.name for _, f in self._frames).most_common(1)[0]
        if count / len(self._frames) >= MAJORITY:
            scores = [f.score for _, f in self._frames if f.name == name]
            self._verdict = Face(name, sum(scores) / len(scores))
        return self._verdict


class Door:
    def __init__(self, link: Publisher, wall_clock: Callable[[], float] = time.time) -> None:
        self.link = link
        self.wall_clock = wall_clock
        self.armed = False  # toujours désarmé au démarrage
        self.state = State()
        self.command: Command = self.state.command
        self._led: str | None = None
        self._last_shot = 0
        self._passage: tuple[str, str | None] | None = None
        self.passage_started = False  # vrai pendant l'image où une nouvelle personne apparaît

    def step(self, face: Face | None, now: float) -> Command:
        self.state, self.command = decide(self.state, face, self.armed, now)
        if self.command.state != self._led:
            self._led = self.command.state
            self.link.publish(T_LED, self._led, retain=True)  # retenu : l'ESP retrouve l'état s'il redémarre
        if self.command.fire:
            # Numéro de tir en secondes (tient dans un long de l'ESP), toujours croissant, jamais retenu.
            self._last_shot = max(self._last_shot + 1, int(self.wall_clock()))
            self.link.publish(T_FIRE, str(self._last_shot))
        self._track_passage(face)
        return self.command

    def _track_passage(self, face: Face | None) -> None:
        """Un passage = une personne (connue ou non) jusqu'au retour à l'état idle : une ligne d'historique, pas une par image."""
        self.passage_started = False
        if self.command.state == "idle":
            self._passage = None
        elif face is not None and (self.command.state, face.name) != self._passage:
            self._passage = (self.command.state, face.name)
            self.passage_started = True
