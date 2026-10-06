import numpy as np
from sentinel.face_id import (
    MAX_SIZE,
    FaceDetector,
    FaceRecognizer,
    identify,
    load_gallery,
    save_gallery,
)


def unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_blank_frame_has_no_face():
    detector = FaceDetector()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    assert len(detector.detect(frame)) == 0


def test_large_frame_is_downscaled_before_detection():
    detector = FaceDetector()
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    small = detector.prepare(frame)

    assert small.shape[1] <= MAX_SIZE[0] and small.shape[0] <= MAX_SIZE[1]


def test_embedding_is_a_normalized_128_vector():
    frame = np.full((480, 640, 3), 128, dtype=np.uint8)
    face_row = np.array([200, 150, 160, 200, 250, 220, 330, 220, 290, 270, 255, 310, 325, 310, 0.9], dtype=np.float32)

    emb = FaceRecognizer().embed(frame, face_row)

    assert emb.shape == (128,)
    assert abs(np.linalg.norm(emb) - 1) < 1e-4


def test_empty_gallery_means_unknown():
    face = identify(unit([1, 0, 0]), {}, threshold=0.4)

    assert face.name is None


def test_close_embedding_is_recognized():
    gallery = {"Sacha": np.stack([unit([1, 0, 0]), unit([0.9, 0.1, 0])])}

    face = identify(unit([0.95, 0.05, 0]), gallery, threshold=0.4)

    assert face.name == "Sacha"
    assert face.score > 0.9


def test_far_embedding_stays_unknown_with_its_best_score():
    gallery = {"Sacha": np.stack([unit([1, 0, 0])])}

    face = identify(unit([0, 1, 0]), gallery, threshold=0.4)

    assert face.name is None
    assert face.score < 0.4


def test_best_match_wins_among_several_people():
    gallery = {"Sacha": np.stack([unit([1, 0, 0])]), "Kiki": np.stack([unit([0, 1, 0])])}

    face = identify(unit([0.2, 1, 0]), gallery, threshold=0.4)

    assert face.name == "Kiki"


def test_gallery_survives_save_and_load(tmp_path):
    path = tmp_path / "faces.npz"
    gallery = {"Sacha": np.stack([unit([1, 0, 0]), unit([0, 1, 0])])}

    save_gallery(gallery, path)
    loaded = load_gallery(path)

    assert list(loaded) == ["Sacha"]
    assert np.allclose(loaded["Sacha"], gallery["Sacha"])


def test_missing_gallery_file_is_empty(tmp_path):
    assert load_gallery(tmp_path / "absent.npz") == {}
