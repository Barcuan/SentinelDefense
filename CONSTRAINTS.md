# Constraints

Dernière revue : 2026-10-05 par @sacha.bonnel — à revoir quand la stack est choisie.

Contexte : workshop Sentinel-X, rendu jeudi 2026-10-08. Firmware ESP8266, lien chiffré,
IA Python (webcam + prédictif), dashboard. Le bar est volontairement léger : 4 jours.

## Floor (toujours appliqué, bloquant)

- Pas de secrets dans le code : clés Wi-Fi, MQTT, chiffrement → `.env` (déjà ignoré par git) ou `secrets.h` non commité
- Pas de nouveaux commentaires de suppression : `# noqa`, `# type: ignore`, `eslint-disable`, `@ts-ignore`
- Pas de stub non implémenté : `raise NotImplementedError`, `pass` à la place d'une logique, `except: pass` / `catch {}` vides
- Pas de test sauté ou supprimé sans raison dans le message de commit
- Ce fichier ne s'affaiblit pas pour faire passer un changement

Raison : ce sont les raccourcis qu'un agent prend pour passer au vert ; ils coûtent zéro outil à vérifier (`git diff`).

## Appliqué avec des chiffres

| Dimension | Règle | Vérifié par | Tourne à | Mode | Pourquoi |
|-----------|-------|-------------|----------|------|----------|
| Secrets | 0 finding | `gitleaks detect --redact --no-banner` | chaque modif + avant commit | **bloque** | Le lien chiffré impose des clés ; une clé commitée dans un dépôt partagé à 3 est compromise. `--redact` obligatoire pour ne pas recopier la clé dans un transcript. |
| Lint Python | 0 erreur | `ruff check .` | chaque modif | avertit | Attrape les bugs bêtes (variables non définies, imports morts) en < 1 s. |
| Types Python | 0 erreur | `mypy .` | fin de tâche | avertit | Les données capteurs passent entre modules ; une erreur de type = un dashboard vide en démo. |
| Dépendances | rien en high ou au-dessus | `osv-scanner scan source -r .` | fin de tâche | avertit | Seul avis externe du lot (base de vulnérabilités publique) ; sous high c'est surtout du bruit. |

Budget : < 5 s par modif, < 90 s en fin de tâche (défaut, pas de CI prévue).

**Statut : outils pas encore installés** (choix d'équipe : on installe une fois l'idée et la stack choisies).
À installer à ce moment-là :

```bash
pip install ruff mypy
```

gitleaks et osv-scanner : binaires depuis leurs releases GitHub, ou `winget install gitleaks`.

Tant qu'ils ne sont pas installés, seul le Floor est réellement appliqué (revue du diff).

## Mesuré, pas encore appliqué

| Métrique | Aujourd'hui | Direction |
|----------|-------------|-----------|
| — | aucune (pas de code) | à mesurer après le premier code |

## Hors périmètre (et pourquoi)

- Couverture de tests : coût trop élevé sur 4 jours, choix d'équipe.
- Accessibilité / performance web : nécessitent une URL qui tourne ; à reconsidérer si le dashboard est servi en local.
- Firmware ESP8266 (C++) : pas d'outil retenu ; seul le Floor (secrets surtout) s'applique.

## Exceptions

| ID | Règle | Chemin | Raison | Responsable | Expire |
|----|-------|--------|--------|-------------|--------|
| — | | | | | |
