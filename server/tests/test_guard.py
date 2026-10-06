from sentinel.guard import (
    FIRE_COOLDOWN_S,
    IDLE_AFTER_S,
    RED_BEFORE_FIRE_S,
    Face,
    State,
    decide,
)

SACHA = Face(name="Sacha", score=0.8)
INTRUS = Face(name=None, score=0.1)


def test_known_face_turns_green_with_welcome_text():
    _, cmd = decide(State(), SACHA, armed=False, now=0)

    assert cmd.state == "green"
    assert cmd.text == "Bienvenue Sacha"


def test_known_face_never_fires_even_armed_for_a_long_time():
    state = State()
    for t in range(30):
        state, cmd = decide(state, SACHA, armed=True, now=t)
        assert not cmd.fire


def test_unknown_face_turns_red_with_refused_text():
    _, cmd = decide(State(), INTRUS, armed=False, now=0)

    assert cmd.state == "red"
    assert cmd.text == "ACCES REFUSE"


def test_unknown_armed_fires_only_after_staying_unknown_long_enough():
    state, at_start = decide(State(), INTRUS, armed=True, now=0)
    state, just_before = decide(state, INTRUS, armed=True, now=RED_BEFORE_FIRE_S - 0.5)
    _, on_time = decide(state, INTRUS, armed=True, now=RED_BEFORE_FIRE_S)

    assert not at_start.fire
    assert not just_before.fire
    assert on_time.fire


def test_unknown_but_disarmed_never_fires():
    state = State()
    for t in range(30):
        state, cmd = decide(state, INTRUS, armed=False, now=t)
        assert not cmd.fire


def test_fires_once_then_waits_for_cooldown():
    state, _ = decide(State(), INTRUS, armed=True, now=0)
    state, first = decide(state, INTRUS, armed=True, now=RED_BEFORE_FIRE_S)
    state, again = decide(state, INTRUS, armed=True, now=RED_BEFORE_FIRE_S + 1)
    _, after = decide(state, INTRUS, armed=True, now=RED_BEFORE_FIRE_S + FIRE_COOLDOWN_S)

    assert first.fire
    assert not again.fire
    assert after.fire


def test_known_face_in_between_restarts_the_countdown():
    state, _ = decide(State(), INTRUS, armed=True, now=0)
    state, _ = decide(state, SACHA, armed=True, now=1)
    state, _ = decide(state, INTRUS, armed=True, now=2)
    state, too_soon = decide(state, INTRUS, armed=True, now=2 + RED_BEFORE_FIRE_S - 0.5)
    _, on_time = decide(state, INTRUS, armed=True, now=2 + RED_BEFORE_FIRE_S)

    assert not too_soon.fire
    assert on_time.fire


def test_face_lost_briefly_keeps_red_without_firing():
    state, _ = decide(State(), INTRUS, armed=True, now=0)
    state, _ = decide(state, INTRUS, armed=True, now=2)
    _, cmd = decide(state, None, armed=True, now=RED_BEFORE_FIRE_S + 0.5)  # 1,5 s sans visage

    assert cmd.state == "red"
    assert not cmd.fire


def test_no_face_for_a_while_goes_idle_and_restarts_the_countdown():
    state, _ = decide(State(), INTRUS, armed=True, now=0)
    state, idle = decide(state, None, armed=True, now=IDLE_AFTER_S + 0.5)
    state, back = decide(state, INTRUS, armed=True, now=IDLE_AFTER_S + 1)

    assert idle.state == "idle"
    assert idle.text == ""
    assert not back.fire


def test_starts_idle():
    _, cmd = decide(State(), None, armed=False, now=0)

    assert cmd.state == "idle"
