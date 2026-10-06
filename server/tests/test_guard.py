from sentinel.guard import ENTRY_CM, FIRE_COOLDOWN_S, IDLE_AFTER_S, Face, State, decide

SACHA = Face(name="Sacha", score=0.8)
INTRUS = Face(name=None, score=0.1)
PROCHE = ENTRY_CM - 10
LOIN = ENTRY_CM + 100


def test_known_face_turns_green_with_welcome_text():
    _, cmd = decide(State(), SACHA, LOIN, armed=False, now=0)

    assert cmd.state == "green"
    assert cmd.text == "Bienvenue Sacha"


def test_known_face_never_fires_even_armed_and_close():
    _, cmd = decide(State(), SACHA, PROCHE, armed=True, now=0)

    assert not cmd.fire


def test_unknown_face_turns_red_with_refused_text():
    _, cmd = decide(State(), INTRUS, LOIN, armed=False, now=0)

    assert cmd.state == "red"
    assert cmd.text == "ACCES REFUSE"


def test_unknown_close_but_disarmed_does_not_fire():
    _, cmd = decide(State(), INTRUS, PROCHE, armed=False, now=0)

    assert not cmd.fire


def test_unknown_armed_but_far_does_not_fire():
    _, cmd = decide(State(), INTRUS, LOIN, armed=True, now=0)

    assert not cmd.fire


def test_unknown_armed_with_no_distance_reading_does_not_fire():
    _, cmd = decide(State(), INTRUS, None, armed=True, now=0)

    assert not cmd.fire


def test_unknown_armed_and_close_fires_once_then_waits_for_cooldown():
    state, first = decide(State(), INTRUS, PROCHE, armed=True, now=0)
    state, again = decide(state, INTRUS, PROCHE, armed=True, now=1)
    _, after = decide(state, INTRUS, PROCHE, armed=True, now=FIRE_COOLDOWN_S + 0.5)

    assert first.fire
    assert not again.fire
    assert after.fire


def test_face_lost_briefly_keeps_last_state_without_firing():
    state, _ = decide(State(), INTRUS, PROCHE, armed=True, now=0)
    _, cmd = decide(state, None, PROCHE, armed=True, now=IDLE_AFTER_S - 1)

    assert cmd.state == "red"
    assert not cmd.fire


def test_no_face_for_a_while_goes_idle():
    state, _ = decide(State(), SACHA, LOIN, armed=False, now=0)
    _, cmd = decide(state, None, LOIN, armed=False, now=IDLE_AFTER_S + 0.5)

    assert cmd.state == "idle"
    assert cmd.text == ""


def test_starts_idle():
    _, cmd = decide(State(), None, None, armed=False, now=0)

    assert cmd.state == "idle"
