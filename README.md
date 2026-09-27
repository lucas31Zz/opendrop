# OpenDrop

> Transfert de fichiers direct sur le reseau local : on lance OpenDrop, on
> scanne le QR code, on envoie. Pas de compte, pas de cloud, pas d'install
> sur le telephone.

[![Tests](https://github.com/lucas31Zz/opendrop/actions/workflows/tests.yml/badge.svg)](https://github.com/lucas31Zz/opendrop/actions/workflows/tests.yml)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](desktop/OpenDrop/OpenDrop.csproj)


```text
PC (OpenDrop)  --->  QR CODE  --->  telephone / tablette / autre PC
                     |                    |
                  code a 6 caracteres     v
                                    interface web (HTTPS)
                                             |
                              Envoyer / Telecharger
                                             |
                                    transfert direct
                                        sur le LAN
```

Le fichier ne quitte jamais le reseau local : OpenDrop est un serveur HTTP(S)
pair-a-pair sur votre machine, rien ne transite par internet.

---

## Ce que ca fait

- **HTTPS obligatoire** : certificat auto-signe genere au premier demarrage
- **Session par token** : 32 caracteres aleatoires, expiration configurable,
  rotation manuelle (bouton Reset) ou automatique (minuterie), code de secours
  a 6 caracteres pour debloquer un appareil
- **Interface web** dans le navigateur, sans installation : onglets
  *Envoyer* et *Telecharger*, barre de quota en haut, verrou de session
- **Dossier Partage** : les fichiers places dedans sont proposes aux autres
  appareils, telechargeables en un clic
- **Quota global de reception** (optionnel) : refus en 507 avant d'ecrire,
  indicateur en direct (vert sous la limite, rouge une fois atteint)
- **Garde-fous** : 10 Go par fichier, limites de debit par IP, noms de
  fichiers assainis, chemins verifies, aucune fuite de chemin serveur
- **Bureau Windows** (WPF/.NET 8) : QR code, adresse, code de session,
  quota, dossiers, parametres, demarrage/Arret du serveur en un clic

---

## Captures d'ecran

A venir (`docs/screenshots/`) : l'application bureau (QR code, quota,
parametres) et l'interface web (onglets *Envoyer* / *Telecharger*).

---

## Prerequis

- Windows (l'application bureau est en WPF, .NET 8)
- Python **3.10+** (developpe et teste en 3.12)
- .NET 8 SDK pour builder l'application bureau

Dependances Python :

```powershell
pip install -e .            # qrcode[pil] + cryptography, installe la commande "opendrop"
```

---

## Demarrage

### 1. Application bureau (recommande)

```powershell
dotnet build desktop\OpenDrop\OpenDrop.csproj
.\desktop\OpenDrop\bin\Debug\net8.0-windows\OpenDrop.exe
```

L'application demarre le serveur automatiquement : la carte d'etat passe a
**Serveur actif**, l'adresse s'affiche, le QR code et le code de session sont
generes. Boutons en bas :

- **Demarrer le serveur / Arreter le serveur**
- **Parametres** (dossiers, port, quota, nouveau token au demarrage) : apres
  enregistrement, le serveur redemarre tout seul avec la nouvelle config

### 2. Serveur seul (sans interface bureau)

```powershell
opendrop                      # apres pip install -e .
# ou
$env:PYTHONPATH = "src"; python -m opendrop.main
```

Options utiles :

| Option | Effet |
|---|---|
| `--headless` | pas de fenetre QR ni de navigateur (usage GUI/automatisation) |
| `--port 9090` | force un port different de `preferred_port` |
| `--rotate-token` | force un nouveau token et un nouveau code de session |

---

## Utilisation sur un telephone

1. Notez l'adresse `https://<ip>:<port>` affichee par l'application.
2. Scannez le **QR code** (ou tapez l'URL avec `?token=...`).
3. Au premier acces, le navigateur affiche un avertissement de certificat
   auto-signe : acceptez celui de la machine OpenDrop uniquement
   (marche pas a pas dans [SECURITY.md](SECURITY.md)).
4. Si l'ecran indique **Session verrouillee**, tapez le **code a 6
   caracteres** affiche dans l'application bureau.
5. Onglet **Envoyer** pour envoyer un fichier, onglet **Telecharger** pour
   recuperer ceux du dossier *Partage*.

La ligne du haut affiche `usage / quota` et se met a jour toute seule
(toutes les 5 s, et apres chaque envoi). Vert : sous la limite. Rouge :
quota atteint.

---

## Dossiers et quota

| Dossier | Role |
|---|---|
| **Dossier de reception** | ou atterrissent les fichiers recus (cote PC) |
| **Dossier de partage** | fichiers proposes aux autres appareils (cote PC) |

Les deux se changent dans **Parametres** (parcours + Enregistrer).

**Quota global du dossier de reception** (Parametres > Stockage) :

- `0` = illimite (valeur par defaut)
- sans unite = Go : `500` vaut 500 Go ; avec unite : `500 mo`, `0,5 go`,
  `10.75` (virgule ou point)
- une valeur illisible est refusee avec un message, jamais ignoree ; une
  valeur negative dans `config.json` est ramenee a 0 (illimite)
- au-dela de 20 % de l'espace libre du disque, un avertissement demande
  confirmation avant l'enregistrement
- un envoi qui ferait depasser le quota est refuse en **507** avant ecriture ;
  deux envois simultanes ne peuvent pas passer sous la limite ensemble
- l'indicateur s'affiche aussi dans la fenetre principale, rafraichi toutes
  les 3 s sans redemarrage

---

## Fichiers de configuration

| Fichier | Contenu |
|---|---|
| `%LOCALAPPDATA%\OpenDrop\config.json` | dossiers, port, quota, options |
| `%LOCALAPPDATA%\OpenDrop\session.json` | token + code de session en cours |
| `%LOCALAPPDATA%\OpenDrop\certs\server.crt` / `server.key` | certificat TLS auto-signe (EC P-256, 397 jours) |

Cles de `config.json` :

| Cle | Defaut | Signification |
|---|---|---|
| `download_directory` | `%USERPROFILE%\Downloads\OpenDrop` | dossier de reception |
| `share_directory` | `%USERPROFILE%\Downloads\OpenDrop\Partage` | dossier de partage |
| `preferred_port` | `8080` | port demande (repli sur un port libre si pris) |
| `session_expires_in` | `3600` | duree de vie d'un token, en secondes |
| `global_quota_bytes` | `0` | quota total du dossier de reception, en octets |
| `generate_new_token` | `false` | nouveau token a chaque demarrage |
| `trust_proxy` | `false` | faire confiance a `X-Forwarded-For` (proxy connu uniquement) |

Pour regenerer le certificat : fermer OpenDrop, supprimer le dossier
`%LOCALAPPDATA%\OpenDrop\certs\`, relancer (voir SECURITY.md).

---

## Tests

Suites maison (aucun framework externe), a lancer depuis la racine :

```powershell
python -m tests.test_security     # 36/36 - tokens, chemins, limites, origine, ecriture, journaux
python -m tests.test_routes       # 44/44 - table de verite des routes
python -m tests.test_paths        # 43/43 - aucun chemin absolu en reponse
python -m tests.test_quota        # 40/40 - quota, reservations simultanees, 507
python -m tests.test_sessions     # 34/34 - sessions, expiration, rotation du code
python -m tests.test_tls          # 15/15 - certificat auto-signe, HTTPS force
python -m tests.test_server       # 11/11 - routes generales, port occupe
python -m tests.test_beta         # 64/64 - parc complet
python -m tests.test_beta --large # 76/76 - lots de fichiers, traversales
```

Avant de builder, fermez l'application bureau : un binaire en cours
d'execution bloque `dotnet build`.

Les memes suites (sans `--large`) sont executes en integration continue
sur Windows et Linux, Python 3.10 et 3.12.

---

## Securite

Le modele de menace complet (routes, jetons, quota, certificat, limites) est
documente dans [SECURITY.md](SECURITY.md). En resume :

- tout passe en HTTPS, certificat auto-signe a accepter manuellement ;
- le jeton est dans l'URL : il peut rester dans l'historique du navigateur ;
  les journaux du serveur, eux, affichent `token=***` et `code=***` ;
- aucun chiffrement au repos : ce qui arrive sur le disque y est en clair ;
  le SHA-256 renvoye a l'emetteur n'est pas compare automatiquement ;
- quiconque possede le jeton ou le code de session peut envoyer/recevoir.

---

## Structure du depot

| Dossier | Role |
|---|---|
| `src/opendrop/` | serveur Python (HTTPS, routes, sessions, quota, TLS) |
| `desktop/OpenDrop/` | application bureau WPF (.NET 8) qui pilote le serveur |
| `web/` | interface web (`index.html`, `app.js`, `style.css`) |
| `tests/` | suites de tests maison |
| `docs/` | documents du projet (captures) |
| `.github/` | integration continue, Dependabot, modeles d'issues |
| `SECURITY.md` | model de menace |
| `CONTRIBUTING.md` | comment contribuer |
| `LICENSE` | licence MIT |

---

## Contribuer

Corrections et fonctionnalites bienvenues : voir
[CONTRIBUTING.md](CONTRIBUTING.md). Les suites de tests tournent aussi en
integration continue (GitHub Actions) a chaque push et pull request.

Une faille a signaler ? Utilisez l'onglet *Security* du depot ou l'e-mail
indique dans [SECURITY.md](SECURITY.md) - pas d'issue publique.

Comportement attendu dans la communaute : [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## Licence

Distribue sous licence [MIT](LICENSE). Utilisez-le sous votre propre
responsabilite. Historique des versions : [CHANGELOG.md](CHANGELOG.md).
