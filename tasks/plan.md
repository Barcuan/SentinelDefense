# Plan d'implémentation : Sentinel-X — Porte gardée

Source : [SPEC.md](../SPEC.md). Tâches détaillées : [todo.md](todo.md).
Fenêtre : mardi 2026-10-06 → mercredi soir (gel du code jeudi matin). 3 personnes en parallèle.

## Vue d'ensemble

On lève d'abord les deux paris risqués (OpenCV sur ce Python, TLS sur ESP8266), puis on construit la porte en tranches verticales : chaque tranche va de la caméra jusqu'à l'actionneur et se démontre seule (lumière → alarme + capture → tir). Le dashboard vient en dernier, sur une base d'événements déjà remplie.

## Décisions d'architecture

- **Contrat MQTT figé dans SPEC.md avant tout code** : c'est ce qui permet aux 3 personnes de travailler en parallèle sans s'attendre.
- **Deux ESP aux rôles clairs** : `panel` (ce qu'on voit : LCD + LED) et `turret` (ce qui bouge : distance, arbalète, caméra).
- **`guard.decide` est une fonction pure** : la logique de tir se teste sans caméra, sans ESP, sans broker.
- **Double vérification du tir** : le PC décide, la turret revérifie distance + fraîcheur du lien.
- **Réseau = partage de connexion du PC portable** : IP du broker stable, démo reproductible.
- **TLS ESP8266 avec CA + NTP** ; repli sur l'empreinte du certificat du broker si la mémoire ou l'heure posent problème. Jamais `setInsecure()`.

## Graphe de dépendances

```
T1 env Python ── T4 face-id ──┐
T5 guard ─────────────────────┼── T6 tranche lumière ── T7 tranche alarme ── T9 dashboard
T2 broker TLS ─┬─ T3 panel TLS┘                                                │
               └─ T10 turret TLS ──────────────────────── T8 tranche tir ──────┘
                        └── T14 balayage caméra
T12 pièces 3D (équipe, hors code) ── montage final de T8
```

## Répartition suggérée

| Personne | Tâches |
|---|---|
| Vision | T1, T4, puis aide sur T7 (capture) |
| Firmware | T3, T10, partie firmware de T6 et T8, T14 |
| Serveur | T2, T5, partie serveur de T6–T8, T9 |

## Liste des tâches

### Phase 1 : Fondations (mardi)
- [ ] T1 : Environnement Python + OpenCV YuNet/SFace qui tourne
- [ ] T2 : Broker Mosquitto TLS + client Python
- [ ] T3 : panel se connecte au broker en TLS
- [ ] T5 : `guard.decide` + tests des règles de tir

**Checkpoint 1** : pytest vert, un ESP publie en TLS, un client sans certificat est refusé.

### Phase 2 : La porte, en tranches (mardi soir → mercredi midi)
- [ ] T4 : face-id — enrôlement + reconnaissance en direct
- [ ] T6 : Tranche « lumière » — visage → LED verte/rouge + LCD
- [ ] T7 : Tranche « alarme » — inconnu → son sur le PC + capture + événement en base
- [ ] T10 : turret se connecte en TLS et publie la distance
- [ ] T8 : Tranche « tir » — distance → servo, avec failsafe

**Checkpoint 2** : critères de réussite 1 à 5 démontrés sur breadboard.

### Phase 3 : Dashboard et finitions (mercredi)
- [ ] T9 : Dashboard — personne devant la porte, historique, armer/désarmer
- [ ] T14 : Stepper — la caméra balaie gauche ↔ droite (si ULN2003 trouvée)
- [ ] T12 : Pièces 3D (arbalète, support caméra) — équipe, hors code

**Checkpoint 3** : les 7 critères de réussite passent.

### Phase 4 : Gel du code (mercredi soir)
- [ ] T13 : Répétition de la démo + outils CONSTRAINTS + README

## Risques et parades

| Risque | Impact | Parade |
|---|---|---|
| Pas de wheel `opencv-python` pour Python 3.14 | Élevé | T1 en premier ; venv Python 3.12 sinon |
| TLS trop lourd pour l'ESP8266 (RAM, heure) | Élevé | T3 tôt ; buffers BearSSL réduits ; empreinte au lieu de CA |
| Wi-Fi école bloque ESP ↔ PC | Élevé | Partage de connexion du PC ; règle pare-feu Windows pour le port 8883 |
| LCD 5V piloté en 3,3V : écran vide | Moyen | RW à la masse (écriture seule), ajuster le contraste ; sinon tout afficher sur le dashboard |
| Un moteur fait rebooter l'ESP (chute de tension) | Moyen | Condensateur 470 µF, ou alim 5V séparée, masse commune |
| Reconnaissance ratée (éclairage, caméra en mouvement) | Moyen | 5+ photos par personne dans la salle ; balayage lent ; seuil réglable |
| Pas de carte ULN2003 | Faible | Caméra fixe, T14 abandonnée |
| Arbalète pas prête | Faible | Le servo qui lève un drapeau suffit à démontrer la logique |
| Pentest des autres groupes jeudi après-midi | Moyen | TLS + mots de passe sur le broker ; dashboard seulement sur le réseau de table |

## Questions ouvertes

1. Carte ULN2003 trouvée ? (décide T14)
