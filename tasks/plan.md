# Plan d'implémentation : Sentinel-X — Porte gardée

Source : [SPEC.md](../SPEC.md). Tâches détaillées : [todo.md](todo.md).
Refait le 2026-10-06 : un seul ESP, plus d'écran, stepper reporté.
Fenêtre : mardi soir → mercredi soir (gel du code jeudi matin). 3 personnes.

## Vue d'ensemble

Le cœur de la démo, dans l'ordre : **la caméra reconnaît → LED verte/rouge → le servo tire sur un inconnu qui entre → le dashboard montre tout.** On construit d'abord ce qui bloque tout le reste (dépôt partagé, PC serveur, lien chiffré), puis la porte en tranches verticales qui se démontrent chacune seule, puis le dashboard.

## Décisions d'architecture

- **Un seul ESP8266** (`door-node`) : un programme, une connexion TLS ; le 2ᵉ ESP reste en secours.
- **Arduino IDE pour le firmware** : déjà installé et testé sur le PC serveur, pas besoin de PlatformIO.
- **Le PC serveur est celui du coéquipier** (ports USB-A pour la C270 et l'ESP) ; le code y arrive par GitHub.
- **`guard.decide` est une fonction pure** : la logique de tir se teste sans caméra, sans ESP, sans broker.
- **Double vérification du tir** : le PC décide, l'ESP vérifie la fraîcheur du lien.
- **TLS ESP8266 avec CA + NTP** ; repli sur l'empreinte du certificat si la mémoire ou l'heure posent problème. Jamais `setInsecure()`.
- **Chaque branchement = un schéma** clair, sans fil qui passe au-dessus d'un trou où il ne va pas.

## Graphe de dépendances

```
T2 dépôt + PC serveur ──┬── T5 broker TLS ── T6 ESP en TLS + LED ──┐
                        │                                          ├── T7 « lumière » ── T8 « capture » ── T11 dashboard v1 ── T12 dashboard v2
T1 OpenCV ✅ ── T4 face-id ─────────────────────────────────────────┘                                          │
T3 guard + tests ───────────────────────────────── T10 « tir » ── T9 capteurs ─────────────────────────────────┘
```

## Répartition suggérée

| Personne | Tâches |
|---|---|
| Vision | T4, puis T8 (capture) |
| Matériel + firmware | T6, T9, T10 (câblage + croquis) |
| Serveur | T2, T5, T3, T7, T11, T12, T15 |

## Liste des tâches

### Phase 1 : Fondations (mardi soir)
- [x] T1 : Environnement Python + OpenCV YuNet qui tourne
- [ ] T2 : Dépôt GitHub partagé + PC serveur prêt (code, venv, C270)
- [x] T3 : `guard.decide` + tests des règles de tir
- [ ] T4 : face-id — enrôlement + reconnaissance en direct (code fait, à vérifier devant la C270)
- [ ] T5 : Broker Mosquitto TLS + client Python

**Checkpoint 1** : sur le PC serveur, la C270 reconnaît les 3 membres ; pytest vert ; un client sans certificat est refusé par le broker.

### Phase 2 : La porte, en tranches (mercredi matin)
- [ ] T6 : L'ESP se connecte en TLS et allume ses LED sur ordre MQTT
- [ ] T7 : Tranche « lumière » — visage connu/inconnu → LED verte/rouge
- [ ] T8 : Tranche « capture » — inconnu → alarme + capture + événement en base
- [ ] T9 : Les capteurs publient température, humidité et gaz
- [ ] T10 : Tranche « tir » — servo + règles de tir + failsafe

**Checkpoint 2** : critères de réussite 1 à 5 démontrés sur breadboard.

### Phase 3 : Dashboard (mercredi après-midi)
- [ ] T11 : Dashboard v1 — message, personne + capture, historique
- [ ] T12 : Dashboard v2 — caméra en direct, température/humidité/gaz, état ESP, armer/désarmer
- [ ] T15 : Page « Visages » — enregistrer, supprimer et régler la reconnaissance depuis le dashboard

**Checkpoint 3** : les 7 critères de réussite passent.

### Phase 4 : Gel du code (mercredi soir)
- [ ] T13 : Répétition de la démo + outils CONSTRAINTS + README

### Plus tard (si le temps le permet)
- [ ] T14 : Stepper — la caméra balaie gauche ↔ droite (ULN2003 à trouver)
- [ ] Pièces 3D (arbalète, support caméra) — gérées par l'équipe, hors code

## Risques et parades

| Risque | Impact | Parade |
|---|---|---|
| Pas de dépôt GitHub → code bloqué sur un PC sans USB-A | Élevé | T2 en premier ; en dépannage, clé USB / zip |
| TLS trop lourd pour l'ESP8266 (RAM, heure) | Élevé | T6 tôt ; empreinte du certificat au lieu de la CA |
| Wi-Fi école bloque ESP ↔ PC | Élevé | Partage de connexion du PC serveur ; règle pare-feu pour le port 8883 |
| Servo + stepper font rebooter l'ESP (courant USB) | Moyen | Stepper coupé pendant le tir ; condensateur 470 µF ; chargeur séparé |
| Servo qui bouge au démarrage de l'ESP | Moyen | Servo sur D2 (jamais D4) ; position « repos » fixée dès `setup()` |
| Reconnaissance ratée (éclairage) | Moyen | 5+ photos par personne dans la salle de démo ; seuil réglable |
| Erreur de câblage (déjà arrivé 2 fois) | Moyen | Un schéma sans croisement par étape, extrémités écrites en texte |
| Pentest des autres groupes jeudi après-midi | Moyen | TLS + mots de passe sur le broker ; dashboard seulement sur le réseau de table |

## Questions ouvertes

1. Lien du dépôt GitHub (bloque T2).
2. Carte ULN2003 trouvée ? (décide T14)
