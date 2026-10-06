from sentinel.app import Enrollment, valid_name
from sentinel.enroll import SHOT_EVERY_S, SHOTS


def test_plain_and_accented_names_are_accepted():
    for name in ["Sacha", "Élodie", "Jean-Pierre", "Jean Pierre", "Kiki2"]:
        assert valid_name(name), name


def test_names_that_could_escape_the_faces_folder_are_refused():
    for name in ["", "..", ".", "../data", "a/b", "a\\b", " Sacha", "Sacha ", "_x", "x" * 31, "Sacha:1"]:
        assert not valid_name(name), name


def test_enrollment_shoots_only_with_exactly_one_face():
    enrollment = Enrollment("Sacha")

    assert not enrollment.wants_shot(faces_in_frame=0, now=0)
    assert not enrollment.wants_shot(faces_in_frame=2, now=0)
    assert enrollment.wants_shot(faces_in_frame=1, now=0)


def test_enrollment_waits_between_two_shots():
    enrollment = Enrollment("Sacha")
    enrollment.record_shot(now=0)

    assert not enrollment.wants_shot(faces_in_frame=1, now=SHOT_EVERY_S / 2)
    assert enrollment.wants_shot(faces_in_frame=1, now=SHOT_EVERY_S)


def test_enrollment_stops_after_enough_shots():
    enrollment = Enrollment("Sacha")
    for i in range(SHOTS):
        enrollment.record_shot(now=i * SHOT_EVERY_S)

    assert enrollment.done
    assert not enrollment.wants_shot(faces_in_frame=1, now=1000)
