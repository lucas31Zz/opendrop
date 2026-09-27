# Changelog

Tous les changements importants de ce projet sont documentes dans ce fichier.

Format adapte de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Versioning : [Semantic Versioning](https://semver.org/lang/fr/).

## [Unreleased]

### Ajoute

- Lancement sous Linux : le QR code s'ouvre via `xdg-open` (et `open` sur
  macOS) au lieu d'etre ignore (`os.startfile` n'existe que sous Windows)
- README : section *Linux (pas de bureau possible)*, prerequisites
  multiplateformes, badge Linux
- Classifier `Operating System :: POSIX :: Linux` dans pyproject

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
