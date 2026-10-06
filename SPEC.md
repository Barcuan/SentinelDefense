# Spec : Sentinel-X — Porte gardée

Statut : validé par l'équipe (3 personnes), mis à jour le 2026-10-06 (un seul ESP, plus d'écran LCD). Code à geler jeudi 2026-10-08 au matin.
Voir aussi [CONSTRAINTS.md](CONSTRAINTS.md).

Le prof a autorisé à sortir du socle du sujet (capteurs DHT22/MQ-2/PIR non fournis) : on fait la porte gardée, sans capteurs environnementaux ni IA prédictive.

## Objectif

Une porte « gardée » pour la démo. La webcam C270 identifie la personne devant la porte :

- **connue** → LED verte, « Bienvenue <nom> » sur le dashboard ;
- **inconnue** → LED rouge + alarme sonore (haut-parleurs du PC) + « ACCES REFUSE » + capture d'écran ;
- **inconnue ET entre dans la salle** (HC-SR04 < 50 cm) **ET système armé** → le servo SG90 déclenche l'arbalète imprimée en 3D (projectile mousse/papier).

Le dashboard remonte tout : ce que voit la caméra, la personne devant la porte (nom ou inconnu, capture), le message affiché, l'historique des passages, la distance mesurée, l'état de l'ESP, et le bouton armer/désarmer.

Plus tard, si le temps le permet : le moteur 28BYJ-48 (via ULN2003) fait balayer la caméra de gauche à droite.

## Carte des capacités

| Module | Rôle | Tourne sur | Dépend de |
|---|---|---|---|
| `link` | Broker MQTT TLS, certificats, contrat des messages | PC serveur | — |
| `face-id` | C270 → détection + reconnaissance → `connu(nom)` / `inconnu` + capture | PC serveur | — |
| `door-node` | L'unique ESP8266 : LED verte/rouge, HC-SR04, servo (stepper plus tard) | ESP8266 | `link` |
| `guard` | Machine d'états : visage + distance + armé → commandes ; stockage des événements | PC serveur | `face-id`, `link` |
| `dashboard` | Page web : caméra en direct, personne, message, historique, distance, état ESP, armer/désarmer | PC serveur | `guard` |

Ordre de construction : `link` ∥ `face-id` → `door-node` ∥ `guard` → `dashboard`.

Le PC serveur est le PC d'un coéquipier : c'est lui qui a des ports USB-A pour la C270 et l'ESP. Le code y arrive par le dépôt GitHub de l'équipe.

## Contrat MQTT (module `link`)

Broker Mosquitto sur le PC serveur, **TLS port 8883**, CA auto-signée + utilisateur/mot de passe. JSON UTF-8.

| Topic | Sens | Payload |
|---|---|---|
| `sentinel/door/led` | PC → ESP | `{"state": "idle"\|"green"\|"red"}` |
| `sentinel/door/distance` | ESP → PC | `{"cm": 42.0}` toutes les 200 ms |
| `sentinel/door/fire` | PC → ESP | `{"id": 17}` (un message = un tir ; `id` évite de tirer deux fois sur un renvoi) |
| `sentinel/door/status` | ESP → PC | `{"online": true}` (retained + LWT `{"online": false}`) |

Changer ce contrat = **demander à l'équipe**.

## Logique `guard`

| État | Entrée | LED / alarme / dashboard |
|---|---|---|
| `idle` | aucun visage depuis 3 s | LED éteintes |
| `green` | visage connu (score SFace ≥ 0.363) | vert, « Bienvenue <nom> » (gardé 3 s après la disparition du visage) |
| `red` | visage inconnu | rouge + alarme PC, « ACCES REFUSE », capture enregistrée |

Règles de tir (toutes nécessaires) :

1. état = `red` ;
2. distance < `ENTRY_CM` (50 cm, réglable) ;
3. système **armé** (désarmé au démarrage, armé depuis le dashboard) ;
4. un seul tir par intrusion, puis 10 s avant de pouvoir retirer.

Le firmware revérifie localement la distance avant d'actionner le servo et ne tire jamais s'il a perdu le lien depuis plus de 2 s.

## Stack

- **PC serveur** : Python (venv), `opencv-python` (YuNet détection + SFace reconnaissance, modèles ONNX), `paho-mqtt`, `fastapi` + `uvicorn`, `numpy`, SQLite (stdlib), son d'alarme via `winsound` (stdlib).
- **Dashboard** : une page HTML + JS servie par FastAPI ; flux caméra en MJPEG ; données rafraîchies par polling. Pas de framework front.
- **Firmware** : un croquis Arduino (`.ino`) compilé avec **Arduino IDE**, déjà installé et testé sur le PC serveur. Cœur ESP8266, `PubSubClient`, `WiFiClientSecure` (BearSSL), `Servo`.
- **Broker** : Mosquitto (Windows).
- **Réseau** : partage de connexion du PC serveur (le Wi-Fi de l'école isole souvent les appareils).

## Commandes

```
python -m venv .venv && .venv\Scripts\activate
pip install -r server/requirements.txt
python server/scripts/get_models.py                  # modèles ONNX YuNet + SFace
python server/scripts/gen_certs.py                   # CA + certs dans link/certs/
mosquitto -c link/mosquitto.conf -v
python -m sentinel.enroll data/faces                 # data/faces/<nom>/*.jpg → data/faces.npz
uvicorn sentinel.app:app --app-dir server --port 8000
pytest
ruff check . && mypy server/sentinel
gitleaks detect --redact --no-banner
```

Firmware : ouvrir `firmware/door-node/door-node.ino` dans Arduino IDE, carte « NodeMCU 1.0 (ESP-12E Module) », Téléverser.

## Structure

```
firmware/door-node/      door-node.ino, secrets.h.example (secrets.h ignoré par git)
link/                    mosquitto.conf, certs/ (ignoré par git)
server/sentinel/         face_id.py, guard.py, mqtt.py, store.py, app.py, enroll.py
server/sentinel/static/  index.html (dashboard)
server/scripts/          get_models.py, gen_certs.py
server/tests/            tests pytest
server/models/           modèles ONNX (téléchargés, ignorés par git)
data/                    faces/, snapshots/, sentinel.db (ignoré par git — photos de personnes)
```

## Style

Python : fonctions simples, types annotés, logique pure séparée du matériel (testable sans caméra ni MQTT).

```python
def decide(state: State, face: Face | None, distance_cm: float | None, armed: bool, now: float) -> tuple[State, Command]:
    """Pure : pas d'I/O, testé dans tests/test_guard.py. Renvoie le nouvel état et la commande."""
    if face is None:
        return Command("idle") if now - state.last_face_at > 3 else state.command
    if face.authorized:
        return Command("green", text=f"Bienvenue {face.name}")
    fire = armed and distance_cm < ENTRY_CM and now - state.last_fire_at > FIRE_COOLDOWN_S
    return Command("red", fire=fire, text="ACCES REFUSE")
```

Firmware : un seul `.ino`, broches en `const int` en tête de fichier, secrets dans `secrets.h` (non commité, copie de `secrets.h.example`).

## Tests

- **pytest** sur `guard.decide` : toutes les règles de tir (pas armé, trop loin, connu, délai, perte de visage). Obligatoire, c'est la logique de sécurité.
- `face-id` : vérification manuelle (chaque membre reconnu, un inconnu rejeté).
- Firmware : checklist manuelle sur breadboard (chaque actionneur répond à son message MQTT).
- Pas d'objectif de couverture (voir CONSTRAINTS.md).

## Câblage (un seul ESP)

Alimentation : 5V sur la broche **VU** (sur ces cartes LoLin V3, VIN ne sort pas le 5V de l'USB), masse sur **G**. Ligne + = côté trait rouge, ligne − = côté trait bleu.

| Broche | Composant | État |
|---|---|---|
| D0 | LED rouge (330 Ω vers la masse) | câblé et testé le 2026-10-06 |
| D8 | LED verte (330 Ω vers la masse) | câblé et testé le 2026-10-06 |
| D3 | HC-SR04 TRIG | à faire |
| D1 | HC-SR04 ECHO, via pont diviseur (10K en haut, 2 × 10K en série en bas ≈ 3,3V) | à faire |
| D2 | Servo SG90 (signal) ; + sur la ligne +, − sur la ligne − | à faire |
| D5, D6, D7, RX | ULN2003 IN1–IN4 pour le stepper | plus tard |
| D4 | libre | — |

Le servo n'est **jamais** sur D4 : cette broche envoie des impulsions au démarrage, qui pourraient déclencher l'arbalète.

Courant : un port USB donne 500–900 mA. Le firmware coupe le stepper pendant un tir et à l'arrêt ; si l'ESP redémarre quand un moteur bouge → condensateur 470 µF entre + et −, ou chargeur USB séparé pour les moteurs (masse commune).

## Limites

- **Toujours** : démarrer désarmé ; secrets dans `.env` / `secrets.h` ; tester `guard.decide` avant chaque commit ; n'enrôler que des personnes d'accord ; un schéma clair pour chaque branchement.
- **Demander d'abord** : nouvelle dépendance ; changement du contrat MQTT ; changement du brochage.
- **Jamais** : de laser ; viser la tête ; tirer hors des 4 règles ci-dessus ; servo sur D4 ; commiter photos, captures, certificats ou base SQLite.

## Critères de réussite

1. Un membre enrôlé devant la C270 → LED verte + « Bienvenue <nom> » sur le dashboard en < 2 s.
2. Un inconnu → LED rouge + alarme en < 2 s, capture visible sur le dashboard.
3. Inconnu + < 50 cm + armé → un seul tir ; désarmé ou connu → aucun tir.
4. Lien coupé → l'ESP éteint ses LED et ne tire pas.
5. `mosquitto_sub` sans certificat ne peut pas se connecter (lien chiffré prouvé).
6. Le dashboard affiche la caméra en direct, la distance, l'état de l'ESP et l'historique des passages, qui survit à un redémarrage.
7. `pytest`, `ruff`, `gitleaks` passent.

## Questions ouvertes

1. **Dépôt GitHub** : à créer par l'équipe ; bloque l'installation du code sur le PC serveur.
2. **Carte ULN2003** : à trouver ; sans elle, la caméra reste fixe.

Tranché le 2026-10-06 : pas de capteurs DHT22/MQ-2/PIR ni d'IA prédictive (accord du prof) ; **un seul ESP8266** (le 2ᵉ reste en secours) ; pas d'écran sur la porte, les messages s'affichent sur le dashboard ; pas de buzzer, alarme sur le PC ; firmware via Arduino IDE ; stepper plus tard ; pièces 3D gérées par l'équipe ; seuil 50 cm ; Python 3.14 + OpenCV 5.0 fonctionnent.
