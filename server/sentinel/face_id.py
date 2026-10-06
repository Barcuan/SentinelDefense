"""Détection de visages sur la webcam (YuNet). La reconnaissance (SFace) arrive en T4."""

from pathlib import Path

import cv2
import numpy as np

MODELS = Path(__file__).resolve().parents[1] / "models"
YUNET = MODELS / "face_detection_yunet_2023mar.onnx"
MAX_SIZE = (640, 480)  # le sujet impose de réduire les images pour rester < 100 ms par image


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


def preview(camera: int = 0) -> None:
    """Affiche la webcam avec un cadre sur chaque visage. Échap pour quitter."""
    detector = FaceDetector()
    cap = cv2.VideoCapture(camera, cv2.CAP_DSHOW)
    while cv2.waitKey(1) != 27:
        ok, frame = cap.read()
        if not ok:
            break
        frame = detector.prepare(frame)
        tick = cv2.getTickCount()
        faces = detector.detect(frame)
        ms = (cv2.getTickCount() - tick) * 1000 / cv2.getTickFrequency()
        for x, y, w, h in faces[:, :4].astype(int):
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(frame, f"{len(faces)} visage(s) {ms:.0f} ms", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Sentinel-X", frame)
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    preview()
