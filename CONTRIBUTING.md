# Contribuer a OpenDrop

Merci de l'interet porte au projet. Ce document decrit comment proposer une
correction ou une fonctionnalite.

## Prérequis

- Python **3.10+** (developpe et teste en 3.12)
- **.NET 8 SDK** si vous touchez a l'application bureau (Avalonia, Windows
  ou Linux)
- `git`

## Mise en place

```powershell
git clone https://github.com/lucas31Zz/opendrop.git
cd opendrop
pip install -e .
```

## Tests

Les suites sont maison (aucun framework externe), a lancer depuis la racine.
**Tout doit passer avant une PR** :

```powershell
python -m tests.test_security     # 36
python -m tests.test_routes       # 44
python -m tests.test_paths        # 43
python -m tests.test_quota        # 40
python -m tests.test_sessions     # 34
python -m tests.test_tls          # 15
python -m tests.test_server       # 11
python -m tests.test_beta         # 64
```

- Chaque suite sort avec un code d'erreur non nul en cas d'echec.
- `python -m tests.test_beta --large` (76) est plus lent : a lancer avant de
  fusionner des changements qui touchent le protocole ou le multipart.
- Les tests travaillent **toujours** dans un dossier temporaire cree par
  `tests/conftest.py` : aucun fichier utilisateur n'est lu, ecrit ou
  supprime. Ne jamais briser cette isolation.

## Conventions

- **Code et commentaires en francais, sans accents** (l'encodage reste simple
  partout). Le markdown (README, docs) accepte les accents.
- **Pas de refactoring hors perimetre** : si un correctif touche 3 lignes, il
  reste sur 3 lignes.
- Aucune nouvelle dependance sans en discuter d'abord (issues).
- Aucun secret, cle, certificat ou chemin personnel dans le depot
  (`config.json`, `session.json`, `certs/` sont hors depot).
- Si une suite gagne ou perd des verifications, mettez a jour les comptes du
  README (section *Tests*) et le `CHANGELOG.md`.

## Commits et pull requests

- Premiere ligne courte a l'impératif (« Ajoute le quota... », « Corrige... »),
  corps si le pourquoi n'est pas evident.
- Decrire le **pourquoi** du changement, pas seulement le quoi.
- Lister les suites lancees dans la description de la PR.
- Interface (web/bureau) : joindre une capture avant/apres.
- Les suites CI (tests + build bureau) doivent passer.

## Issues

- **Bug** : systeme d'exploitation, version Python, etapes pour reproduire,
  comportement attendu vs observe.
- **Fonctionnalite** : decrir l'usage reel avant la solution proposee.

## Securite

Ne publiez pas une faille en issue publique : voir
[SECURITY.md](SECURITY.md) (formulaire prive GitHub ou e-mail).
