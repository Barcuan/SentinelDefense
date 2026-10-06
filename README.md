# Sentinel-X : la porte gardée

Une webcam reconnaît les visages devant la porte. Visage connu : LED verte et « Bienvenue ». Visage inconnu : LED rouge, alarme et capture ; s'il reste inconnu 3 s et que le système est armé, le servo déclenche l'arbalète imprimée en 3D. Un dashboard affiche tout.

Détails : [SPEC.md](SPEC.md) (ce qu'on construit), [tasks/plan.md](tasks/plan.md) (avancement), [CONSTRAINTS.md](CONSTRAINTS.md) (règles de qualité).

## Installer sur le PC serveur (Windows)

Le PC serveur est celui où sont branchés la webcam C270 et l'ESP8266. Il faut **Git** et **Python 3.14**.

```powershell
git clone https://github.com/Barcuan/SentinelDefense.git
cd SentinelDefense
python -m venv .venv
.venv\Scripts\activate
pip install -r server/requirements.txt
python server/scripts/get_models.py
pytest
```

`get_models.py` télécharge les deux modèles de reconnaissance (environ 38 Mo). Ils ne sont pas dans le dépôt.

## Enregistrer les visages autorisés

Depuis le dossier `server`, chaque membre se met face à la caméra et lance, avec son prénom :

```powershell
cd server
python -m sentinel.enroll --capture Sacha
```

Le programme prend 10 photos (bougez un peu la tête entre deux photos), puis apprend le visage. Échap pour arrêter avant la fin.

Pour vérifier la reconnaissance en direct (cadre vert + prénom, ou rouge + « inconnu ») :

```powershell
python sentinel/face_id.py
```

Si c'est la webcam intégrée du PC qui s'allume au lieu de la C270, choisissez la caméra 1 :

```powershell
$env:SENTINEL_CAMERA=1
```

Le seuil de reconnaissance se règle de la même façon : `$env:SENTINEL_THRESHOLD=0.4` rend la reconnaissance plus stricte, une valeur plus basse la rend plus tolérante.

Les photos et les empreintes des visages restent dans `data/`, qui n'est **jamais** envoyé sur GitHub.

## L'ESP8266

Programmé avec **Arduino IDE** (carte « NodeMCU 1.0 (ESP-12E Module) »). Câblage dans [SPEC.md](SPEC.md#câblage-un-seul-esp). Le programme définitif arrivera dans `firmware/door-node/`.

## Vérifications avant chaque commit

```powershell
pytest
ruff check .
mypy server/sentinel
```
