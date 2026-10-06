from pathlib import Path

from sentinel.door import Door, pick_face
from sentinel.guard import RED_BEFORE_FIRE_S, Face
from sentinel.mqtt import T_FIRE, T_LED, find_mosquitto, parse_climate

SACHA = Face(name="Sacha", score=0.8)
INTRUS = Face(name=None, score=0.1)


class FakeLink:
    def __init__(self):
        self.sent = []

    def publish(self, topic, payload, retain=False):
        self.sent.append((topic, payload, retain))


def make_door(clock_start=1_000_000.0):
    link = FakeLink()
    clock = iter(clock_start + i for i in range(1000))
    return Door(link, wall_clock=lambda: next(clock)), link


def test_climate_with_all_values_is_kept():
    assert parse_climate(b'{"temp":23.5,"hum":45,"gas":312}') == {"temp": 23.5, "hum": 45.0, "gas": 312.0}


def test_climate_without_dht_values_keeps_the_gas():
    assert parse_climate(b'{"gas":300}') == {"gas": 300.0}


def test_broken_or_absurd_climate_is_ignored():
    assert parse_climate(b"pas du json") is None
    assert parse_climate(b'{"temp":"chaud","gas":1}') is None
    assert parse_climate(b'{"temp":500,"gas":1}') is None
    assert parse_climate(b"[1,2]") is None


def test_any_unknown_face_wins_over_known_ones():
    assert pick_face([SACHA, INTRUS]) == INTRUS
    assert pick_face([SACHA]) == SACHA
    assert pick_face([]) is None


def test_led_is_published_retained_and_only_when_it_changes():
    door, link = make_door()
    door.step(None, now=0)
    door.step(SACHA, now=1)
    door.step(SACHA, now=2)
    door.step(SACHA, now=3)

    assert [(t, p, r) for t, p, r in link.sent if t == T_LED] == [(T_LED, "idle", True), (T_LED, "green", True)]


def test_armed_intruder_triggers_one_fire_message_with_a_fresh_id():
    door, link = make_door()
    door.armed = True
    door.step(INTRUS, now=0)
    door.step(INTRUS, now=RED_BEFORE_FIRE_S)
    door.step(INTRUS, now=RED_BEFORE_FIRE_S + 1)

    fires = [(p, r) for t, p, r in link.sent if t == T_FIRE]
    assert len(fires) == 1
    assert fires[0][1] is False  # jamais retenu : un tir ne doit pas être rejoué à la reconnexion
    assert int(fires[0][0]) > 0


def test_disarmed_door_never_fires_and_starts_disarmed():
    door, link = make_door()
    assert door.armed is False
    for t in range(20):
        door.step(INTRUS, now=t)

    assert not [m for m in link.sent if m[0] == T_FIRE]


def test_two_shots_get_different_ids():
    door, link = make_door()
    door.armed = True
    for t in range(30):
        door.step(INTRUS, now=t)

    ids = [p for t, p, _ in link.sent if t == T_FIRE]
    assert len(ids) >= 2 and len(set(ids)) == len(ids)


def test_door_reports_verdict_text_for_the_dashboard():
    door, _ = make_door()
    door.step(SACHA, now=0)
    assert door.command.text == "Bienvenue Sacha"


def passages(door, frames):
    started = []
    for now, face in frames:
        door.step(face, now)
        if door.passage_started:
            started.append(face.name if face else "?")
    return started


def test_one_passage_per_person_not_one_per_frame():
    door, _ = make_door()

    assert passages(door, [(0, SACHA), (0.1, SACHA), (0.2, SACHA)]) == ["Sacha"]


def test_a_different_person_starts_a_new_passage():
    door, _ = make_door()

    assert passages(door, [(0, SACHA), (1, INTRUS), (2, INTRUS)]) == ["Sacha", None]


def test_face_lost_briefly_is_the_same_passage_but_coming_back_later_is_new():
    door, _ = make_door()
    frames = [(0, SACHA), (1, None), (2, SACHA), (10, None), (11, SACHA)]

    assert passages(door, frames) == ["Sacha", "Sacha"]


def test_missing_mosquitto_is_reported_as_none(tmp_path):
    assert find_mosquitto([Path(tmp_path / "nulle-part" / "mosquitto.exe")]) is None
