"""Serveur Sentinel-X : caméra, logique de la porte, liaison chiffrée avec l'ESP et dashboard.

    start.bat, ou : python -m sentinel.app --open   (depuis le dossier server) → http://localhost:8000
"""

import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from sentinel import face_id
from sentinel.door import Door, Smoother, pick_face
from sentinel.enroll import FACES_DIR, SHOT_EVERY_S, SHOTS, build_gallery
from sentinel.face_id import (
    CAMERA,
    FaceDetector,
    FaceRecognizer,
    Gallery,
    identify,
    load_gallery,
    save_gallery,
)
from sentinel.guard import Face
from sentinel.mqtt import Link
from sentinel.store import SNAPSHOTS, Store, valid_snapshot

STATIC = Path(__file__).parent / "static"
MIN_FACE_PX = 70  # visage plus étroit (en pixels, image 640×480) = trop loin pour décider
# Le prénom devient un nom de dossier : lettres (accents compris), chiffres, espace, tiret. Jamais de / ni de ..
NAME_RE = re.compile(r"[^\W_][\w\- ]{0,29}")


def valid_name(name: str) -> bool:
    return bool(NAME_RE.fullmatch(name)) and name == name.strip() and "_" not in name


@dataclass
class Enrollment:
    name: str
    taken: int = 0
    last: float = field(default=-1e9)

    @property
    def done(self) -> bool:
        return self.taken >= SHOTS

    def wants_shot(self, faces_in_frame: int, now: float) -> bool:
        return not self.done and faces_in_frame == 1 and now - self.last >= SHOT_EVERY_S

    def record_shot(self, now: float) -> None:
        self.taken += 1
        self.last = now


WARNING = "Personne inconnue. Si vous ne vous éloignez pas de la zone, nous ouvrirons le feu."
# Synthèse vocale de Windows (voix française si installée), lancée à part pour ne pas figer la caméra.
SPEAK_PS = (
    "Add-Type -AssemblyName System.Speech;"
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'fr*' } | Select-Object -First 1;"
    "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) };"
    "$s.Rate = 0; $s.Volume = 100; $s.Speak($env:SENTINEL_SAY)"
)
_speaker: subprocess.Popen[bytes] | None = None


def speak(text: str) -> None:
    """Prononce le texte sur le haut-parleur du PC, sans attendre ; ignoré si une phrase est déjà en cours."""
    global _speaker
    if sys.platform != "win32" or (_speaker is not None and _speaker.poll() is None):
        return
    env = {**os.environ, "SENTINEL_SAY": text}  # le texte passe par l'environnement : jamais interprété comme du code
    _speaker = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", SPEAK_PS], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW)


class Camera:
    """Un seul thread lit la caméra et fait toute la vision : les modèles OpenCV ne se partagent pas entre threads."""

    def __init__(self, door: Door, store: Store) -> None:
        self.door = door
        self.store = store
        self._passage_id = 0
        self.smoother = Smoother()
        self.threshold = face_id.THRESHOLD
        self.gallery: Gallery = {}
        self.jpeg: bytes | None = None
        self.faces: list[dict[str, Any]] = []
        self.ms = 0.0
        self.error = "démarrage de la caméra…"
        self.enrollment: Enrollment | None = None
        self.rebuild_requested = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)

    def _run(self) -> None:
        detector, recognizer = FaceDetector(), FaceRecognizer()
        self.gallery = load_gallery()
        cap = cv2.VideoCapture(CAMERA, cv2.CAP_DSHOW)
        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                self.error = f"caméra {CAMERA} introuvable : vérifiez le câble ou SENTINEL_CAMERA"
                cap.release()
                time.sleep(1)
                cap = cv2.VideoCapture(CAMERA, cv2.CAP_DSHOW)
                continue
            self.error = ""
            if self.rebuild_requested:
                self.rebuild_requested = False
                FACES_DIR.mkdir(parents=True, exist_ok=True)
                self.gallery = build_gallery(detector, recognizer)
                save_gallery(self.gallery)
            self._process(detector.prepare(frame), detector, recognizer)
        cap.release()

    def _process(self, frame: np.ndarray, detector: FaceDetector, recognizer: FaceRecognizer) -> None:
        tick = time.perf_counter()
        rows = detector.detect(frame)
        enrollment = self.enrollment
        if enrollment and enrollment.wants_shot(len(rows), time.monotonic()):
            folder = FACES_DIR / enrollment.name
            folder.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(folder / f"{int(time.time() * 1000)}.jpg"), frame)
            enrollment.record_shot(time.monotonic())
            if enrollment.done:
                self.enrollment = None
                self.rebuild_requested = True

        shown = frame.copy()
        faces = []
        seen: list[Face] = []
        for row in rows:
            x, y, w, h = row[:4].astype(int)
            if w < MIN_FACE_PX:  # trop loin : l'empreinte serait trop floue pour être fiable
                cv2.rectangle(shown, (x, y), (x + w, y + h), (160, 160, 160), 1)
                cv2.putText(shown, "approchez", (x, max(y - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1)
                continue
            face = identify(recognizer.embed(frame, row), self.gallery, self.threshold)
            color = (60, 180, 60) if face.authorized else (40, 40, 220)
            cv2.rectangle(shown, (x, y), (x + w, y + h), color, 2)
            cv2.putText(shown, face_id.label(face), (x, max(y - 8, 16)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            faces.append({"name": face.name, "score": round(face.score, 3)})
            seen.append(face)
        # Pendant un enregistrement, la personne est encore « inconnue » : la porte l'ignore (pas de tir).
        now = time.monotonic()
        chosen = None if enrollment else self.smoother.push(pick_face(seen), now)
        command = self.door.step(chosen, now)
        if self.door.passage_started and chosen is not None:
            snapshot = None
            if not chosen.authorized:
                snapshot = f"{int(time.time() * 1000)}.jpg"
                SNAPSHOTS.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(SNAPSHOTS / snapshot), shown)
            self._passage_id = self.store.add_passage(time.time(), chosen.name, chosen.score, snapshot)
        if command.warn:
            speak(WARNING)
        if command.fire:
            self.store.mark_fired(self._passage_id)
        if enrollment and not enrollment.done:
            hint = f"Enregistrement de {enrollment.name} : {enrollment.taken}/{SHOTS}"
            cv2.putText(shown, hint, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        self.ms = (time.perf_counter() - tick) * 1000
        self.faces = faces
        ok, buf = cv2.imencode(".jpg", shown, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            self.jpeg = buf.tobytes()


store = Store()
link = Link()
camera = Camera(Door(link), store)


def record_reading(reading: dict[str, float]) -> None:
    now = time.time()
    store.add_reading(now, reading)
    if int(now) % 300 == 0:  # environ toutes les 5 min
        store.prune(now)


link.on_climate = record_reading


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    link.start()
    camera.start()
    yield
    camera.stop()
    link.stop()


app = FastAPI(title="Sentinel-X", lifespan=lifespan)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


def mjpeg() -> Iterator[bytes]:
    last = None
    while not camera._stop.is_set():
        jpeg = camera.jpeg
        if jpeg is not None and jpeg is not last:
            last = jpeg
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        time.sleep(0.03)


@app.get("/video")
def video() -> StreamingResponse:
    return StreamingResponse(mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/live")
def live() -> dict[str, Any]:
    enrollment = camera.enrollment
    return {
        "faces": camera.faces,
        "threshold": camera.threshold,
        "ms": round(camera.ms),
        "error": camera.error,
        "enrollment": {"name": enrollment.name, "taken": enrollment.taken, "total": SHOTS} if enrollment else None,
        "rebuilding": camera.rebuild_requested,
        "door": {"state": camera.door.command.state, "text": camera.door.command.text, "armed": camera.door.armed},
        "link": {
            "status": link.status,
            "connected": link.connected,
            "esp_online": link.esp_online,
            "climate": link.climate,
            "climate_age": round(time.time() - link.climate_at) if link.climate_at else None,
        },
    }


@app.get("/api/faces")
def faces() -> list[dict[str, Any]]:
    if not FACES_DIR.exists():
        return []
    return [
        {"name": p.name, "photos": len(list(p.glob("*.jpg")))}
        for p in sorted(FACES_DIR.iterdir())
        if p.is_dir()
    ]


class NewFace(BaseModel):
    name: str


@app.post("/api/faces")
def add_face(body: NewFace) -> dict[str, str]:
    name = body.name.strip()
    if not valid_name(name):
        raise HTTPException(400, "Prénom invalide : lettres, chiffres, espaces et tirets seulement (30 au maximum).")
    if camera.enrollment:
        raise HTTPException(409, f"Un enregistrement est déjà en cours ({camera.enrollment.name}).")
    camera.enrollment = Enrollment(name)
    return {"status": "started"}


@app.delete("/api/faces/{name}")
def delete_face(name: str) -> dict[str, str]:
    folder = FACES_DIR / name
    if not valid_name(name) or not folder.is_dir():
        raise HTTPException(404, "Personne inconnue.")
    shutil.rmtree(folder)
    camera.rebuild_requested = True
    return {"status": "deleted"}


@app.get("/api/passages")
def passages() -> list[dict[str, Any]]:
    return store.passages()


@app.get("/api/readings")
def readings(minutes: int = 60) -> list[dict[str, Any]]:
    minutes = max(1, min(minutes, 24 * 60))
    return store.readings(since=time.time() - minutes * 60)


@app.get("/snapshots/{name}")
def snapshot(name: str) -> FileResponse:
    if not valid_snapshot(name) or not (SNAPSHOTS / name).is_file():
        raise HTTPException(404, "Capture introuvable.")
    return FileResponse(SNAPSHOTS / name, media_type="image/jpeg")


class Arm(BaseModel):
    armed: bool


@app.post("/api/arm")
def arm(body: Arm) -> dict[str, bool]:
    camera.door.armed = body.armed
    return {"armed": camera.door.armed}


class LedTest(BaseModel):
    state: Literal["green", "red", "idle"]


@app.post("/api/control/led")
def control_led(body: LedTest) -> dict[str, str]:
    camera.door.test_led(body.state, time.monotonic())
    return {"led": body.state}


@app.post("/api/control/fire")
def control_fire() -> dict[str, bool]:
    if not camera.door.manual_fire():
        raise HTTPException(409, "Armez d'abord le système pour pouvoir tirer.")
    if camera.door.command.state == "red":
        camera.store.mark_fired(camera._passage_id)
    return {"fired": True}


class Threshold(BaseModel):
    value: float


@app.post("/api/threshold")
def set_threshold(body: Threshold) -> dict[str, float]:
    if not 0.1 <= body.value <= 0.9:
        raise HTTPException(400, "Le seuil doit être entre 0,1 et 0,9.")
    camera.threshold = body.value
    return {"threshold": camera.threshold}


if __name__ == "__main__":
    if "--open" in sys.argv:  # start.bat : ouvre le navigateur une fois le serveur prêt
        threading.Timer(3, webbrowser.open, ["http://localhost:8000"]).start()
    # 127.0.0.1 : le dashboard n'est visible que depuis ce PC (pentest des autres groupes jeudi).
    uvicorn.run(app, host="127.0.0.1", port=8000, timeout_graceful_shutdown=1)
