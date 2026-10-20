<!-- version: 0.16.1 -->
### Ajouté

- **Le panneau Paramètres de l'interface web rejoint les captures du
  README** (clair et sombre) : l'outil de capture local passe désormais
  d'abord par le vrai recouvrement `#pair=`, si bien que le panneau
  affiche le bloc de l'appareil appairé (jeton, IP, dissocier) au lieu
  du champ de collage, puis ouvre l'engrenage après la capture de
  l'onglet Téléchargement. Les onze images du README ont été
  régénérées depuis l'interface actuelle — l'ancien lot montrait encore
  l'ancien logo et l'ancienne zone de dépôt.

### Retiré

- **Les releases n'attachent plus de captures PNG** : le job
  `screenshots` du workflow de release et le script
  `tests/screenshots.py` qui le portait ont disparu, et les quatre
  captures langue × thème ont été supprimées de la release v0.16.0. Les
  captures vivent dans le README seulement — jamais dans le changelog
  ni les notes de release.

### Corrigé

- **Linux : l'entrée du menu des applications ne lançait rien.**
  `install.sh` ne copiait jamais les bibliothèques natives du binaire
  publié (`libSkiaSharp.so`, `libHarfbBuzzSharp.so`) dans
  `/opt/opendrop` : la publication en fichier unique les garde à côté de
  l'exécutable et .NET les charge depuis le dossier de l'application,
  si bien que l'application installée mourait au démarrage avec un
  `DllNotFoundException` et sans fenêtre — lancer directement depuis le
  dossier extrait fonctionnait, l'entrée du menu non. L'installeur
  copie désormais tout `*.so` porté par le lot, ce qui répare aussi le
  chemin de mise à jour automatique (il relance `install.sh` par-dessus
  l'installation existante). Trouvé à la main sur Kali le 20/10/2026.
