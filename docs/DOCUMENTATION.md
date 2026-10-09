# Sentinel-X, documentation du projet

**Équipe** Killian Henriet, Sacha BONNEL et François NOWICKI

**Cadre** Workshop EPSI, Mastère 1, octobre 2026

**Code source** github.com/Barcuan/SentinelDefense

---

## 1. Présentation du projet

### Le contexte

Le sujet place l'équipe en 2050, au service de la société AetherCorp. Ses micro-centrales énergétiques, installées dans des zones isolées, subissent trois menaces en même temps. Il y a des intrusions physiques, des risques environnementaux comme les fuites de gaz ou les surchauffes, et des cyberattaques. Comme il est impossible d'y laisser du personnel en permanence, AetherCorp demande un boîtier de surveillance autonome relié à un poste de commandement local.

### Notre réponse

Nous avons conçu Sentinel-X, le module de contrôle d'accès de l'avant-poste. Il garde l'entrée du site et répond aux trois menaces.

| Menace du sujet | Ce que fait Sentinel-X |
|---|---|
| Intrusion physique | Reconnaissance faciale à l'entrée, voyant vert ou rouge, avertissement vocal, photo de l'intrus et tir de dissuasion avec une arbalète imprimée en 3D |
| Fuite de gaz, surchauffe | Mesure du gaz, de la température et de l'humidité, avec une alerte automatique |
| Cyberattaque | Liaison chiffrée entre le boîtier et le serveur, un compte par appareil, des droits limités et un journal des tentatives refusées |

Le rôle de serveur est tenu par un ordinateur portable, sur lequel la webcam est branchée en USB. Le boîtier contient la carte ESP8266 et ses composants.

---

## 2. Ce que fait Sentinel-X

### Quand quelqu'un se présente à la porte

| Temps | Membre de l'équipe reconnu | Personne inconnue, seule devant la caméra |
|---|---|---|
| 0 s | LED verte et message « Bienvenue » avec son prénom | LED rouge, message « ACCÈS REFUSÉ » et photo enregistrée dans l'historique |
| 3 s | Rien de plus | Le PC annonce à voix haute « Personne inconnue. Si vous ne vous éloignez pas de la zone, nous ouvrirons le feu. » |
| 11 s | Rien de plus | Si la personne est toujours là et que le système est armé, l'arbalète tire une balle en mousse |

Quelques règles complètent ce scénario.

- Le système démarre toujours désarmé. Il faut l'armer depuis le dashboard pour qu'il puisse tirer.
- Si un membre de l'équipe est dans l'image à côté d'un inconnu, la porte reste verte. Nous considérons qu'il accompagne un invité, donc il n'y a ni avertissement ni tir.
- Deux tirs sont toujours séparés d'au moins 10 secondes.
- Le tir part à 11 secondes et non à 3, pour laisser à la personne le temps d'entendre l'avertissement (la phrase dure environ 7 secondes) et de partir.

### Les alertes environnement

Le capteur de gaz est comparé à l'air habituel de la pièce, mesuré sur les 10 dernières minutes. Quand la valeur monte nettement au-dessus, c'est une fuite. Un bandeau rouge apparaît sur le dashboard et le PC annonce « Alerte. Fuite de gaz détectée. » Une température au-delà de 45 °C déclenche de la même façon une alerte de surchauffe.

---

## 3. Architecture générale

Le système repose sur trois blocs.

```
   Webcam C270                      PC serveur                         ESP8266 + composants
   (les yeux)                       (le cerveau)                       (les mains)
 ┌─────────────┐   USB   ┌──────────────────────────────┐  Wi-Fi   ┌────────────────────────┐
 │  C270 HD    │ ──────▶ │  IA de vision                │ chiffré  │  LED verte et rouge    │
 └─────────────┘         │  Logique de la porte         │ ◀──────▶ │  Température, humidité │
                         │  Broker MQTT (Mosquitto)     │   TLS    │  Capteur de gaz        │
                         │  Base de données SQLite      │          │  Servo de l'arbalète   │
                         │  Dashboard web               │          └────────────────────────┘
                         └──────────────────────────────┘
                                        │
                                        ▼
                         Navigateur du PC serveur (localhost)
```

| Bloc | Rôle |
|---|---|
| Webcam C270 | Filme l'entrée. Elle est branchée en USB sur le PC serveur, comme l'impose le sujet. |
| PC serveur | Analyse les images, décide quoi faire, garde l'historique, fait tourner le broker MQTT et affiche le dashboard. |
| ESP8266 | Allume les LED, actionne le servo et envoie les mesures des capteurs. |
| Dashboard | Page web ouverte sur le PC serveur. Elle montre tout et permet de commander le système. |

### Le réseau

L'ESP8266 se connecte au partage de connexion Wi-Fi du PC serveur. Ce réseau dédié à notre table évite les problèmes du Wi-Fi de l'école, qui isole souvent les appareils entre eux.

| Élément | Adresse |
|---|---|
| Réseau de table | 192.168.137.0/24, créé par le point d'accès mobile de Windows |
| PC serveur | 192.168.137.1, adresse fixe sur ce réseau |
| ESP8266 | Adresse attribuée automatiquement par le PC, du type 192.168.137.x |
| Broker MQTT | Port 8883 du PC serveur, ouvert dans le pare-feu uniquement pour le réseau de table |
| Dashboard | Port 8000 du PC serveur, accessible uniquement depuis le PC lui-même |

---

## 4. Le matériel et le câblage

### Le matériel utilisé

| Composant | Usage |
|---|---|
| Carte ESP8266 LoLin V3 (puce USB CH340) | Pilote tous les composants du boîtier |
| Webcam Logitech C270 HD | Filme l'entrée pour la reconnaissance faciale |
| 2 LED, verte et rouge | Indiquent si l'accès est autorisé ou refusé |
| Module DHT11 (KY-015) | Mesure la température et l'humidité |
| Capteur de gaz « Flying Fish » | Mesure la présence de gaz |
| Servo SG90 | Déclenche l'arbalète imprimée en 3D |
| Breadboards, résistances 330 Ω, 10 kΩ et 100 kΩ, fils | Montage et liaisons |

### Le câblage de l'ESP8266

| Broche | Composant | Détail |
|---|---|---|
| VU | Ligne + de la breadboard | Fournit le 5 V de l'USB. Sur cette carte, la broche VIN ne donne rien quand elle est alimentée en USB. |
| G | Ligne − de la breadboard | Masse commune à tous les composants |
| D0 | LED rouge | Avec une résistance de 330 Ω vers la masse |
| D8 | LED verte | Avec une résistance de 330 Ω vers la masse |
| D1 | Signal du DHT11 | Le capteur est alimenté par la broche 3V de l'ESP |
| A0 | Sortie AO du capteur de gaz | À travers deux résistances de 100 kΩ en série |
| D2 | Signal du servo | Le servo est alimenté par la ligne + |

### Pourquoi deux résistances pour le capteur de gaz

Le capteur de gaz fonctionne en 5 V et sa sortie peut donc monter jusqu'à 5 V. La broche A0 de la carte accepte au maximum 3,3 V. Des résistances placées à la suite se partagent la tension en proportion de leur valeur. La carte contient déjà, derrière A0, deux résistances de 220 kΩ et 100 kΩ vers la masse, soit 320 kΩ. En ajoutant 200 kΩ devant, la broche reçoit au plus 5 V × 320 / 520, soit environ 3,1 V. Nous avons obtenu ces 200 kΩ avec deux résistances de 100 kΩ placées en série.

### Pourquoi le servo n'est jamais sur D4

Au démarrage de la carte, avant même le lancement de notre programme, la broche D4 envoie une rafale d'impulsions. C'est aussi pour cela que la LED bleue de la carte clignote au branchement. Un servo se pilote justement par impulsions. Branché sur D4, il bougerait tout seul à chaque démarrage et risquerait de déclencher l'arbalète. La broche D2 reste silencieuse au démarrage, et notre programme place le servo en position de repos avant toute autre action.

### Méthode de montage

Nous avons branché et testé chaque composant seul, avec un petit programme de test, avant de les réunir. Cette méthode nous a permis de trouver rapidement les pièges du montage, comme la broche VIN qui ne fournit pas de 5 V sur cette carte.

---

## 5. Le programme de l'ESP8266

Le programme `firmware/door-node/door-node.ino` est écrit en C++ et téléversé avec Arduino IDE. Il s'appuie sur deux bibliothèques, PubSubClient pour MQTT et DHT sensor library pour le capteur de température.

Au démarrage, il place le servo au repos, éteint les LED, se connecte au Wi-Fi puis au broker en TLS. Ensuite, en boucle, il fait trois choses.

1. Il écoute les ordres du serveur. `green`, `red` ou `idle` pilotent les LED, et un numéro de tir déclenche un aller-retour du servo. Un numéro déjà reçu est ignoré, pour ne jamais tirer deux fois sur le même ordre.
2. Toutes les deux secondes, il envoie la température, l'humidité et la valeur du gaz.
3. Il surveille la liaison. S'il perd le broker plus de deux secondes, il éteint les LED. Sans liaison, aucun ordre de tir ne peut lui parvenir.

Les réglages propres à chaque installation (nom et mot de passe du Wi-Fi, adresse du broker, compte MQTT et certificat) sont dans le fichier `secrets.h`. Ce fichier est généré à l'installation et n'est jamais envoyé sur GitHub.

---

## 6. Le serveur

Le serveur est écrit en Python. Un seul programme, lancé par `start.bat`, démarre tout le reste.

| Partie | Fichier | Rôle |
|---|---|---|
| Programme principal | `server/sentinel/app.py` | Lance la caméra, le broker et le dashboard, et relie tous les modules entre eux |
| Vision | `server/sentinel/face_id.py` | Détecte et reconnaît les visages |
| Enregistrement des visages | `server/sentinel/enroll.py` | Prend les photos d'un nouveau membre et apprend son visage |
| Règles de la porte | `server/sentinel/guard.py` | Décide du vert, du rouge, de l'avertissement et du tir |
| Porte | `server/sentinel/door.py` | Applique ces règles, envoie les ordres à l'ESP et lisse le verdict sur plusieurs images |
| Liaison MQTT | `server/sentinel/mqtt.py` | Lance Mosquitto et échange les messages avec l'ESP |
| Alertes | `server/sentinel/alerts.py` | Détecte les fuites de gaz et les surchauffes |
| Historique | `server/sentinel/store.py` | Enregistre les passages, les mesures et les alertes dans une base SQLite |
| Supervision | `server/sentinel/monitor.py` | Mesure la charge du PC et lit le journal du broker |
| Installation | `server/sentinel/setup.py` | Génère les certificats, les mots de passe et les réglages de l'ESP |
| Dashboard | `server/sentinel/static/index.html` | La page web |

Les règles de la porte sont écrites comme une fonction pure, sans caméra ni réseau. Nous pouvons ainsi vérifier chaque règle de tir par des tests automatiques, sans matériel.

---

## 7. L'intelligence artificielle de vision

### Comment un visage est reconnu

Nous utilisons deux modèles fournis par OpenCV, qui tournent entièrement sur le PC serveur. Aucune image ne quitte la machine.

1. **Détecter.** Le modèle YuNet repère où se trouvent les visages dans chaque image.
2. **Encoder.** Le modèle SFace transforme chaque visage en une liste de 128 nombres, son empreinte. Deux photos de la même personne donnent des empreintes proches.
3. **Comparer.** L'empreinte est comparée aux 10 photos enregistrées de chaque membre. Le score va de 0, aucune ressemblance, à 1, identique. Le score d'un membre est la moyenne de ses 3 photos les plus ressemblantes.
4. **Décider.** Au-dessus de 0,45, c'est un membre. En dessous, c'est un inconnu.
5. **Confirmer.** Un verdict ne compte que s'il tient sur environ 0,6 seconde, avec au moins 70 % des images d'accord.

Les images de la webcam sont réduites à 640 × 480 avant l'analyse. Le traitement complet prend moins de 30 millisecondes par image, alors que le sujet demande moins de 100.

### Enregistrer un membre

Dans l'onglet Visages du dashboard, on tape un prénom puis on clique sur Enregistrer. Le système prend 10 photos en quelques secondes pendant que la personne tourne légèrement la tête, puis il apprend le visage sans redémarrer. Les photos restent sur le PC serveur et ne sont jamais envoyées sur GitHub.

### Rendre la reconnaissance fiable

Lors de nos essais, des personnes non enregistrées étaient parfois reconnues comme un membre. Plutôt que de corriger au hasard, nous avons mesuré les scores sur nos propres données.

| Ce que nous avons mesuré | Ce que nous avons corrigé |
|---|---|
| Les vraies reconnaissances avaient un score moyen d'environ 0,63, les fausses étaient entre 0,36 et 0,45, juste au-dessus du seuil par défaut d'OpenCV (0,363) | Seuil relevé à 0,45, toujours réglable depuis le dashboard |
| Une seule photo ressemblante suffisait à reconnaître quelqu'un | Score calculé sur la moyenne des 3 photos les plus proches |
| Le verdict changeait d'une image à l'autre, ce qui avait créé 263 passages pour une seule session | Vote sur 0,6 seconde avant de valider un verdict |
| Les visages lointains donnaient des scores au hasard | Les visages de moins de 70 pixels de large sont ignorés et marqués « approchez » |

---

## 8. La communication entre le PC et l'ESP

Le PC et l'ESP communiquent avec MQTT, un protocole conçu pour les objets connectés. Le broker Mosquitto, sur le PC serveur, joue le rôle d'un bureau de poste. Chaque appareil dépose ses messages dans des sujets, et ceux qui sont abonnés à un sujet les reçoivent.

| Sujet | Émetteur | Contenu |
|---|---|---|
| `sentinel/door/led` | PC | `green`, `red` ou `idle` (LED éteintes) |
| `sentinel/door/fire` | PC | Un numéro de tir |
| `sentinel/door/climate` | ESP | Température, humidité et gaz, toutes les deux secondes |
| `sentinel/door/status` | ESP | `online`, et `offline` publié automatiquement par le broker si l'ESP disparaît |

Le serveur expose aussi une API web. La route `POST /api/v1/alerts`, citée en exemple par le sujet, permet à un autre programme de signaler une alerte qui s'affiche alors sur le dashboard.

---

## 9. La cybersécurité

### Matrice de sécurité

| Protection | Attaque visée | Vérification |
|---|---|---|
| Chiffrement TLS 1.2 | Capture du trafic Wi-Fi avec Wireshark | Le contenu des messages et les mots de passe sont illisibles. Seuls les adresses et la taille des paquets restent visibles. |
| Certificat vérifié | Faux broker (attaque de l'homme du milieu) | Un client qui ne connaît pas notre autorité de certification refuse le broker. L'ESP fait la même vérification. |
| Un compte par appareil | Connexion pirate au broker | Une connexion sans mot de passe ou avec un mauvais mot de passe est refusée |
| Droits limités | Vol du mot de passe de l'ESP | Le compte de l'ESP ne peut pas envoyer d'ordre. Un essai d'ordre de LED avec ce compte est bloqué par le broker. |
| Dashboard local | Prise de contrôle à distance | Le serveur web n'écoute que sur 127.0.0.1, l'adresse interne du PC |
| Pare-feu | Accès depuis le Wi-Fi de l'école | Le port 8883 n'est ouvert qu'au réseau de table 192.168.137.0/24 |
| Secrets hors GitHub | Fuite du code source | Aucune clé ni aucun mot de passe dans le dépôt, et des clés uniques générées à chaque installation |

### Le fonctionnement du certificat

À l'installation, le programme crée une autorité de certification, signe avec elle le certificat du broker, puis détruit la clé de cette autorité. Plus personne ne peut ensuite signer un certificat que l'ESP accepterait. Un attaquant qui se ferait passer pour le PC serveur ne pourrait pas présenter de certificat valide, et l'ESP refuserait de lui parler. Le certificat lui-même n'est pas secret. Ce qui doit rester protégé, c'est la clé privée du broker, qui ne quitte jamais le PC serveur.

Les certificats utilisent la courbe elliptique P-256, plus légère que RSA pour la petite mémoire de l'ESP8266. L'ESP connaît la date de génération du certificat et peut ainsi le valider sans accès à Internet.

### Le comportement en cas d'attaque

Le système ne peut pas empêcher un déni de service, comme la saturation du Wi-Fi ou la déconnexion de l'ESP. En revanche, il échoue du côté sûr. Sans liaison, l'ESP éteint ses LED et ne peut recevoir aucun ordre de tir. On peut nous couper, mais pas nous détourner.

### Les limites connues

- Avec le mot de passe de l'ESP, un attaquant pourrait envoyer de fausses mesures, sans pouvoir rien actionner.
- Le dashboard n'a pas de mot de passe. Il faut donc verrouiller la session Windows du PC serveur.
- Le mot de passe du partage de connexion est la première barrière et doit rester secret.

---

## 10. Le dashboard

Le dashboard s'ouvre automatiquement au lancement et comporte quatre onglets.

| Onglet | Contenu |
|---|---|
| Surveillance | Caméra en direct avec les visages encadrés, verdict en grand, bouton pour armer le système, panneau de commande (LED et tir de test), historique des passages avec la photo de chaque inconnu |
| Capteurs | Température, humidité et gaz en direct, courbes sur 15 minutes à 24 heures, historique des alertes |
| Visages | Enregistrement d'un membre, liste des membres, réglage du seuil de reconnaissance avec le score en direct |
| Serveur | Charge du processeur et de la mémoire, messages MQTT échangés, journal du broker avec les connexions refusées en rouge |

En haut de la page, trois voyants indiquent l'état de la caméra, de la liaison chiffrée et de l'ESP.

---

## 11. Installation et lancement

L'installation se fait sur le PC serveur, sous Windows, avec Git et Python 3.14.

1. Activer le partage de connexion de Windows, en bande 2,4 GHz car l'ESP8266 ne capte pas le 5 GHz.
2. Récupérer le code avec `git clone`, puis lancer `install.bat`. Il installe les dépendances, les modèles de reconnaissance et Mosquitto, ouvre le port du broker dans le pare-feu, puis demande le nom et le mot de passe du partage de connexion pour générer les certificats et les réglages de l'ESP.
3. Téléverser une fois `firmware/door-node/door-node.ino` sur l'ESP avec Arduino IDE.
4. Lancer `start.bat`. Tout démarre et le dashboard s'ouvre dans le navigateur.

---

## 12. Tests et vérifications

### Tests automatiques

Le projet compte 81 tests automatiques, lancés avec `pytest`. Ils vérifient notamment toutes les règles de tir (jamais de tir sur un membre, jamais de tir désarmé, délai entre deux tirs), la reconnaissance et le lissage du verdict, les alertes gaz et surchauffe, l'historique, la génération des certificats et la lecture du journal du broker. Le code est aussi vérifié par les outils `ruff` et `mypy`, sans aucune exception désactivée.

### Essais réels

- Chaque composant de l'ESP a été testé seul, puis le montage complet.
- Le programme de l'ESP a été compilé pour notre carte avant d'être téléversé.
- La liaison chiffrée a été testée avec le vrai broker et un faux ESP utilisant les mêmes identifiants.

### Vérifications de sécurité

Nous avons vérifié la résistance du broker avec les outils fournis par Mosquitto.

| Essai | Résultat |
|---|---|
| Connexion avec le bon compte et le bon certificat | Acceptée |
| Connexion avec un mauvais mot de passe | Refusée, « not authorised » |
| Connexion sans mot de passe, même avec le certificat public | Refusée, « not authorised » |
| Connexion sans chiffrement TLS | Refusée, erreur de protocole |
| Client qui ne connaît pas notre autorité de certification | Refuse lui-même le broker |
| Ordre de LED envoyé avec le compte de l'ESP | Bloqué par les droits du broker |
| Coupure brutale de l'ESP | Le serveur affiche l'ESP hors ligne en moins de 6 secondes |

Chaque tentative refusée apparaît en direct en rouge dans l'onglet Serveur du dashboard, avec l'adresse de l'appareil qui a essayé.

---

## 13. Nos choix et leurs raisons

| Choix | Raison |
|---|---|
| Pas de Docker | L'installation tient en un double-clic et reste simple à dépanner pendant le workshop |
| Pas d'écran sur le boîtier | Un écran LCD demandait trop de broches de l'ESP. Les messages s'affichent sur le dashboard, plus lisible et plus complet. |
| Avertissement vocal au lieu d'un buzzer | Une phrase claire est plus dissuasive qu'un bip |
| Un seul ESP8266 | Un seul programme et une seule connexion chiffrée à gérer. Le second ESP reste en secours. |
| Un membre accompagné d'un inconnu reste vert | Éviter de viser un invité accompagné |
| Python pour le serveur | Le sujet impose Python pour l'IA, et OpenCV y est disponible directement |

---

## 14. Limites et pistes d'amélioration

- **Détection du vivant.** Une photo d'un membre montrée sur un téléphone est reconnue comme ce membre, car le système compare des apparences. Une parade serait de demander à la personne de tourner la tête, ou d'ajouter un modèle anti-usurpation.
- **Alimentation.** Séparer l'alimentation du servo et du capteur de gaz de celle de l'ESP pour plus de stabilité.
