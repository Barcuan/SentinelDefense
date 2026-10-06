# Tâches : Sentinel-X

Plan : [plan.md](plan.md). Spec : [SPEC.md](../SPEC.md). Règles : [CONSTRAINTS.md](../CONSTRAINTS.md).

Vérifications communes : `pytest` · `ruff check .` · `mypy server/sentinel` · firmware compilé (arduino-cli si disponible).
Chaque tâche de câblage s'accompagne d'un schéma sans croisement, extrémités écrites en texte.

---

## Fait

- [x] **T1** Python 3.14 + OpenCV 5.0, détection en 12 ms (`37310f4`)
- [x] **T3** `guard.decide` : tir après 3 s de visage inconnu, armé, 10 s entre deux tirs (`8fd75d7`)
- [x] **T4** Reconnaissance SFace + `enroll` (`d6a7665`) — à vérifier devant la C270 : les 3 membres reconnus, un inconnu rejeté
- [x] **T15** Dashboard : caméra en direct + page Visages (`024b42d`) — même vérification
- [x] **T2** Dépôt GitHub `Barcuan/SentinelDefense`, README d'installation
- [x] **Matériel** LED rouge D0, verte D8, DHT11 D1, servo D2, gaz A0 : câblés et testés un par un

---

## Phase A : relier l'ESP au PC

### T5 : Liaison chiffrée générée en une commande ✅
**Description :** `python -m sentinel.setup` demande le nom et le mot de passe du Wi-Fi, puis génère dans `link/` (ignoré par git) : une CA et un certificat broker EC P-256 (valables pour `192.168.137.1` et `localhost`), `mosquitto.conf` (8883, TLS, pas d'anonyme), le fichier de mots de passe (un compte serveur, un compte ESP) ; dans `.env` les mots de passe ; dans `firmware/door-node/secrets.h` le Wi-Fi, l'adresse du broker, le compte ESP, la CA et l'heure de génération.
**Critères :**
- [x] Le certificat broker est signé par la CA et valable pour 192.168.137.1 et localhost (testé)
- [x] `secrets.h` contient tout ce dont le firmware a besoin, et rien n'est ajouté à git (testé)
- [x] Relancer `setup` ne casse pas une installation existante (garde les fichiers sauf `--force`)
**Fichiers :** `server/sentinel/setup.py`, `server/tests/test_setup.py`, `.gitignore`

### T6 : Firmware définitif `door-node.ino` ✅ (compilé avec arduino-cli, esp8266 3.1.2 ; checklist d'essai dans T13)
**Description :** Wi-Fi ; MQTT sur TLS (CA + heure fixée) avec mot de passe ; `sentinel/door/status` avec LWT ; `sentinel/door/led` (`green`/`red`/`idle`) ; `sentinel/door/fire` (numéro de tir, ignoré s'il est répété) ; `sentinel/door/climate` toutes les 2 s (temp, hum, gas) ; servo au repos dès le démarrage ; lien coupé depuis plus de 2 s → LED éteintes, pas de tir.
**Critères :**
- [x] Compile pour « NodeMCU 1.0 (ESP-12E Module) » avec les bibliothèques `PubSubClient` et `DHT sensor library`
- [x] Aucun secret dans le fichier : tout vient de `secrets.h`
- [ ] Checklist d'essai réel écrite dans le README
**Fichiers :** `firmware/door-node/door-node.ino`, `firmware/door-node/secrets.h.example`

### T7 : Serveur ↔ ESP
**Description :** au démarrage, `sentinel.app` lance Mosquitto avec `link/mosquitto.conf`, se connecte en TLS, s'abonne à `climate` et `status`. La logique de la porte (`guard.decide`) tourne dans le thread caméra : publie `led` quand l'état change, `fire` à chaque tir. Armé/désarmé côté serveur (désarmé au démarrage).
**Critères :**
- [ ] Une mesure `climate` valide est enregistrée ; une mesure invalide est ignorée sans planter (testé)
- [ ] `led` n'est publié que quand l'état change ; un tir = un message `fire` avec un numéro qui augmente (testé avec un faux client)
- [ ] Sans Mosquitto installé, le dashboard démarre quand même et l'affiche clairement
**Fichiers :** `server/sentinel/mqtt.py`, `server/sentinel/door.py`, `server/sentinel/app.py`, tests

### ✅ Checkpoint A
- [ ] pytest, ruff, mypy verts ; firmware compilé ; commit + push + `graphify update .`

---

## Phase B : tout afficher

### T8 : Historique, captures, alarme
**Description :** SQLite `data/sentinel.db` : un passage = une ligne (heure, nom ou inconnu, score, capture si inconnu, tir ou non) ; mesures capteurs (une par 2 s, gardées 24 h). Alarme `winsound` qui ne bloque pas la caméra, une fois par passage inconnu.
**Critères :**
- [ ] Un passage = une ligne, pas une par image (testé)
- [ ] Les mesures se relisent dans l'ordre, les plus anciennes que 24 h sont effacées (testé)
- [ ] Captures et base hors de git
**Fichiers :** `server/sentinel/store.py`, `server/tests/test_store.py`, `server/sentinel/app.py`

### T11 : Dashboard en onglets
**Description :** **Surveillance** : caméra, verdict en gros (« Bienvenue <nom> » / « ACCES REFUSE » / « En attente »), bouton armer/désarmer, état de l'ESP, historique des passages avec captures. **Capteurs** : valeurs actuelles et courbes température, humidité, gaz (dessinées sans bibliothèque externe), état de l'ESP. **Visages** : la page existante.
**Critères :**
- [ ] Un passage apparaît en < 3 s sans recharger ; l'historique survit à un redémarrage
- [ ] Armer/désarmer change le comportement ; au démarrage : désarmé
- [ ] ESP débranché → « hors ligne » en < 5 s
**Fichiers :** `server/sentinel/app.py`, `server/sentinel/static/index.html`

---

## Phase C : installer et lancer

### T13 : Installation et lancement en une commande
**Description :** `install.bat` : vérifie Python, crée le venv, installe les dépendances, télécharge les modèles, installe Mosquitto (winget), ajoute la règle de pare-feu pour le port 8883, lance `sentinel.setup`. `start.bat` : lance `sentinel.app` et ouvre le navigateur. README réécrit en 3 étapes : installer, téléverser l'ESP, lancer.
**Critères :**
- [ ] Les deux scripts fonctionnent depuis un double-clic
- [ ] README : installation + checklist d'essai réel + dépannage
- [ ] Toutes les vérifications passent ; push sur GitHub
**Fichiers :** `install.bat`, `start.bat`, `README.md`

---

## Plus tard

- [ ] **T14** Moteur de la caméra via ULN2003 (D5, D6, D7, RX), coupé pendant un tir
- [ ] **Pièces 3D** (équipe) : arbalète déclenchée 5 fois sur 5, visée au torse ; support caméra
