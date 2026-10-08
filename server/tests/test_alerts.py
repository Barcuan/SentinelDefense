from sentinel.alerts import GAS_RISE, MIN_SAMPLES, TEMP_MAX, AlertMonitor


def warm_up(monitor, gas=200.0, temp=22.0, start=0.0):
    t = start
    for _ in range(MIN_SAMPLES):
        monitor.push({"gas": gas, "temp": temp}, t)
        t += 2
    return t


def test_no_gas_alert_before_the_room_baseline_is_known():
    monitor = AlertMonitor()

    assert monitor.push({"gas": 900.0}, 0) == []


def test_gas_well_above_the_room_baseline_raises_one_alert():
    monitor = AlertMonitor()
    t = warm_up(monitor)

    first = monitor.push({"gas": 200 + GAS_RISE + 10}, t)
    again = monitor.push({"gas": 200 + GAS_RISE + 30}, t + 2)

    assert [a.kind for a in first] == ["gas"]
    assert again == []
    assert "gas" in monitor.active


def test_gas_alert_clears_when_back_to_normal_and_can_fire_again():
    monitor = AlertMonitor()
    t = warm_up(monitor)
    monitor.push({"gas": 200 + GAS_RISE + 10}, t)

    monitor.push({"gas": 205.0}, t + 2)
    assert "gas" not in monitor.active
    assert [a.kind for a in monitor.push({"gas": 200 + GAS_RISE + 10}, t + 4)] == ["gas"]


def test_small_gas_wobble_is_not_an_alert():
    monitor = AlertMonitor()
    t = warm_up(monitor)

    assert monitor.push({"gas": 200 + GAS_RISE / 2}, t) == []


def test_overheat_is_an_absolute_threshold():
    monitor = AlertMonitor()

    alerts = monitor.push({"temp": TEMP_MAX + 1}, 0)

    assert [a.kind for a in alerts] == ["temp"]
    assert alerts[0].message.startswith("Surchauffe")


def test_external_alert_is_kept_with_its_text():
    monitor = AlertMonitor()

    alert = monitor.external("porte", "Porte forcée", 1.0, now=10)

    assert alert.kind == "porte" and alert.message == "Porte forcée" and alert.source == "api"


def test_a_long_leak_does_not_become_the_new_normal():
    monitor = AlertMonitor()
    t = warm_up(monitor)
    for i in range(200):  # ~7 min de fuite
        monitor.push({"gas": 200 + GAS_RISE + 50}, t + i * 2)

    assert "gas" in monitor.active
