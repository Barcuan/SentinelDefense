# Plan d'implémentation : Sentinel-X — Porte gardée

Source : [SPEC.md](../SPEC.md). Tâches détaillées : [todo.md](todo.md).
Refait le 2026-10-06 au soir : objectif « on installe, on lance, on ouvre le dashboard, et TOUT marche ».

## Vue d'ensemble

Le matériel est câblé et testé (LED, DHT11, servo, capteur de gaz). La reconnaissance et la page « Visages » existent. Il reste à **tout relier et tout automatiser** :

- **Installer une fois** (`install.bat`) : dépendances, modèles, Mosquitto, certificats, mots de passe et fichier de réglages de l'ESP, tout généré automatiquement. Seule question posée : le nom et le mot de passe du Wi-Fi.
- **Téléverser l'ESP une fois** depuis Arduino IDE (son fichier de réglages a été généré à l'installation).
- **Lancer** (`start.bat`) : un seul programme démarre le broker chiffré, la caméra, la logique de la porte, la liaison avec l'ESP et le dashboard, puis ouvre le navigateur.
- **Le dashboard** a trois onglets : **Surveillance** (caméra, verdict, armer/désarmer, historique avec captures), **Capteurs** (température, humidité, gaz en courbes, état de l'ESP), **Visages** (enregistrer, supprimer, régler le seuil).

## Décisions d'architecture

- **Un seul programme serveur** (`python -m sentinel.app`) lance lui-même Mosquitto en sous-processus : rien d'autre à démarrer à la main.
- **Certificats générés en Python** (`cryptography`), en courbe elliptique P-256 : plus légers pour l'ESP8266 que RSA. Le certificat du broker est valable pour `192.168.137.1` (l'adresse fixe du partage de connexion Windows) et `localhost`.
- **Heure du certificat fixée dans le firmware** (`setX509Time`) : l'ESP valide le certificat sans Internet ni NTP.
- **Ordres vers l'ESP en texte simple** (`green`, `red`, `idle`, numéro de tir) au lieu de JSON : pas de bibliothèque JSON à installer dans Arduino IDE. L'ESP renvoie ses mesures en JSON écrit à la main.
- **Un seul thread possède la caméra et les modèles** ; la logique de la porte tourne dans ce thread, et le client MQTT ne publie que quand l'état change.
- **Tout reste sur le PC** : dashboard sur `127.0.0.1` ; broker accessible seulement avec certificat + mot de passe ; secrets dans `.env` et `secrets.h`, jamais dans git.

## Graphe de dépendances

```
T5 liaison chiffrée (certificats, broker, réglages) ──┬── T6 firmware de l'ESP
                                                      └── T7 serveur ↔ ESP (MQTT + logique de la porte)
T3 guard ✅ ── T4 visages ✅ ── T15 page Visages ✅ ───────────┘
T7 ── T8 historique + captures + alarme ── T11 dashboard Surveillance + Capteurs ── T13 install.bat / start.bat + README
```

## Liste des tâches

### Fait
- [x] T1 : Python 3.14 + OpenCV
- [x] T3 : logique de tir (`guard.decide`) + tests
- [x] T4 : reconnaissance des visages (à vérifier devant la C270)
- [x] T15 : page Visages du dashboard (à vérifier devant la C270)
- [x] Matériel : LED D0/D8, DHT11 D1, servo D2, gaz A0 — câblés et testés

### Phase A : relier l'ESP au PC
- [x] T5 : Liaison chiffrée — certificats, configuration Mosquitto, mots de passe, `secrets.h` de l'ESP, générés par une commande
- [x] T6 : Firmware définitif `door-node.ino` — Wi-Fi, TLS, LED, servo, capteurs, sécurité en cas de coupure
- [x] T7 : Serveur ↔ ESP — le programme lance Mosquitto, publie LED et tirs, reçoit les mesures

**Checkpoint A** : tests verts ; la configuration Mosquitto démarre ; le firmware compile.

### Phase B : tout afficher
- [ ] T8 : Historique des passages (SQLite), captures des inconnus, alarme sonore
- [ ] T11 : Dashboard en onglets — Surveillance (verdict, armer, historique) et Capteurs (courbes, état ESP)

### Phase C : installer et lancer en une commande
- [ ] T13 : `install.bat`, `start.bat`, README en 3 étapes ; vérifications finales

**Checkpoint final** : sur le PC serveur, install → téléversement ESP → start → tout fonctionne depuis le dashboard.

### Plus tard
- [ ] T14 : moteur de la caméra (ULN2003)
- [ ] Pièces 3D (équipe)

## Risques et parades

| Risque | Impact | Parade |
|---|---|---|
| TLS trop lourd pour l'ESP8266 | Élevé | Certificats EC P-256 (petits) ; buffers BearSSL réduits ; heure fixée, pas de NTP |
| Pare-feu Windows bloque le port 8883 | Élevé | `install.bat` ajoute la règle (demande les droits administrateur une fois) |
| Wi-Fi de l'école isole l'ESP | Élevé | Partage de connexion du PC serveur (adresse fixe 192.168.137.1) |
| Je ne peux pas tester l'ESP réel d'ici | Moyen | Firmware compilé avec arduino-cli si autorisé ; logique testée côté serveur ; checklist pour l'essai réel |
| Servo + capteur de gaz + ESP sur un seul USB | Moyen | Port USB direct du PC ; condensateur ou chargeur séparé si l'ESP redémarre au tir |
| Pentest jeudi | Moyen | TLS + mot de passe par client ; dashboard local uniquement ; prénoms validés |
