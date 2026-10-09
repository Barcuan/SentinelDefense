from sentinel.monitor import parse_broker_line, runtime_conf, system_stats, tail


def test_refused_password_is_flagged_as_an_attack():
    line = "1791532630: Client auto-A00E [127.0.0.1:62638] disconnected: not authorised."

    event = parse_broker_line(line)

    assert event["at"] == 1791532630
    assert event["level"] == "refus"
    assert "mot de passe" in event["text"]
    assert event["ip"] == "127.0.0.1"


def test_plain_connection_without_tls_is_flagged():
    event = parse_broker_line("1791532631: Client 192.168.137.50 [192.168.137.50:62652] disconnected: protocol error.")

    assert event["level"] == "refus"
    assert event["ip"] == "192.168.137.50"


def test_accepted_client_is_info():
    line = "1791532640: New client connected from 192.168.137.12:50000 as sentinel-door-ab12 (p2, c1, k3, u'esp')."

    event = parse_broker_line(line)

    assert event["level"] == "ok"
    assert "esp" in event["text"]


def test_noise_lines_are_ignored():
    assert parse_broker_line("1791532628: Bridge support available.") is None
    assert parse_broker_line("pas un journal") is None


def test_tail_returns_the_last_lines(tmp_path):
    log = tmp_path / "m.log"
    log.write_text("\n".join(f"ligne {i}" for i in range(500)) + "\n", encoding="utf-8")

    assert tail(log, 3) == ["ligne 497", "ligne 498", "ligne 499"]
    assert tail(tmp_path / "absent.log", 3) == []


def test_runtime_conf_logs_to_a_file_instead_of_stdout(tmp_path):
    conf = "allow_anonymous false\nlog_dest stdout\nlistener 8883\n"

    out = runtime_conf(conf, tmp_path / "mosquitto.log")

    assert "log_dest stdout" not in out
    assert f"log_dest file {(tmp_path / 'mosquitto.log').as_posix()}" in out
    assert "log_type notice" in out and "listener 8883" in out


def test_system_stats_are_percentages():
    stats = system_stats()

    assert 0 <= stats["cpu"] <= 100
    assert 0 < stats["ram"] <= 100
    assert stats["process_mb"] > 0
