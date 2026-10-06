"""Enregistrer les visages autorisés.

    python -m sentinel.enroll --capture Sacha   prend 10 photos à la webcam, puis recalcule
    python -m sentinel.enroll                   recalcule data/faces.npz depuis data/faces/<nom>/*.jpg
"""

import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from sentinel.face_id import (
    CAMERA,
    GALLERY,
    ROOT,
    FaceDetector,
    FaceRecognizer,
    Gallery,
    save_gallery,
)

FACES_DIR = ROOT / "data" / "faces"
SHOTS = 10
SHOT_EVERY_S = 0.7  # bougez un peu la tête entre deux photos : angles différents = meilleure reconnaissance


def largest(faces: np.ndarray) -> np.ndarray:
    return faces[np.argmax(faces[:, 2] * faces[:, 3])]


def build_gallery(detector: FaceDetector, recognizer: FaceRecognizer, faces_dir: Path = FACES_DIR) -> Gallery:
    gallery: Gallery = {}
    for person in sorted(p for p in faces_dir.iterdir() if p.is_dir()):
        embeddings = []
        for image in sorted(person.glob("*.jpg")):
            raw = cv2.imread(str(image))
            if raw is None:
                print(f"  illisible, ignorée : {image.name}")
                continue
            frame = detector.prepare(raw)
            faces = detector.detect(frame)
            if len(faces):
                embeddings.append(recognizer.embed(frame, largest(faces)))
        print(f"{person.name} : {len(embeddings)} photo(s) utilisable(s)")
        if embeddings:
            gallery[person.name] = np.stack(embeddings)
    return gallery


def capture(name: str, detector: FaceDetector, camera: int = CAMERA) -> None:
    """Prend SHOTS photos où l'on voit exactement un visage. Échap pour arrêter avant."""
    folder = FACES_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(camera, cv2.CAP_DSHOW)
    taken, last = 0, 0.0
    while taken < SHOTS and cv2.waitKey(1) != 27:
        ok, frame = cap.read()
        if not ok:
            break
        frame = detector.prepare(frame)
        faces = detector.detect(frame)
        if len(faces) == 1 and time.monotonic() - last >= SHOT_EVERY_S:
            cv2.imwrite(str(folder / f"{int(time.time() * 1000)}.jpg"), frame)
            taken, last = taken + 1, time.monotonic()
        shown = frame.copy()
        for x, y, w, h in faces[:, :4].astype(int):
            cv2.rectangle(shown, (x, y), (x + w, y + h), (0, 200, 0), 2)
        hint = f"{name} : {taken}/{SHOTS}" if len(faces) == 1 else "un seul visage face a la camera"
        cv2.putText(shown, hint, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
        cv2.imshow("Sentinel-X : enregistrement", shown)
    cap.release()
    cv2.destroyAllWindows()
    print(f"{taken} photo(s) enregistrée(s) dans {folder}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--capture", metavar="NOM", help="prendre des photos de cette personne avant de recalculer")
    args = parser.parse_args()

    detector = FaceDetector()
    if args.capture:
        capture(args.capture, detector)
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    gallery = build_gallery(detector, FaceRecognizer())
    save_gallery(gallery)
    print(f"{len(gallery)} personne(s) enregistrée(s) dans {GALLERY}")


if __name__ == "__main__":
    main()
