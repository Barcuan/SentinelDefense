# Tâches : Sentinel-X

Plan : [plan.md](plan.md). Spec : [SPEC.md](../SPEC.md). Règles : [CONSTRAINTS.md](../CONSTRAINTS.md).

Commandes de vérification communes :
`pytest` · `ruff check .` · `mypy server/sentinel` · `gitleaks detect --redact --no-banner` · Arduino IDE « Vérifier » sur `firmware/door-node/door-node.ino`

Chaque tâche de câblage s'accompagne d'un schéma sans croisement, extrémités écrites en texte.

---

## Phase 1 : Fondations

### T1 : Environnement Python + OpenCV YuNet ✅
Fait le 2026-10-06 (commit `37310f4`) : Python 3.14 + OpenCV 5.0, détection en 12 ms par image.
- [x] `pip install -r server/requirements.txt` passe
- [x] La webcam s'affiche avec un cadre sur chaque visage
- [x] `server/models/` et `data/` ignorés par git

### T2 : Dépôt GitHub partagé + PC serveur prêt
**Description :** L'équipe crée le dépôt ; on y pousse le code ; le PC serveur (coéquipier) clone, crée le venv, télécharge les modèles, et lance l'aperçu avec la **C270** (pas la webcam intégrée).
**Critères :**
- [ ] Le dépôt contient le code, sans modèle, photo ni secret
- [ ] Sur le PC serveur : `pytest` passe et l'aperçu `face_id.py` montre l'image de la C270 avec un cadre sur le visage
- [ ] L'index de la C270 est réglable sans toucher au code (si la webcam intégrée est la caméra 0)
**Vérification :** aperçu lancé sur le PC serveur ; `gitleaks detect --redact --no-banner`.
**Dépend de :** T1 ; lien du dépôt fourni par l'équipe
**Fichiers :** `README.md` (installation), `server/sentinel/face_id.py`
**Taille :** S

### T3 : `guard.decide` + tests ✅
**Description :** Machine d'états pure (idle/green/red) et les 4 règles de tir de la spec.
**Critères :**
- [x] Tests : connu → jamais de tir ; inconnu désarmé → pas de tir ; inconnu armé loin → pas de tir ; inconnu armé proche → 1 tir puis délai de 10 s ; plus de visage depuis 3 s → idle
- [x] Aucun import matériel/réseau dans `guard.py`
**Vérification :** `pytest`.
**Dépend de :** —
**Fichiers :** `server/sentinel/guard.py`, `server/tests/test_guard.py`
**Taille :** S

### T4 : face-id — enrôlement + reconnaissance
**Description :** `enroll` calcule les empreintes SFace de `data/faces/<nom>/*.jpg` ; la boucle live renvoie `Face(name, authorized, score)` + image ; l'aperçu affiche le nom ou « inconnu ».
**Critères :**
- [ ] Chaque membre enrôlé est reconnu (score ≥ 0.363) sous l'éclairage de la salle
- [ ] Une personne non enrôlée → « inconnu »
- [ ] Seuil réglable sans toucher au code
**Vérification :** démo à 3 + 1 inconnu devant la C270.
**Dépend de :** T1 (T2 pour le test avec la C270)
**Fichiers :** `server/sentinel/face_id.py`, `server/sentinel/enroll.py`, `server/tests/test_face_id.py`
**Taille :** M

### T5 : Broker Mosquitto TLS + client Python
**Description :** Installer Mosquitto sur le PC serveur ; CA auto-signée et certificats ; `mosquitto.conf` (8883, TLS, mots de passe) ; wrapper `mqtt.py`.
**Critères :**
- [ ] `mosquitto_pub/sub` avec CA + identifiants fonctionne sur 8883
- [ ] Le même client sans CA ou sans mot de passe est refusé (critère 5)
- [ ] Certificats et mots de passe hors de git
**Vérification :** les deux commandes ci-dessus ; `gitleaks detect --redact --no-banner`.
**Dépend de :** T2
**Fichiers :** `server/scripts/gen_certs.py`, `link/mosquitto.conf`, `server/sentinel/mqtt.py`, `.gitignore`
**Taille :** M

### ✅ Checkpoint 1
- [ ] Sur le PC serveur, la C270 reconnaît les 3 membres
- [ ] pytest vert, ruff propre
- [ ] Client sans certificat refusé par le broker

---

## Phase 2 : La porte, en tranches

### T6 : L'ESP se connecte en TLS et allume ses LED sur ordre
**Description :** Croquis `door-node.ino` : Wi-Fi (partage de connexion du PC serveur), NTP, MQTT TLS, `sentinel/door/status` avec LWT, et `sentinel/door/led` qui pilote les LED déjà câblées (rouge D0, verte D8). Pas de nouveau câblage.
**Critères :**
- [ ] `{"online": true}` reçu sur le PC à la mise sous tension ; débrancher l'ESP → `{"online": false}`
- [ ] `mosquitto_pub -t sentinel/door/led -m '{"state":"green"}'` allume la verte ; `red` la rouge ; `idle` éteint
- [ ] Seul `secrets.h.example` est commité
**Vérification :** Téléverser depuis Arduino IDE + `mosquitto_sub -t 'sentinel/#'`.
**Dépend de :** T5
**Fichiers :** `firmware/door-node/door-node.ino`, `firmware/door-node/secrets.h.example`
**Taille :** M

### T7 : Tranche « lumière »
**Description :** Boucle serveur : face-id → `guard.decide` → `sentinel/door/led`.
**Critères :**
- [ ] Membre devant la caméra → LED verte en < 2 s, nom dans les logs du serveur
- [ ] Inconnu → LED rouge en < 2 s
- [ ] Personne → LED éteintes après 3 s
**Vérification :** test chronométré devant la C270.
**Dépend de :** T3, T4, T6
**Fichiers :** `server/sentinel/app.py`
**Taille :** M

### T8 : Tranche « capture »
**Description :** En rouge : alarme sur le PC (`winsound`), capture JPEG dans `data/snapshots/` ; chaque passage (connu ou inconnu) devient un événement SQLite (heure, nom/inconnu, capture).
**Critères :**
- [ ] Inconnu → alarme pendant l'état rouge (critère 2)
- [ ] Une capture + une ligne en base par passage, pas une par image
- [ ] Captures et base hors de git
**Vérification :** `sqlite3 data/sentinel.db "select * from events"` + fichier présent.
**Dépend de :** T7
**Fichiers :** `server/sentinel/store.py`, `server/sentinel/app.py`, `server/tests/test_store.py`
**Taille :** M

### T9 : Le capteur DHT publie température et humidité
**Description :** Câblage du capteur DHT (données sur D1, alimentation sur la broche 3V de l'ESP) avec schéma ; le croquis publie `sentinel/door/climate` toutes les 2 s.
**Critères :**
- [ ] Valeurs plausibles reçues sur le PC (souffler sur le capteur fait monter l'humidité)
- [ ] Une lecture ratée n'envoie rien plutôt qu'une valeur fausse
**Vérification :** `mosquitto_sub -t sentinel/door/climate`.
**Dépend de :** T6
**Fichiers :** `firmware/door-node/door-node.ino`
**Taille :** S

### T10 : Tranche « tir »
**Description :** Câblage du servo sur D2 avec schéma ; position de repos dès `setup()` ; guard publie `sentinel/door/fire` ; l'ESP vérifie la fraîcheur du lien avant de tirer.
**Critères :**
- [ ] Inconnu pendant 3 s + armé → exactement 1 tir (critère 3)
- [ ] Désarmé ou connu → aucun tir ; le servo ne bouge pas au démarrage de l'ESP
- [ ] Broker coupé → LED éteintes, pas de tir (critère 4)
**Vérification :** les 3 scénarios devant la C270 ; `pytest`.
**Dépend de :** T7
**Fichiers :** `firmware/door-node/door-node.ino`, `server/sentinel/app.py`
**Taille :** M

### ✅ Checkpoint 2
- [ ] Critères de réussite 1 à 5 démontrés
- [ ] pytest, ruff, gitleaks verts
- [ ] Commit + push + `graphify update .`

---

## Phase 3 : Dashboard

### T11 : Dashboard v1 — message, personne, historique
**Description :** Page FastAPI : message en gros (« Bienvenue <nom> » / « ACCES REFUSE » / « En attente »), dernière personne + capture, historique des passages.
**Critères :**
- [ ] Un passage apparaît en < 3 s sans recharger la page (critères 1 et 2)
- [ ] L'historique survit à un redémarrage du serveur
**Vérification :** navigateur sur `http://localhost:8000`.
**Dépend de :** T8
**Fichiers :** `server/sentinel/app.py`, `server/sentinel/static/index.html`
**Taille :** M

### T12 : Dashboard v2 — caméra, température/humidité, ESP, armer
**Description :** Flux MJPEG de la C270 avec les cadres et noms ; température et humidité en direct avec une courbe ; ESP en ligne / hors ligne ; bouton armer/désarmer (désarmé au démarrage).
**Critères :**
- [ ] La caméra s'affiche en direct dans la page (critère 6)
- [ ] Débrancher l'ESP → « hors ligne » en < 5 s
- [ ] Le bouton armer/désarmer change réellement le comportement de T10 ; au redémarrage : désarmé
**Vérification :** démo navigateur.
**Dépend de :** T10, T11
**Fichiers :** `server/sentinel/app.py`, `server/sentinel/static/index.html`
**Taille :** M

### ✅ Checkpoint 3
- [ ] Les 7 critères de réussite de la spec passent

---

## Phase 4 : Gel du code

### T13 : Démo + rendu
**Description :** Installer gitleaks, faire passer CONSTRAINTS, README (installation, câblage, commandes), 2 répétitions complètes de la démo.
**Critères :**
- [ ] `ruff`, `mypy`, `pytest`, `gitleaks` passent (ou avertissements expliqués)
- [ ] Un membre qui n'a pas codé une partie peut la lancer depuis le README
- [ ] Démo de bout en bout réussie 2 fois de suite
**Dépend de :** Checkpoint 3
**Fichiers :** `README.md`
**Taille :** S

---

## Plus tard

### T14 : La caméra balaie gauche ↔ droite (si ULN2003 trouvée)
**Description :** 28BYJ-48 via ULN2003 sur D5, D6, D7, RX ; allers-retours lents ; moteur coupé pendant un tir et à l'arrêt.
**Critères :**
- [ ] Balayage continu sans retarder les mesures ni le tir ; l'ESP ne redémarre pas pendant un tir
- [ ] La reconnaissance marche encore pendant le balayage
**Dépend de :** T10
**Taille :** S

### Pièces 3D (équipe, hors code)
- [ ] Arbalète : le servo déclenche le tir 5 fois sur 5, visée au torse
- [ ] Support caméra
