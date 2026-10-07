# Spec : Sentinel-X — Porte gardée

Statut : validé par l'équipe (3 personnes), mis à jour le 2026-10-06 (un seul ESP, plus d'écran LCD). Code à geler jeudi 2026-10-08 au matin.
Voir aussi [CONSTRAINTS.md](CONSTRAINTS.md).

Le prof a autorisé à sortir du socle du sujet (capteurs DHT22/MQ-2/PIR non fournis) : on fait la porte gardée, sans capteurs environnementaux ni IA prédictive.

## Objectif

Une porte « gardée » pour la démo. La webcam C270 identifie la personne devant la porte :

- **connue** → LED verte, « Bienvenue <nom> » sur le dashboard ;
- **inconnue** → LED rouge + « ACCES REFUSE » + capture d'écran ;
- **inconnue pendant 3 s** → le PC prononce « Personne inconnue. Si vous ne vous éloignez pas de la zone, nous ouvrirons le feu. » (voix Windows, pas de bip) ;
- **toujours inconnue à 11 s ET système armé** → le servo SG90 déclenche l'arbalète imprimée en 3D (projectile mousse/papier) ;
- **un visage connu présent dans l'image** → il l'emporte : vert, ni avertissement ni tir, même avec un inconnu à côté (choix de l'équipe du 2026-10-07).

Le dashboard remonte tout : ce que voit la caméra, la personne devant la porte (nom ou inconnu, capture), le message affiché, l'historique des passages, la température, l'humidité et le niveau de gaz (capteurs DHT11 et MQ sur l'ESP, avec courbes), l'état de l'ESP, et le bouton armer/désarmer.

Plus tard, si le temps le permet : le moteur 28BYJ-48 (via ULN2003) fait balayer la caméra de gauche à droite.

## Carte des capacités

| Module | Rôle | Tourne sur | Dépend de |
|---|---|---|---|
| `link` | Broker MQTT TLS, certificats, contrat des messages | PC serveur | — |
| `face-id` | C270 → détection + reconnaissance → `connu(nom)` / `inconnu` + capture | PC serveur | — |
| `door-node` | L'unique ESP8266 : LED verte/rouge, capteur DHT (température/humidité), capteur de gaz, servo (stepper plus tard) | ESP8266 | `link` |
| `guard` | Machine d'états : visage + armé → commandes ; stockage des événements | PC serveur | `face-id`, `link` |
| `dashboard` | Page web : caméra en direct, personne, message, historique, température/humidité, état ESP, armer/désarmer | PC serveur | `guard` |

Ordre de construction : `link` ∥ `face-id` → `door-node` ∥ `guard` → `dashboard`.

Le PC serveur est le PC d'un coéquipier : c'est lui qui a des ports USB-A pour la C270 et l'ESP. Le code y arrive par le dépôt GitHub de l'équipe.

## Contrat MQTT (module `link`)

Broker Mosquitto sur le PC serveur, **TLS 1.2 port 8883**, CA auto-signée (EC P-256) + mot de passe par compte (`server`, `esp`) + ACL : l'ESP ne peut lire que `led`/`fire` et écrire que `climate`/`status`. Tout est généré par `python -m sentinel.setup`. Ordres vers l'ESP en texte simple (pas de bibliothèque JSON sur l'ESP), mesures de l'ESP en JSON.

| Topic | Sens | Payload |
|---|---|---|
| `sentinel/door/led` | PC → ESP | texte : `green`, `red` ou `idle` (retained : l'ESP retrouve l'état après un redémarrage) |
| `sentinel/door/climate` | ESP → PC | `{"temp": 22.5, "hum": 48.0, "gas": 312}` toutes les 2 s (`gas` : 0–1023, plus c'est haut, plus il y a de gaz) |
| `sentinel/door/fire` | PC → ESP | texte : numéro du tir, ex. `17` (un message = un tir ; un numéro déjà vu est ignoré) |
| `sentinel/door/status` | ESP → PC | `online` / `offline` (retained + LWT `offline`) |

Changer ce contrat = **demander à l'équipe**.

## Logique `guard`

| État | Entrée | LED / voix / dashboard |
|---|---|---|
| `idle` | aucun visage depuis 3 s | LED éteintes |
| `green` | visage connu : moyenne des 3 photos les plus ressemblantes ≥ 0,45, stable sur ~0,6 s (70 % des images), visage d'au moins 70 px de large | vert, « Bienvenue <nom> » (gardé 3 s après la disparition du visage) |
| `red` | visage inconnu (et aucun membre dans l'image) | rouge, « ACCES REFUSE », capture enregistrée ; avertissement vocal à 3 s |

Règles de tir (toutes nécessaires) :

1. état = `red` ;
2. le visage est resté inconnu pendant `RED_BEFORE_FIRE_S` (11 s, réglable ; l'avertissement vocal part à `WARN_AFTER_S` = 3 s et dure ~7 s) : un visage connu entre-temps ou 3 s sans visage remettent le compte à zéro ;
3. système **armé** (désarmé au démarrage, armé depuis le dashboard) ;
4. 10 s minimum entre deux tirs.

Le firmware ne tire jamais s'il a perdu le lien depuis plus de 2 s.

## Stack

- **PC serveur** : Python (venv), `opencv-python` (YuNet détection + SFace reconnaissance, modèles ONNX), `paho-mqtt`, `fastapi` + `uvicorn`, `numpy`, SQLite (stdlib), avertissement vocal via la synthèse vocale de Windows (System.Speech, voix française).
- **Dashboard** : une page HTML + JS servie par FastAPI ; flux caméra en MJPEG ; données rafraîchies par polling. Pas de framework front.
- **Firmware** : un croquis Arduino (`.ino`) compilé avec **Arduino IDE**, déjà installé et testé sur le PC serveur. Cœur ESP8266, `PubSubClient`, `WiFiClientSecure` (BearSSL), `Servo`.
- **Broker** : Mosquitto (Windows).
- **Réseau** : partage de connexion du PC serveur (le Wi-Fi de l'école isole souvent les appareils).

## Commandes

```
install.bat                                  une fois : dépendances, modèles, Mosquitto, pare-feu, liaison chiffrée
start.bat                                    lance tout et ouvre http://localhost:8000
python -m sentinel.setup [--force]           (dossier server) régénère certificats, mots de passe, secrets.h
pytest ; ruff check . ; mypy server/sentinel vérifications
```

Firmware : Arduino IDE, `firmware/door-node/door-node.ino`, carte « NodeMCU 1.0 (ESP-12E Module) », bibliothèques PubSubClient et DHT sensor library.

## Structure

```
install.bat, start.bat   installation et lancement
firmware/door-node/      door-node.ino, secrets.h.example (secrets.h généré, ignoré par git)
link/                    généré : certificats, mosquitto.conf, passwd, acl (ignoré par git)
server/sentinel/         app.py (serveur + dashboard), face_id.py, enroll.py, guard.py, door.py, mqtt.py, store.py, setup.py
server/sentinel/static/  index.html (dashboard : Surveillance, Capteurs, Visages)
server/scripts/          get_models.py, windows_admin.ps1
server/tests/            tests pytest
data/                    faces/, snapshots/, sentinel.db (ignoré par git — photos de personnes)
```

## Style

Python : fonctions simples, types annotés, logique pure séparée du matériel (testable sans caméra ni MQTT).

```python
# extrait de server/sentinel/guard.py (pure, testé dans server/tests/test_guard.py)
red_since = state.red_since if state.command.state == "red" else now
fire = armed and now - red_since >= RED_BEFORE_FIRE_S and now - state.last_fire_at >= FIRE_COOLDOWN_S
cmd = Command("red", "ACCES REFUSE", fire)
return State(cmd, now, now if fire else state.last_fire_at, red_since), cmd
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
| D1 | Capteur DHT11 (module KY-015 : S → D1, milieu → 3V de l'ESP, droite → ligne −) | câblé et testé le 2026-10-06 (27,6 °C lus) |
| D2 | Servo SG90 (orange → D2, rouge → ligne +, marron → ligne −) | câblé et testé le 2026-10-06 |
| A0 | Capteur de gaz « Flying Fish » : AO → 2 × 100K en série → A0 (la broche A0 de la carte a déjà son pont interne 220K/100K, entrée max 3,3V) ; VCC → ligne +, GND → ligne −, DO vide | câblé et testé le 2026-10-06 (350–400 avec du gel hydroalcoolique) |
| D5, D6, D7, RX | ULN2003 IN1–IN4 pour le stepper | plus tard |
| D3, D4 | libres | — |

Le servo n'est **jamais** sur D4 : cette broche envoie des impulsions au démarrage, qui pourraient déclencher l'arbalète.

Courant : un port USB donne 500–900 mA ; le capteur de gaz chauffe en permanence (~150 mA, il est chaud au toucher, c'est normal). Le firmware coupe le stepper pendant un tir et à l'arrêt ; si l'ESP redémarre quand un moteur bouge → condensateur 470 µF entre + et −, ou chargeur USB séparé pour les moteurs (masse commune).

## Limites

- **Toujours** : démarrer désarmé ; secrets dans `.env` / `secrets.h` ; tester `guard.decide` avant chaque commit ; n'enrôler que des personnes d'accord ; un schéma clair pour chaque branchement.
- **Demander d'abord** : nouvelle dépendance ; changement du contrat MQTT ; changement du brochage.
- **Jamais** : de laser ; viser la tête ; tirer hors des 4 règles ci-dessus ; servo sur D4 ; commiter photos, captures, certificats ou base SQLite.

## Critères de réussite

1. Un membre enrôlé devant la C270 → LED verte + « Bienvenue <nom> » sur le dashboard en < 2 s.
2. Un inconnu → LED rouge en < 2 s, capture visible sur le dashboard, avertissement vocal à 3 s.
3. Inconnu seul : avertissement vocal à 3 s ; armé et toujours là à 11 s → un seul tir ; désarmé, connu ou membre présent dans l'image → aucun tir.
4. Lien coupé → l'ESP éteint ses LED et ne tire pas.
5. `mosquitto_sub` sans certificat ne peut pas se connecter (lien chiffré prouvé).
6. Le dashboard affiche la caméra en direct, la température et l'humidité, l'état de l'ESP et l'historique des passages, qui survit à un redémarrage.
7. `pytest`, `ruff`, `gitleaks` passent.

## Questions ouvertes

1. **Dépôt GitHub** : à créer par l'équipe ; bloque l'installation du code sur le PC serveur.
2. **Carte ULN2003** : à trouver ; sans elle, la caméra reste fixe.

Tranché le 2026-10-06 : kit capteurs du sujet non fourni, pas de PIR ni d'IA prédictive (accord du prof) ; les capteurs de l'équipe (DHT11 température/humidité, capteur de gaz « Flying Fish ») servent à l'affichage sur le dashboard ; **un seul ESP8266** (le 2ᵉ reste en secours) ; pas d'écran sur la porte, les messages s'affichent sur le dashboard ; pas de buzzer : avertissement vocal sur le PC (plus de bips depuis le 2026-10-07) ; firmware via Arduino IDE ; stepper plus tard ; pièces 3D gérées par l'équipe ; HC-SR04 abandonné au profit d'un capteur température/humidité, le tir part après 3 s de visage inconnu ; Python 3.14 + OpenCV 5.0 fonctionnent.
