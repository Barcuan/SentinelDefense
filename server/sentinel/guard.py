"""Logique de la porte : visage + distance + armé → LED, texte, tir. Pure : aucune I/O."""

import math
from dataclasses import dataclass, field

ENTRY_CM = 50.0  # en dessous, l'intrus est « entré dans la salle »
FIRE_COOLDOWN_S = 10.0  # délai minimum entre deux tirs
IDLE_AFTER_S = 3.0  # sans visage pendant ce temps → LED éteintes


@dataclass(frozen=True)
class Face:
    name: str | None  # None = inconnu
    score: float

    @property
    def authorized(self) -> bool:
        return self.name is not None


@dataclass(frozen=True)
class Command:
    state: str  # "idle" | "green" | "red"
    text: str = ""
    fire: bool = False


@dataclass(frozen=True)
class State:
    command: Command = field(default_factory=lambda: Command("idle"))
    last_face_at: float = -math.inf
    last_fire_at: float = -math.inf


def decide(state: State, face: Face | None, distance_cm: float | None, armed: bool, now: float) -> tuple[State, Command]:
    if face is None:
        if now - state.last_face_at > IDLE_AFTER_S:
            cmd = Command("idle")
        else:
            cmd = Command(state.command.state, state.command.text)  # on garde l'affichage, jamais le tir
        return State(cmd, state.last_face_at, state.last_fire_at), cmd

    if face.authorized:
        cmd = Command("green", f"Bienvenue {face.name}")
        return State(cmd, now, state.last_fire_at), cmd

    close = distance_cm is not None and distance_cm < ENTRY_CM
    fire = armed and close and now - state.last_fire_at >= FIRE_COOLDOWN_S
    cmd = Command("red", "ACCES REFUSE", fire)
    return State(cmd, now, now if fire else state.last_fire_at), cmd
