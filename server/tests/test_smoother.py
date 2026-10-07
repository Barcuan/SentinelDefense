from sentinel.door import MIN_FRAMES, WINDOW_S, Smoother
from sentinel.guard import Face

SACHA = Face(name="Sacha", score=0.7)
INTRUS = Face(name=None, score=0.2)


def feed(smoother, faces, start=0.0, step=0.05):
    out = None
    for i, face in enumerate(faces):
        out = smoother.push(face, start + i * step)
    return out


def test_no_decision_before_enough_frames():
    s = Smoother()
    for i in range(MIN_FRAMES - 1):
        assert s.push(SACHA, i * 0.05) is None


def test_steady_member_is_recognized():
    assert feed(Smoother(), [SACHA] * 10).name == "Sacha"


def test_one_lookalike_frame_does_not_turn_a_stranger_green():
    out = feed(Smoother(), [INTRUS] * 6 + [SACHA] + [INTRUS] * 3)

    assert out is not None and out.name is None


def test_mixed_frames_keep_the_previous_verdict():
    s = Smoother()
    feed(s, [INTRUS] * 10)
    out = feed(s, [SACHA, INTRUS] * 5, start=1.0)

    assert out is not None and out.name is None


def test_old_frames_leave_the_window():
    s = Smoother()
    feed(s, [INTRUS] * 10)
    out = feed(s, [SACHA] * 10, start=1.0 + WINDOW_S)

    assert out is not None and out.name == "Sacha"


def test_no_face_is_passed_through():
    s = Smoother()
    feed(s, [SACHA] * 10)

    assert s.push(None, 1.0) is None
