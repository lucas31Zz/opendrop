# Changelog

Tous les changements importants de ce projet sont documentes dans ce fichier.

Format adapte de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Versioning : [Semantic Versioning](https://semver.org/lang/fr/).

## [Unreleased]

## [0.2.0] - 2026-09-27

### Ajoute

- Application bureau multiplateforme : port de WPF vers **Avalonia** (.NET 8),
  un seul code pour Windows (`win-x64`) et Linux (`linux-x64`), publie en
  fichier unique auto-contenu
- **Installeur Windows** (Inno Setup) : droits admin, installation dans
  `Program Files (x86)`, dependances Python installees en local a partir des
  wheels fournis (hors-ligne, venv dans le dossier d'installation),
  raccourcis menu/bureau, interface francais/anglais, desinstalleur qui
  nettoie les donnees applicatives **sans jamais toucher** aux dossiers de
  reception et de partage
- **Scripts Linux** (`install.sh` / `uninstall.sh`) : installation dans
  `/opt/opendrop` avec venv local et entree de menu (`opendrop-desktop`),
  desinstallation equivalentes conservant les fichiers recus et partages
- Release automatique : a chaque tag `v*`, GitHub Actions genere
  `*-win-x64-setup.exe`, `*-win-x64.zip` et `*-linux-x64.tar.gz` (wheels
  hors-ligne inclus)
- Icône d'application et de menu generees par `tools/make_icon.py` (QR code)
- Lancement sous Linux : le QR code s'ouvre via `xdg-open` (et `open` sur
  macOS) au lieu d'etre ignore (`os.startfile` n'existe que sous Windows)
- README : section *Linux (pas de bureau possible)*, section
  *Telechargements*, prerequisites multiplateformes, badge Linux
- Classifier `Operating System :: POSIX :: Linux` dans pyproject

### Corrige

- `server.pid` : le dossier de config n'existait pas au tout premier
  lancement, l'ecriture echouait en silence et un serveur orphelin pouvait
  garder le port au lancement suivant
- L'application bureau utilise d'abord le `venv` cree par l'installeur
  (`venv/Scripts/python.exe`, `venv/bin/python3`) avant `python`/`python3`
  du PATH : dependances garanties quelle que soit la configuration
- Chemin de config du bureau aligne sur le serveur Python : lecture de
  `LOCALAPPDATA` comme cote Python, repli `~/.opendrop` sous Linux (desktop
  et serveur lisent le meme `config.json` sur les deux systemes)
- Lancement du serveur sous Linux : `python3` d'abord (Debian/Kali n'ont pas
  d'alias `python`)

## [0.1.0] - 2026-09-27

Premiere version publique.

### Ajoute

- Serveur HTTP(S) local : certificat auto-signe EC P-256 (397 jours),
  HTTPS force sur toutes les routes, TLS 1.2+
- Session par jeton aleatoire de 32 caracteres, expiration configurable,
  rotation manuelle (`--rotate-token`, bouton Reset) ou automatique,
  code de secours a 6 caracteres (31^6, 5 essais/min/IP)
- Interface web sans installation : onglets *Envoyer* / *Telecharger*,
  verrou de session, barre de quota en direct (vert/rouge)
- Dossier *Partage* : fichiers proposes aux autres appareils, telechargement
  en un clic
- Quota global de reception : refus 507 avant ecriture, reservations
  atomiques (envois simultanes), valeur negative ramenee a 0 (illimite)
- Garde-fous : 10 Go par fichier, limites de debit par IP, noms de fichiers
  assainis, chemins verifies, aucune fuite de chemin serveur, journaux sans
  secrets (`token=***`, `code=***`)
- Application bureau Windows (WPF, .NET 8) : QR code, adresse, code de
  session, quota, dossiers, parametres, demarrage/Arret du serveur
- Tests maison : 8 suites, 287 verifications (299 avec `--large`)
- Integration continue GitHub Actions (tests + build bureau) et Dependabot
