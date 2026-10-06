# Spec : Sentinel-X — Porte gardée

Statut : validé par l'équipe (3 personnes), mis à jour le 2026-10-06. Code à geler jeudi 2026-10-08 au matin.
Voir aussi [CONSTRAINTS.md](CONSTRAINTS.md).

Le prof a autorisé à sortir du socle du sujet (capteurs DHT22/MQ-2/PIR non fournis) : on fait la porte gardée, sans capteurs environnementaux ni IA prédictive.

## Objectif

Une porte « gardée » pour la démo. Une webcam identifie la personne devant la porte :

- **autorisée** → LED verte, « Bienvenue <nom> » sur le LCD ;
- **inconnue** → LED rouge + alarme sonore (haut-parleurs du PC) + « ACCES REFUSE » + capture d'écran ;
- **inconnue ET entre dans la salle** (HC-SR04 < 50 cm) **ET système armé** → l'arbalète imprimée en 3D tire (servo SG90) un projectile en mousse/papier.

La caméra balaie la porte de gauche à droite (stepper). Le dashboard enregistre chaque personne scannée (capture, nom ou inconnu, heure) pour le suivi, et permet d'armer/désarmer.

## Carte des capacités

| Module | Rôle | Tourne sur | Dépend de |
|---|---|---|---|
| `link` | Broker MQTT TLS, certificats, contrat des messages | PC | — |
| `face-id` | C270 → détection + reconnaissance → `autorisé(nom)` / `inconnu` + capture | PC | — |
| `panel` | ESP8266 n°1 : LCD 1602 + LED verte/rouge | ESP8266 | `link` |
| `turret` | ESP8266 n°2 : HC-SR04, servo de l'arbalète, stepper qui balaie la caméra | ESP8266 | `link` |
| `guard` | Machine d'états : visage + distance + armé → commandes ; stockage des événements | PC | `face-id`, `link` |
| `dashboard` | Page web : personne devant la porte, historique des passages, armer/désarmer | PC | `guard` |

Ordre de construction : `link` ∥ `face-id` → `panel` ∥ `turret` ∥ `guard` → `dashboard`.

Répartition suggérée : vision (`face-id`) / firmware (`panel`, `turret`) / serveur (`link`, `guard`, `dashboard`).

## Contrat MQTT (module `link`)

Broker Mosquitto sur le PC, **TLS port 8883**, CA auto-signée + utilisateur/mot de passe par nœud. JSON UTF-8.

| Topic | Sens | Payload |
|---|---|---|
| `sentinel/door/cmd` | PC → panel | `{"state": "idle"\|"green"\|"red", "text": "ACCES REFUSE"}` |
| `sentinel/turret/distance` | turret → PC | `{"cm": 42.0}` toutes les 200 ms |
| `sentinel/turret/fire` | PC → turret | `{"id": 17}` (un message = un tir ; `id` évite de tirer deux fois sur un renvoi) |
| `sentinel/<node>/status` | nœud → PC | `{"online": true}` (retained + LWT `{"online": false}`) |

Changer ce contrat = **demander à l'équipe** (trois personnes codent contre lui).

## Logique `guard`

| État | Entrée | LED / alarme / LCD |
|---|---|---|
| `idle` | aucun visage depuis 3 s | éteint |
| `green` | visage autorisé (score SFace ≥ 0.363) | vert, « Bienvenue <nom> », 5 s |
| `red` | visage inconnu | rouge + alarme PC, « ACCES REFUSE », capture enregistrée |

Règles de tir (toutes nécessaires) :

1. état = `red` ;
2. distance < `ENTRY_CM` (50 cm, réglable) ;
3. système **armé** (désarmé au démarrage, armé depuis le dashboard) ;
4. un seul tir par intrusion, puis 10 s avant de pouvoir retirer.

Le firmware `turret` revérifie localement la distance avant d'actionner le servo et ne tire jamais s'il a perdu le lien depuis plus de 2 s.

## Stack

- **PC** : Python (venv), `opencv-python` (YuNet détection + SFace reconnaissance, modèles ONNX), `paho-mqtt`, `fastapi` + `uvicorn`, `numpy`, SQLite (stdlib), son d'alarme via `winsound` (stdlib).
- **Dashboard** : une page HTML + JS servie par FastAPI, rafraîchie par polling. Pas de framework front.
- **Firmware** : C++ Arduino via PlatformIO, `PubSubClient`, `WiFiClientSecure` (BearSSL), `LiquidCrystal`, `Servo`, `AccelStepper`.
- **Broker** : Mosquitto (Windows).
- **Réseau** : partage de connexion du PC portable (le Wi-Fi de l'école isole souvent les appareils).

## Commandes

```
python -m venv .venv && .venv\Scripts\activate
pip install -r server/requirements.txt
python server/scripts/gen_certs.py                  # CA + certs broker/nœuds dans link/certs/
mosquitto -c link/mosquitto.conf -v
python -m sentinel.enroll data/faces                 # data/faces/<nom>/*.jpg → data/faces.npz
uvicorn sentinel.app:app --app-dir server --port 8000
pio run -d firmware/panel -t upload
pio run -d firmware/turret -t upload
pytest server/tests
ruff check . && mypy server/sentinel
gitleaks detect --redact --no-banner
```

## Structure

```
firmware/panel/          PlatformIO : src/main.cpp, include/secrets.h.example
firmware/turret/         idem
link/                    mosquitto.conf, certs/ (ignoré par git)
server/sentinel/         face_id.py, guard.py, mqtt.py, store.py, app.py, enroll.py
server/sentinel/static/  index.html (dashboard)
server/tests/            tests pytest
server/models/           modèles ONNX YuNet/SFace (téléchargés, ignorés par git)
data/                    faces/, snapshots/, sentinel.db (ignoré par git — photos de personnes)
```

## Style

Python : fonctions simples, types annotés, logique pure séparée du matériel (testable sans caméra ni MQTT).

```python
def decide(state: State, face: Face | None, distance_cm: float, armed: bool, now: float) -> Command:
    """Pure: pas d'I/O, testé dans tests/test_guard.py."""
    if face is None:
        return Command("idle") if now - state.last_face_at > 3 else state.command
    if face.authorized:
        return Command("green", text=f"Bienvenue {face.name}")
    fire = armed and distance_cm < ENTRY_CM and now - state.last_fire_at > FIRE_COOLDOWN_S
    return Command("red", fire=fire, text="ACCES REFUSE")
```

Firmware : un `main.cpp` par nœud, broches en `constexpr` en tête de fichier, secrets dans `include/secrets.h` (non commité, copie de `secrets.h.example`).

## Tests

- **pytest** sur `guard.decide` : toutes les règles de tir (pas armé, trop loin, autorisé, délai, perte de visage). Obligatoire, c'est la logique de sécurité.
- `face-id` : vérification manuelle (chaque membre reconnu, un inconnu rejeté).
- Firmware : checklist manuelle sur breadboard (chaque actionneur répond à son message MQTT).
- Pas d'objectif de couverture (voir CONSTRAINTS.md).

## Câblage (à confirmer sur breadboard)

**panel (ESP n°1)** — 8 broches :
- LCD 1602 en mode 4 bits : RS, E, D4, D5, D6, D7 → 6 broches ; RW → GND ; VDD → 5V (broche VU : sur ces cartes LoLin V3, VIN ne sort pas le 5V de l'USB) ; VSS → GND.
- Contraste VO : vers GND à travers ~1 kΩ (3 × 330 Ω en série), à ajuster si l'écran est vide ou tout noir.
- Rétroéclairage : A → 5V via 330 Ω, K → GND.
- LED verte et rouge : une résistance **330 Ω** en série chacune.

**turret (ESP n°2)** — 7 broches :
- HC-SR04 : TRIG direct ; ECHO sort en 5V → pont diviseur (10K en haut, 2 × 10K en série en bas ≈ 3,3V) avant l'ESP.
- Servo SG90 : signal + 5V (broche VU : sur ces cartes LoLin V3, VIN ne sort pas le 5V de l'USB) + GND.
- Stepper 28BYJ-48 via carte **ULN2003** (IN1–IN4) : 5V (broche VU : sur ces cartes LoLin V3, VIN ne sort pas le 5V de l'USB). Si l'ESP redémarre quand un moteur bouge → condensateur 470 µF ou alim 5V séparée, masse commune.

## Limites

- **Toujours** : démarrer désarmé ; secrets dans `.env` / `secrets.h` ; tester `guard.decide` avant chaque commit ; n'enrôler que des personnes d'accord.
- **Demander d'abord** : nouvelle dépendance ; changement du contrat MQTT ; changement du brochage.
- **Jamais** : de laser ; viser la tête ; tirer hors des 4 règles ci-dessus ; commiter photos, captures, certificats ou base SQLite.

## Critères de réussite

1. Un membre enrôlé devant la C270 → LED verte + son nom sur le LCD en < 2 s.
2. Un inconnu → LED rouge + alarme en < 2 s, capture visible sur le dashboard.
3. Inconnu + < 50 cm + armé → un seul tir ; désarmé ou autorisé → aucun tir.
4. Lien coupé → le panel passe en `idle`, la turret ne tire pas.
5. `mosquitto_sub` sans certificat ne peut pas se connecter (lien chiffré prouvé).
6. Le dashboard liste chaque passage (capture, nom/inconnu, heure) et l'historique survit à un redémarrage.
7. `pytest`, `ruff`, `gitleaks` passent.

## Questions ouvertes

1. **Carte ULN2003** : à trouver par l'équipe ; sans elle, la caméra reste fixe (T14 abandonnée).
2. **Python 3.14** : si `opencv-python` n'a pas encore de wheel, venv en Python 3.12.

Tranché le 2026-10-06 : pas de capteurs DHT22/MQ-2/PIR ni d'IA prédictive (accord du prof) ; deux ESP8266 ; LCD sans module I2C sur son propre ESP ; pas de buzzer, alarme sur le PC ; stepper = balayage gauche ↔ droite ; pièces 3D gérées par l'équipe ; seuil 50 cm.
