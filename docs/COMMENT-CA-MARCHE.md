# Comment marche Sentinel-X (version simple)

Ce document explique le projet sans jargon : ce que fait chaque morceau, et comment ils se parlent. Pour installer et lancer, voir le [README](../README.md). Pour les détails techniques, voir la [SPEC](../SPEC.md).

## L'idée en une phrase

Une caméra regarde la porte. Si elle reconnaît un membre de l'équipe, la lumière passe au vert. Si c'est un inconnu, la lumière passe au rouge, le PC le prévient à voix haute, et s'il ne part pas, une arbalète imprimée en 3D tire une balle en mousse. En plus, des capteurs surveillent la température, l'humidité et le gaz.

## Les trois morceaux

```
 Webcam C270 ──USB──▶  PC serveur  ◀──Wi-Fi chiffré──▶  ESP8266 + composants
                       (le cerveau)                     (les bras et les yeux de la porte)
                           │
                           ▼
                 Dashboard dans le navigateur
```

| Morceau | Rôle | Analogie |
|---|---|---|
| **Le PC serveur** | Regarde la caméra, reconnaît les visages, décide quoi faire, garde l'historique, affiche le dashboard | Le cerveau |
| **L'ESP8266** | Une petite carte électronique : allume les LED, fait tourner le servo, lit les capteurs | Les mains et les capteurs |
| **Le dashboard** | Une page web, ouverte sur le PC, qui montre tout et permet de commander | L'écran de contrôle |

## Ce qui se passe quand quelqu'un arrive

| Temps | Visage connu | Visage inconnu (seul) |
|---|---|---|
| 0 s | LED verte, « Bienvenue Sacha » | LED rouge, « ACCES REFUSE », photo enregistrée |
| 3 s | — | Le PC dit : « Personne inconnue. Si vous ne vous éloignez pas de la zone, nous ouvrirons le feu. » |
| 11 s | — | Si la personne est toujours là **et** que le système est armé : l'arbalète tire |

Si un membre est dans l'image à côté de l'inconnu, la porte reste verte : pas d'avertissement, pas de tir.

Le système démarre toujours **désarmé** : il faut cliquer sur « Armer » dans le dashboard pour qu'il puisse tirer.

## Comment la reconnaissance faciale marche

1. **Trouver les visages** (modèle YuNet) : dans chaque image de la caméra, le programme repère où sont les visages.
2. **Transformer un visage en empreinte** (modèle SFace) : chaque visage devient une liste de 128 nombres, une sorte d'« empreinte » du visage. Deux photos de la même personne donnent des empreintes proches.
3. **Comparer** : l'empreinte est comparée à celles des photos enregistrées (10 par personne). Le score va de 0 (aucune ressemblance) à 1 (identique).
4. **Décider** : on prend la moyenne des 3 photos qui ressemblent le plus. Au-dessus de **0,45**, c'est un membre ; en dessous, c'est un inconnu.
5. **Ne pas se laisser piéger par une image** : le verdict doit tenir sur environ 0,6 seconde (70 % des images d'accord) avant de compter.

Tout ça prend moins de 30 millisecondes par image (le sujet demande moins de 100).

**Limite connue :** une photo d'un membre montrée sur un téléphone est reconnue comme ce membre. Le système compare des apparences, il ne vérifie pas que la personne est vivante.

## Comment le PC et l'ESP se parlent

Ils utilisent **MQTT**, un système de messages fait pour les objets connectés. Un programme central, le **broker** (Mosquitto), sert de bureau de poste : chacun dépose ses messages dans des « boîtes » (des sujets), et ceux qui sont abonnés les reçoivent.

| Boîte (sujet) | Qui écrit | Contenu |
|---|---|---|
| `sentinel/door/led` | le PC | `green`, `red` ou `idle` (éteint) |
| `sentinel/door/fire` | le PC | un numéro de tir : l'ESP fait tirer l'arbalète |
| `sentinel/door/climate` | l'ESP | température, humidité et gaz, toutes les 2 s |
| `sentinel/door/status` | l'ESP | `online` ; le broker écrit `offline` tout seul si l'ESP disparaît |

**La sécurité de la liaison :**
- tout est **chiffré** (TLS, le même principe que le cadenas des sites en https) ;
- l'ESP vérifie qu'il parle au **vrai** PC grâce à un certificat ;
- chaque appareil a **son propre mot de passe**, et l'ESP n'a le droit que de lire ses ordres et d'envoyer ses mesures, jamais de donner des ordres ;
- le dashboard n'est visible que depuis le PC lui-même ;
- les mots de passe et certificats sont générés à l'installation et ne vont jamais sur GitHub.

## Les alertes environnement

- **Gaz** : le programme apprend la valeur habituelle de la pièce (sur 10 minutes). Si le gaz monte nettement au-dessus, c'est une fuite : bandeau rouge sur le dashboard et « Alerte. Fuite de gaz détectée » à voix haute.
- **Surchauffe** : au-delà de 45 °C.
- Un autre programme peut aussi signaler une alerte en envoyant un message à l'adresse `POST /api/v1/alerts` (c'est l'exemple donné dans le sujet).

## Le câblage de l'ESP

| Broche de l'ESP | Composant |
|---|---|
| VU | 5V vers la ligne + de la breadboard (sur cette carte, VIN ne donne rien en USB) |
| G | masse, vers la ligne − |
| D0 | LED rouge (avec une résistance de 330 Ω) |
| D8 | LED verte (avec une résistance de 330 Ω) |
| D1 | capteur température/humidité DHT11 (alimenté par la broche 3V) |
| A0 | capteur de gaz, à travers 2 résistances de 100K (sa sortie peut monter à 5V, l'ESP n'accepte que 3,3V) |
| D2 | servo de l'arbalète (jamais D4 : cette broche s'agite au démarrage) |

## Qui fait quoi dans le code

| Fichier | Ce qu'il fait |
|---|---|
| `install.bat` | Installe tout, une seule fois |
| `start.bat` | Lance tout et ouvre le dashboard |
| `firmware/door-node/door-node.ino` | Le programme de l'ESP |
| `server/sentinel/app.py` | Le programme principal du PC : caméra, dashboard, liens entre tout le reste |
| `server/sentinel/face_id.py` | Trouve et reconnaît les visages |
| `server/sentinel/enroll.py` | Enregistre les photos d'un nouveau visage |
| `server/sentinel/guard.py` | Les règles de la porte : vert, rouge, avertissement, tir |
| `server/sentinel/door.py` | Applique ces règles et envoie les ordres à l'ESP ; lisse le verdict sur plusieurs images |
| `server/sentinel/mqtt.py` | Lance le broker et parle avec l'ESP |
| `server/sentinel/alerts.py` | Détecte les fuites de gaz et la surchauffe |
| `server/sentinel/store.py` | Garde l'historique (passages, mesures, alertes) dans une petite base de données |
| `server/sentinel/setup.py` | Génère les certificats, les mots de passe et les réglages de l'ESP |
| `server/sentinel/static/index.html` | La page du dashboard |
| `server/tests/` | 74 tests automatiques qui vérifient que les règles marchent |

## Les choix assumés

- **Pas de Docker** : tout tourne directement sur le PC, plus simple à installer et à dépanner pendant le workshop.
- **Pas d'IA prédictive sur les capteurs** : le kit de capteurs du sujet n'a pas été fourni ; le prof a validé un projet plus libre.
- **Un membre accompagne un inconnu = vert** : choix de l'équipe, pour éviter de tirer sur un invité accompagné.
- **Le tir part à 11 s, pas à 3 s** : il faut laisser le temps d'entendre l'avertissement (environ 7 s) et de reculer.
