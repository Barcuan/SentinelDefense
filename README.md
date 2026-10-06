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

## Lancer le dashboard

Depuis le dossier `server` :

```powershell
cd server
python -m sentinel.app
```

Puis ouvrez **http://localhost:8000** dans le navigateur du même PC. On y trouve :

- la caméra en direct : cadre vert + prénom si le visage est connu, rouge + « inconnu » sinon ;
- **Enregistrer un visage** : tapez un prénom, cliquez sur Enregistrer, restez seul face à la caméra et bougez un peu la tête. 10 photos sont prises, puis le visage est appris ;
- **Visages enregistrés** : la liste, avec un bouton pour supprimer quelqu'un ;
- **Réglage de la reconnaissance** : le curseur du seuil. Montez-le si un inconnu est pris pour un membre, baissez-le si un membre reste « inconnu ». Le score de la personne devant la caméra s'affiche en direct à côté.

Ctrl+C dans le terminal pour arrêter. Le dashboard n'est accessible que depuis ce PC.

Si c'est la webcam intégrée du PC qui s'affiche au lieu de la C270, arrêtez, puis relancez avec la caméra 1 :

```powershell
$env:SENTINEL_CAMERA=1
python -m sentinel.app
```

Les photos et les empreintes des visages restent dans `data/`, qui n'est **jamais** envoyé sur GitHub.

Sans dashboard, en ligne de commande : `python -m sentinel.enroll --capture Sacha` pour enregistrer, `python sentinel/face_id.py` pour l'aperçu.

## L'ESP8266

Programmé avec **Arduino IDE** (carte « NodeMCU 1.0 (ESP-12E Module) »). Câblage dans [SPEC.md](SPEC.md#câblage-un-seul-esp). Le programme définitif arrivera dans `firmware/door-node/`.

## Vérifications avant chaque commit

```powershell
pytest
ruff check .
mypy server/sentinel
```
