import base64
import datetime as dt
import hashlib
import ipaddress

from cryptography import x509
from sentinel.setup import (
    BROKER_IP,
    c_string,
    generate,
    load_env,
    make_ca,
    make_server_cert,
    mosquitto_hash,
    render_secrets_h,
)

NOW = dt.datetime(2026, 10, 6, 20, 0, tzinfo=dt.UTC)


def test_server_certificate_is_signed_by_the_ca_and_valid_for_the_hotspot_ip():
    ca_key, ca_cert = make_ca(NOW)
    _, cert = make_server_cert(ca_key, ca_cert, NOW)

    cert.verify_directly_issued_by(ca_cert)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert ipaddress.ip_address(BROKER_IP) in san.get_values_for_type(x509.IPAddress)
    assert "localhost" in san.get_values_for_type(x509.DNSName)
    assert cert.not_valid_before_utc <= NOW <= cert.not_valid_after_utc


def test_mosquitto_hash_uses_the_pbkdf2_sha512_format_and_verifies():
    line = mosquitto_hash("s3cret")

    algo, iterations, salt, digest = line.split("$")[1:]
    assert (algo, iterations) == ("7", "101")
    expected = hashlib.pbkdf2_hmac("sha512", b"s3cret", base64.b64decode(salt), 101)
    assert base64.b64decode(digest) == expected


def test_c_string_escapes_quotes_and_backslashes():
    assert c_string('Wi"Fi\\x') == '"Wi\\"Fi\\\\x"'


def test_secrets_header_holds_everything_the_firmware_needs():
    header = render_secrets_h("Hotspot Kiki", 'p@ss"word', "esp", "mqtt-pass", "-----BEGIN CERTIFICATE-----\nAAA\n", NOW)

    assert 'WIFI_SSID = "Hotspot Kiki";' in header
    assert 'WIFI_PASSWORD = "p@ss\\"word";' in header
    assert f'MQTT_HOST = "{BROKER_IP}";' in header
    assert 'MQTT_USER = "esp";' in header
    assert 'MQTT_PASSWORD = "mqtt-pass";' in header
    assert f"CERT_TIME = {int(NOW.timestamp())};" in header
    assert "-----BEGIN CERTIFICATE-----\nAAA" in header


def test_generate_writes_every_file_and_keeps_them_unless_forced(tmp_path):
    generate(tmp_path, "Hotspot", "wifipass", now=NOW)
    files = [
        "link/certs/ca.crt", "link/certs/server.crt", "link/certs/server.key",
        "link/passwd", "link/acl", "link/mosquitto.conf", ".env", "firmware/door-node/secrets.h",
    ]
    for name in files:
        assert (tmp_path / name).is_file(), name
    ca_before = (tmp_path / "link/certs/ca.crt").read_bytes()

    generate(tmp_path, "Autre", "autre", now=NOW)
    assert (tmp_path / "link/certs/ca.crt").read_bytes() == ca_before

    generate(tmp_path, "Autre", "autre", now=NOW, force=True)
    assert (tmp_path / "link/certs/ca.crt").read_bytes() != ca_before


def test_broker_refuses_anonymous_clients_and_limits_the_esp_topics(tmp_path):
    generate(tmp_path, "Hotspot", "wifipass", now=NOW)
    conf = (tmp_path / "link/mosquitto.conf").read_text(encoding="utf-8")
    acl = (tmp_path / "link/acl").read_text(encoding="utf-8")

    assert "allow_anonymous false" in conf
    assert "listener 8883" in conf
    assert "\\" not in conf
    assert "user esp\ntopic read sentinel/door/led" in acl
    assert "topic readwrite" not in acl.split("user esp")[1]


def test_env_file_round_trips_the_server_password(tmp_path):
    generate(tmp_path, "Hotspot", "wifipass", now=NOW)
    env = load_env(tmp_path / ".env")

    assert env["MQTT_USER"] == "server"
    assert len(env["MQTT_PASSWORD"]) >= 20
