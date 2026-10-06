"""Détection (YuNet) et reconnaissance (SFace) des visages sur la webcam."""

import os
from pathlib import Path

import cv2
import numpy as np

from sentinel.guard import Face

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "server" / "models"
YUNET = MODELS / "face_detection_yunet_2023mar.onnx"
SFACE = MODELS / "face_recognition_sface_2021dec.onnx"
GALLERY = ROOT / "data" / "faces.npz"
MAX_SIZE = (640, 480)  # le sujet impose de réduire les images pour rester < 100 ms par image
CAMERA = int(os.environ.get("SENTINEL_CAMERA", "0"))  # 1 si la C270 n'est pas la caméra par défaut
THRESHOLD = float(os.environ.get("SENTINEL_THRESHOLD", "0.363"))  # seuil cosinus SFace conseillé par OpenCV

Gallery = dict[str, np.ndarray]  # nom → empreintes normalisées, une ligne de 128 valeurs par photo


class FaceDetector:
    def __init__(self, score_threshold: float = 0.8) -> None:
        self._yunet = cv2.FaceDetectorYN.create(str(YUNET), "", MAX_SIZE, score_threshold)

    def prepare(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        scale = min(MAX_SIZE[0] / w, MAX_SIZE[1] / h, 1.0)
        return frame if scale == 1.0 else cv2.resize(frame, (int(w * scale), int(h * scale)))

    def detect(self, frame: np.ndarray) -> np.ndarray:
        """Renvoie une ligne par visage : x, y, w, h, 5 points de repère, score."""
        h, w = frame.shape[:2]
        self._yunet.setInputSize((w, h))
        _, faces = self._yunet.detect(frame)
        return faces if faces is not None else np.empty((0, 15), dtype=np.float32)


class FaceRecognizer:
    def __init__(self) -> None:
        self._sface = cv2.FaceRecognizerSF.create(str(SFACE), "")

    def embed(self, frame: np.ndarray, face_row: np.ndarray) -> np.ndarray:
        """Empreinte normalisée (128 valeurs) du visage décrit par une ligne de FaceDetector.detect."""
        aligned = self._sface.alignCrop(frame, face_row)
        feature = self._sface.feature(aligned).flatten()
        return feature / np.linalg.norm(feature)


def identify(embedding: np.ndarray, gallery: Gallery, threshold: float = THRESHOLD) -> Face:
    """Compare à toutes les photos enregistrées ; garde la plus ressemblante (similarité cosinus)."""
    best_name, best = None, -1.0
    for name, embeddings in gallery.items():
        score = float(np.max(embeddings @ embedding))
        if score > best:
            best_name, best = name, score
    return Face(best_name if best >= threshold else None, best)


def save_gallery(gallery: Gallery, path: Path = GALLERY) -> None:
    """Fichier .npz : arr_0 = les noms, puis une matrice d'empreintes par nom, dans le même ordre."""
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(gallery)
    np.savez(path, np.array(names), *(gallery[name] for name in names))


def load_gallery(path: Path = GALLERY) -> Gallery:
    if not path.exists():
        return {}
    with np.load(path) as data:
        return {str(name): data[f"arr_{i + 1}"] for i, name in enumerate(data["arr_0"])}


def label(face: Face) -> str:
    return f"{face.name} ({face.score:.2f})" if face.name else f"inconnu ({face.score:.2f})"


def preview(camera: int = CAMERA) -> None:
    """Affiche la webcam : cadre vert + nom si connu, rouge si inconnu. Échap pour quitter."""
    detector, recognizer, gallery = FaceDetector(), FaceRecognizer(), load_gallery()
    print(f"{len(gallery)} personne(s) enregistrée(s), seuil {THRESHOLD}")
    cap = cv2.VideoCapture(camera, cv2.CAP_DSHOW)
    while cv2.waitKey(1) != 27:
        ok, frame = cap.read()
        if not ok:
            break
        frame = detector.prepare(frame)
        tick = cv2.getTickCount()
        for row in detector.detect(frame):
            face = identify(recognizer.embed(frame, row), gallery)
            x, y, w, h = row[:4].astype(int)
            color = (0, 200, 0) if face.authorized else (0, 0, 230)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, label(face), (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        ms = (cv2.getTickCount() - tick) * 1000 / cv2.getTickFrequency()
        cv2.putText(frame, f"{ms:.0f} ms", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("Sentinel-X", frame)
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    preview()
