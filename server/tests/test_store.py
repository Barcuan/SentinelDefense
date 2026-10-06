from sentinel.store import KEEP_READINGS_S, Store, valid_snapshot


def test_passages_come_back_newest_first(tmp_path):
    store = Store(tmp_path / "s.db")
    store.add_passage(100.0, "Sacha", 0.8, None)
    store.add_passage(200.0, None, 0.1, "200000.jpg")

    rows = store.passages()

    assert [r["name"] for r in rows] == [None, "Sacha"]
    assert rows[0]["snapshot"] == "200000.jpg"
    assert rows[0]["fired"] is False


def test_a_shot_is_recorded_on_its_passage(tmp_path):
    store = Store(tmp_path / "s.db")
    pid = store.add_passage(100.0, None, 0.1, None)

    store.mark_fired(pid)

    assert store.passages()[0]["fired"] is True


def test_history_survives_a_restart(tmp_path):
    Store(tmp_path / "s.db").add_passage(100.0, "Sacha", 0.8, None)

    assert Store(tmp_path / "s.db").passages()[0]["name"] == "Sacha"


def test_readings_come_back_in_order_and_old_ones_are_pruned(tmp_path):
    store = Store(tmp_path / "s.db")
    store.add_reading(10.0, {"temp": 21.0, "hum": 40.0, "gas": 300.0})
    store.add_reading(20.0, {"gas": 310.0})
    store.add_reading(10.0 + KEEP_READINGS_S + 5, {"gas": 320.0})

    store.prune(now=10.0 + KEEP_READINGS_S + 5)
    rows = store.readings(since=0)

    assert [r["gas"] for r in rows] == [310.0, 320.0]
    assert rows[0]["temp"] is None


def test_snapshot_names_cannot_escape_the_folder():
    assert valid_snapshot("1791300000123.jpg")
    for name in ["../sentinel.db", "a.jpg", "123.png", "123.jpg/..", ""]:
        assert not valid_snapshot(name), name
