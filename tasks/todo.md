# Tâches : Sentinel-X

Plan : [plan.md](plan.md). Spec : [SPEC.md](../SPEC.md). Règles : [CONSTRAINTS.md](../CONSTRAINTS.md).

Commandes de vérification communes :
`pytest server/tests` · `ruff check .` · `gitleaks detect --redact --no-banner` · `pio run -d firmware/<node>`

---

## Phase 1 : Fondations

### T1 : Environnement Python + OpenCV YuNet/SFace
**Description :** Venv, dépendances, téléchargement des modèles ONNX, script qui ouvre la C270 et encadre les visages. Lève le risque « pas de wheel pour 3.14 ». Installe aussi ruff/mypy (CONSTRAINTS).
**Critères :**
- [x] `pip install -r server/requirements.txt` passe (Python 3.14, sinon 3.12)
- [x] La C270 s'affiche avec un cadre sur chaque visage détecté
- [x] `server/models/` et `data/` ignorés par git
**Vérification :** lancer le script, montrer 1 puis 2 visages ; `git status` ne montre ni modèle ni photo.
**Dépend de :** —
**Fichiers :** `server/requirements.txt`, `server/sentinel/face_id.py`, `server/scripts/get_models.py`, `.gitignore`
**Taille :** S

### T2 : Broker Mosquitto TLS + client Python
**Description :** CA auto-signée, certificats broker/nœuds, `mosquitto.conf` (8883, TLS, mots de passe), wrapper `mqtt.py`.
**Critères :**
- [ ] `mosquitto_pub/sub` avec CA + identifiants fonctionne sur 8883
- [ ] Le même client sans CA ou sans mot de passe est refusé (critère de réussite 5)
- [ ] Certificats et mots de passe hors de git
**Vérification :** les deux commandes ci-dessus ; `gitleaks detect --redact --no-banner`.
**Dépend de :** —
**Fichiers :** `server/scripts/gen_certs.py`, `link/mosquitto.conf`, `server/sentinel/mqtt.py`, `.gitignore`
**Taille :** M

### T3 : panel se connecte en TLS
**Description :** Projet PlatformIO, Wi-Fi (partage de connexion du PC), NTP, connexion TLS au broker, `sentinel/panel/status` avec LWT. Lève le risque TLS sur ESP8266 ; le code de connexion sera réutilisé par la turret.
**Critères :**
- [ ] `{"online": true}` reçu sur le PC à la mise sous tension
- [ ] Débrancher l'ESP → `{"online": false}` reçu (LWT)
- [ ] Secrets dans `include/secrets.h`, seul `secrets.h.example` est commité
**Vérification :** `pio run -d firmware/panel -t upload` + `mosquitto_sub -t 'sentinel/#'`.
**Dépend de :** T2
**Fichiers :** `firmware/panel/platformio.ini`, `src/main.cpp`, `include/secrets.h.example`
**Taille :** M

### T5 : `guard.decide` + tests
**Description :** Machine d'états pure (idle/green/red) et les 4 règles de tir de la spec.
**Critères :**
- [ ] Tests : autorisé → jamais de tir ; inconnu désarmé → pas de tir ; inconnu armé loin → pas de tir ; inconnu armé proche → 1 tir puis délai de 10 s ; plus de visage depuis 3 s → idle
- [ ] Aucun import matériel/réseau dans `guard.py`
**Vérification :** `pytest server/tests`.
**Dépend de :** —
**Fichiers :** `server/sentinel/guard.py`, `server/tests/test_guard.py`
**Taille :** S

### ✅ Checkpoint 1
- [ ] pytest vert, ruff propre
- [ ] panel visible en TLS, client sans certificat refusé
- [ ] OpenCV détecte les visages sur la C270

---

## Phase 2 : La porte, en tranches

### T4 : face-id — enrôlement + reconnaissance
**Description :** `enroll` calcule les empreintes SFace de `data/faces/<nom>/*.jpg` ; la boucle live renvoie `Face(name, authorized, score)` + image.
**Critères :**
- [ ] Chaque membre enrôlé est reconnu (score ≥ 0.363) sous l'éclairage de la salle
- [ ] Une personne non enrôlée → `inconnu`
- [ ] Seuil réglable sans toucher au code
**Vérification :** démo manuelle à 3 + 1 inconnu.
**Dépend de :** T1
**Fichiers :** `server/sentinel/face_id.py`, `server/sentinel/enroll.py`
**Taille :** M

### T6 : Tranche « lumière »
**Description :** Boucle serveur face-id → `guard.decide` → `sentinel/door/cmd` ; le panel allume vert/rouge et écrit sur le LCD (mode 4 bits).
**Critères :**
- [ ] Membre devant la caméra → LED verte + « Bienvenue <nom> » en < 2 s (critère 1)
- [ ] Inconnu → LED rouge + « ACCES REFUSE » en < 2 s
- [ ] Personne → tout s'éteint après 3 s
**Vérification :** test sur breadboard, chronométré.
**Dépend de :** T3, T4, T5
**Fichiers :** `server/sentinel/app.py`, `firmware/panel/src/main.cpp`
**Taille :** M

### T7 : Tranche « alarme »
**Description :** En rouge, le PC joue un son d'alarme (`winsound`) ; capture JPEG dans `data/snapshots/` + événement SQLite (heure, nom/inconnu, capture). Les passages autorisés sont aussi enregistrés (suivi).
**Critères :**
- [ ] Inconnu → alarme qui sonne pendant l'état rouge (critère 2)
- [ ] Une capture + une ligne en base par passage (pas une par image)
- [ ] Captures et base hors de git
**Vérification :** `sqlite3 data/sentinel.db "select * from events"` + fichier présent.
**Dépend de :** T6
**Fichiers :** `server/sentinel/store.py`, `server/sentinel/app.py`
**Taille :** M

### T10 : turret se connecte en TLS et publie la distance
**Description :** 2ᵉ projet PlatformIO, reprend le code de connexion de T3 ; HC-SR04 (ECHO via pont diviseur) publie `sentinel/turret/distance` toutes les 200 ms.
**Critères :**
- [ ] Distances plausibles reçues sur le PC (main à 20 cm → ~20)
- [ ] LWT `sentinel/turret/status` fonctionne
**Vérification :** `mosquitto_sub -t 'sentinel/turret/#'`.
**Dépend de :** T3
**Fichiers :** `firmware/turret/platformio.ini`, `src/main.cpp`, `include/secrets.h.example`
**Taille :** M

### T8 : Tranche « tir »
**Description :** guard publie `sentinel/turret/fire` ; la turret revérifie la distance et la fraîcheur du lien avant d'actionner le SG90.
**Critères :**
- [ ] Inconnu + < 50 cm + armé → exactement 1 tir (critère 3)
- [ ] Désarmé ou autorisé → aucun tir
- [ ] Broker coupé → la turret ne tire pas, le panel passe en idle (critère 4)
**Vérification :** les 3 scénarios sur breadboard ; `pytest server/tests`.
**Dépend de :** T7, T10
**Fichiers :** `firmware/turret/src/main.cpp`, `firmware/panel/src/main.cpp`, `server/sentinel/app.py`
**Taille :** M

### ✅ Checkpoint 2
- [ ] Critères de réussite 1 à 5 démontrés
- [ ] pytest, ruff, gitleaks verts
- [ ] Commit + `graphify update .`

---

## Phase 3 : Dashboard et finitions

### T9 : Dashboard
**Description :** Page FastAPI : dernière personne + capture, historique des passages (nom/inconnu, heure, capture), bouton armer/désarmer (désarmé au démarrage).
**Critères :**
- [ ] Un nouveau passage apparaît en < 3 s sans recharger la page (critère 2)
- [ ] L'historique survit à un redémarrage du serveur (critère 6)
- [ ] Le bouton armer/désarmer change réellement le comportement de T8 ; au redémarrage : désarmé
**Vérification :** démo navigateur sur `http://localhost:8000`.
**Dépend de :** T7 (T8 pour le bouton)
**Fichiers :** `server/sentinel/app.py`, `server/sentinel/static/index.html`
**Taille :** M

### T14 : La caméra balaie gauche ↔ droite (si ULN2003 trouvée)
**Description :** Sur la turret, le 28BYJ-48 (via ULN2003) fait des allers-retours lents sur un angle fixe, sans lien avec le PC.
**Critères :**
- [ ] Balayage continu sur l'angle réglé (constante en tête de fichier), sans retarder la mesure de distance ni le tir
- [ ] La reconnaissance (T4) marche encore pendant le balayage
**Vérification :** 2 min de balayage + passer devant la caméra.
**Dépend de :** T10
**Fichiers :** `firmware/turret/src/main.cpp`
**Taille :** S

### T12 : Pièces 3D (géré par l'équipe, hors code)
**Description :** Arbalète déclenchée par le SG90 (projectile mousse/papier) + support de caméra pour le stepper.
**Critères :**
- [ ] Le servo déclenche le tir de façon fiable 5 fois sur 5
- [ ] Monté visé au torse, pas à hauteur de tête

### ✅ Checkpoint 3
- [ ] Les 7 critères de réussite de la spec passent

---

## Phase 4 : Gel du code

### T13 : Démo + rendu
**Description :** Installer gitleaks, faire passer CONSTRAINTS, README avec câblage et commandes, 2 répétitions complètes de la démo.
**Critères :**
- [ ] `ruff`, `mypy`, `pytest`, `gitleaks` passent (ou avertissements expliqués)
- [ ] Un membre qui n'a pas codé une partie peut la lancer depuis le README
- [ ] Démo de bout en bout réussie 2 fois de suite
**Vérification :** répétition chronométrée.
**Dépend de :** Checkpoint 3
**Fichiers :** `README.md`
**Taille :** S
