import numpy as np
from sentinel.face_id import MAX_SIZE, FaceDetector


def test_blank_frame_has_no_face():
    detector = FaceDetector()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    assert len(detector.detect(frame)) == 0


def test_large_frame_is_downscaled_before_detection():
    detector = FaceDetector()
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    small = detector.prepare(frame)

    assert small.shape[1] <= MAX_SIZE[0] and small.shape[0] <= MAX_SIZE[1]
