"""Logique de la porte : visage + armé → LED, texte, tir. Pure : aucune I/O."""

import math
from dataclasses import dataclass, field

RED_BEFORE_FIRE_S = 3.0  # un visage doit rester inconnu ce temps avant le tir (évite un tir sur une erreur d'une image)
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
    red_since: float = math.inf  # début de l'état rouge en cours, inf hors rouge


def decide(state: State, face: Face | None, armed: bool, now: float) -> tuple[State, Command]:
    if face is None:
        if now - state.last_face_at > IDLE_AFTER_S:
            cmd = Command("idle")
            return State(cmd, state.last_face_at, state.last_fire_at), cmd
        cmd = Command(state.command.state, state.command.text)  # on garde l'affichage, jamais le tir
        return State(cmd, state.last_face_at, state.last_fire_at, state.red_since), cmd

    if face.authorized:
        cmd = Command("green", f"Bienvenue {face.name}")
        return State(cmd, now, state.last_fire_at), cmd

    red_since = state.red_since if state.command.state == "red" else now
    fire = armed and now - red_since >= RED_BEFORE_FIRE_S and now - state.last_fire_at >= FIRE_COOLDOWN_S
    cmd = Command("red", "ACCES REFUSE", fire)
    return State(cmd, now, now if fire else state.last_fire_at, red_since), cmd
