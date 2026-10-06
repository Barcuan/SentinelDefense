"""Générer la liaison chiffrée PC ↔ ESP et les réglages de l'ESP, une fois pour toutes.

    python -m sentinel.setup            demande le Wi-Fi, génère ce qui manque
    python -m sentinel.setup --force    régénère tout (il faudra re-téléverser l'ESP)

Crée (rien de tout ça ne va dans git) :
    link/certs/   CA + certificat du broker (courbe elliptique P-256, léger pour l'ESP8266)
    link/         mosquitto.conf, passwd (mots de passe hachés), acl (qui a le droit de quoi)
    .env          compte MQTT du serveur
    firmware/door-node/secrets.h   Wi-Fi, broker, compte MQTT de l'ESP, CA, heure de génération
"""

import argparse
import base64
import datetime as dt
import getpass
import hashlib
import ipaddress
import os
import secrets
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[2]
BROKER_IP = "192.168.137.1"  # adresse fixe du PC quand il partage sa connexion (point d'accès mobile Windows)
MQTT_PORT = 8883
SERVER_USER, ESP_USER = "server", "esp"

ACL = """user server
topic readwrite sentinel/#

user esp
topic read sentinel/door/led
topic read sentinel/door/fire
topic write sentinel/door/climate
topic write sentinel/door/status
"""


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Sentinel-X"),
                      x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def make_ca(now: dt.datetime) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name("Sentinel-X CA"))
        .issuer_name(_name("Sentinel-X CA"))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False,
                                     key_encipherment=False, data_encipherment=False, key_agreement=False,
                                     encipher_only=False, decipher_only=False), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def make_server_cert(
    ca_key: ec.EllipticCurvePrivateKey, ca_cert: x509.Certificate, now: dt.datetime
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    san = x509.SubjectAlternativeName([
        x509.IPAddress(ipaddress.ip_address(BROKER_IP)),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.DNSName("localhost"),
        x509.DNSName(BROKER_IP),  # certaines piles TLS embarquées comparent l'adresse comme un nom
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(BROKER_IP))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=825))
        .add_extension(san, critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    return key, cert


def mosquitto_hash(password: str) -> str:
    """Format de mot de passe de Mosquitto 2 : $7$ = PBKDF2-SHA512, 101 itérations, sel de 12 octets."""
    salt = os.urandom(12)
    digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 101)
    return f"$7$101${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def c_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_secrets_h(ssid: str, wifi_password: str, mqtt_user: str, mqtt_password: str,
                     ca_pem: str, now: dt.datetime) -> str:
    return f"""// Généré par « python -m sentinel.setup » le {now:%Y-%m-%d %H:%M}. Ne pas commiter, ne pas partager.
#pragma once

const char* WIFI_SSID = {c_string(ssid)};
const char* WIFI_PASSWORD = {c_string(wifi_password)};

const char* MQTT_HOST = "{BROKER_IP}";
const int MQTT_PORT = {MQTT_PORT};
const char* MQTT_USER = {c_string(mqtt_user)};
const char* MQTT_PASSWORD = {c_string(mqtt_password)};

// Heure de génération : l'ESP valide le certificat du broker avec cette date, sans Internet.
const time_t CERT_TIME = {int(now.timestamp())};

const char CA_CERT[] PROGMEM = R"EOF(
{ca_pem.strip()}
)EOF";
"""


def render_mosquitto_conf(link: Path) -> str:
    certs = (link / "certs").as_posix()
    return f"""# Généré par « python -m sentinel.setup ». Broker Sentinel-X : TLS obligatoire, pas d'anonyme.
allow_anonymous false
password_file {(link / "passwd").as_posix()}
acl_file {(link / "acl").as_posix()}
persistence false
log_dest stdout

listener {MQTT_PORT}
cafile {certs}/ca.crt
certfile {certs}/server.crt
keyfile {certs}/server.key
tls_version tlsv1.2
"""


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    pairs = (line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line)
    return {key.strip(): value.strip() for key, value in pairs}


def _pem(obj: x509.Certificate) -> bytes:
    return obj.public_bytes(serialization.Encoding.PEM)


def _key_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def generate(root: Path, ssid: str, wifi_password: str, now: dt.datetime | None = None, force: bool = False) -> bool:
    """Écrit tous les fichiers. Sans force, ne touche à rien si la liaison existe déjà. Renvoie True si écrit."""
    now = now or dt.datetime.now(dt.UTC)
    link = root / "link"
    certs = link / "certs"
    if (certs / "ca.crt").exists() and not force:
        return False
    certs.mkdir(parents=True, exist_ok=True)

    ca_key, ca_cert = make_ca(now)
    server_key, server_cert = make_server_cert(ca_key, ca_cert, now)
    (certs / "ca.crt").write_bytes(_pem(ca_cert))
    (certs / "server.crt").write_bytes(_pem(server_cert))
    (certs / "server.key").write_bytes(_key_pem(server_key))
    # La clé de la CA n'est pas gardée : personne ne pourra signer un faux broker avec.

    server_password, esp_password = secrets.token_urlsafe(18), secrets.token_urlsafe(18)
    (link / "passwd").write_text(
        f"{SERVER_USER}:{mosquitto_hash(server_password)}\n{ESP_USER}:{mosquitto_hash(esp_password)}\n", encoding="utf-8")
    (link / "acl").write_text(ACL, encoding="utf-8")
    (link / "mosquitto.conf").write_text(render_mosquitto_conf(link), encoding="utf-8")
    (root / ".env").write_text(f"MQTT_USER={SERVER_USER}\nMQTT_PASSWORD={server_password}\n", encoding="utf-8")

    firmware = root / "firmware" / "door-node"
    firmware.mkdir(parents=True, exist_ok=True)
    header = render_secrets_h(ssid, wifi_password, ESP_USER, esp_password, _pem(ca_cert).decode(), now)
    (firmware / "secrets.h").write_text(header, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="tout régénérer (il faudra re-téléverser l'ESP)")
    args = parser.parse_args()

    if (ROOT / "link" / "certs" / "ca.crt").exists() and not args.force:
        print("La liaison chiffrée existe déjà : rien à faire. (--force pour tout régénérer)")
        return
    print("Wi-Fi sur lequel l'ESP va se connecter (le partage de connexion de ce PC) :")
    ssid = input("  Nom du Wi-Fi : ").strip()
    wifi_password = getpass.getpass("  Mot de passe du Wi-Fi (caché) : ")
    generate(ROOT, ssid, wifi_password, force=args.force)
    print("Liaison chiffrée générée : link/, .env et firmware/door-node/secrets.h")
    print("Prochaine étape : téléverser firmware/door-node/door-node.ino sur l'ESP avec Arduino IDE.")


if __name__ == "__main__":
    main()
