"""Télécharge les modèles ONNX YuNet (détection) et SFace (reconnaissance) depuis opencv_zoo."""

import urllib.request
from pathlib import Path

ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models"
MODELS = {
    "face_detection_yunet_2023mar.onnx": f"{ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": f"{ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}
DEST = Path(__file__).resolve().parents[1] / "models"

DEST.mkdir(exist_ok=True)
for name, url in MODELS.items():
    path = DEST / name
    if path.exists():
        print(f"ok      {name}")
        continue
    urllib.request.urlretrieve(url, path)
    print(f"fetched {name} ({path.stat().st_size // 1024} Ko)")
