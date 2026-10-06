# Sentinel-X : la porte gardée

Une webcam reconnaît les visages devant la porte. Visage connu : LED verte et « Bienvenue ». Visage inconnu : LED rouge, alarme et capture ; s'il reste inconnu 3 s et que le système est armé, le servo déclenche l'arbalète imprimée en 3D. Le dashboard montre la caméra, les passages, la température, l'humidité et le gaz.

Détails : [SPEC.md](SPEC.md) (ce qu'on construit, câblage), [tasks/plan.md](tasks/plan.md) (avancement), [CONSTRAINTS.md](CONSTRAINTS.md) (règles de qualité).

## Installer et lancer en 3 étapes

Sur le **PC serveur** : celui où sont branchées la webcam C270 et l'ESP8266 (Windows, avec Git et **Python 3.14** installés, « Add python.exe to PATH » coché).

### 0. Activer le partage de connexion

**Paramètres → Réseau et Internet → Point d'accès sans fil mobile** : activez-le et notez son **nom** et son **mot de passe**. C'est le Wi-Fi sur lequel l'ESP se connecte (le Wi-Fi de l'école bloque souvent les appareils entre eux).

### 1. Installer (une seule fois)

```powershell
git clone https://github.com/Barcuan/SentinelDefense.git
```

Puis double-cliquez sur **`install.bat`**. Il installe tout (dépendances, modèles, Mosquitto), ouvre une fenêtre administrateur pour le pare-feu (acceptez), puis demande **le nom et le mot de passe du partage de connexion**. Il génère alors les certificats, les mots de passe et le fichier de réglages de l'ESP. Rien de tout ça ne part sur GitHub.

### 2. Téléverser l'ESP (une seule fois)

Dans **Arduino IDE** :

1. **Outils → Gérer les bibliothèques** : installez **PubSubClient** (Nick O'Leary) et **DHT sensor library** (Adafruit, acceptez « Install all »).
2. **Fichier → Ouvrir** : `firmware\door-node\door-node.ino` (le fichier `secrets.h` à côté a été généré par l'installation).
3. **Outils → Carte** : « NodeMCU 1.0 (ESP-12E Module) », **Outils → Port** : le COM de l'ESP, puis **Téléverser**.

### 3. Lancer

Double-cliquez sur **`start.bat`**. Tout démarre (broker chiffré, caméra, logique de la porte, liaison avec l'ESP) et le navigateur s'ouvre sur **http://localhost:8000** :

- **Surveillance** : caméra en direct, verdict en gros, bouton **Armer**, historique des passages avec les captures des inconnus ;
- **Capteurs** : température, humidité et gaz, avec des courbes sur 15 min à 24 h ;
- **Visages** : enregistrer un visage (prénom + bouton, 10 photos), supprimer, régler le seuil de reconnaissance.

En haut à droite, trois voyants : **caméra**, **liaison chiffrée**, **ESP**. Tous doivent être verts.

## Checklist de l'essai réel

1. `start.bat` lancé, le partage de connexion activé, l'ESP branché : le voyant **ESP** passe au vert en moins de 30 s.
2. Onglet **Capteurs** : une mesure toutes les 2 s. Soufflez sur le DHT11 : l'humidité monte. Gel hydroalcoolique près du capteur de gaz : le gaz monte.
3. Onglet **Visages** : enregistrez les 3 membres.
4. Un membre devant la caméra : **LED verte** + « Bienvenue <prénom> ». Un inconnu : **LED rouge** + alarme + capture dans l'historique.
5. **Désarmé** : un inconnu qui reste ne déclenche **pas** le servo. **Armé** (sans arbalète montée la première fois) : après 3 s, un aller-retour du servo, « TIR » dans l'historique.
6. Débranchez l'ESP : voyant **ESP hors ligne** en moins de 5 s. Coupez `start.bat` : les LED s'éteignent en 2 s.

## Dépannage

| Symptôme | Que faire |
|---|---|
| Voyant **caméra** rouge, ou c'est la webcam intégrée qui s'affiche | Dans `start.bat`, enlevez `rem` devant `set SENTINEL_CAMERA=1`, relancez |
| Voyant **liaison** rouge « non configurée » | Relancez `install.bat` |
| Voyant **ESP** reste rouge | Moniteur série d'Arduino IDE (115200) avec l'ESP branché : il affiche l'étape qui bloque (Wi-Fi, TLS, mot de passe). Vérifiez que le partage de connexion est actif et porte le nom donné à l'installation |
| Le nom ou le mot de passe du Wi-Fi a changé | `python -m sentinel.setup --force` depuis le dossier `server` (avec le venv activé), puis re-téléversez l'ESP |
| L'ESP redémarre quand le servo tire | Port USB directement sur le PC (pas un hub) ; sinon condensateur 470 µF entre + et − |
| Un membre reste « inconnu », ou un inconnu est reconnu | Onglet **Visages** : réglez le seuil, ou ré-enregistrez la personne sous l'éclairage de la salle |

Une photo d'un membre montrée sur un téléphone est reconnue comme ce membre : c'est une limite connue de la reconnaissance faciale simple (pas de détection du vivant).

## Pour les développeurs

```powershell
.venv\Scripts\activate
pytest
ruff check .
mypy server/sentinel
```

Le firmware se compile aussi sans carte : `arduino-cli compile --fqbn esp8266:esp8266:nodemcuv2 firmware/door-node` (avec un `secrets.h` généré).
