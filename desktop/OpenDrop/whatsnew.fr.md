<!-- version: 0.16.0 -->
### Ajouté

- **Reprise des téléchargements (HTTP Range)** : `/api/download` comprend
  désormais un en-tête `Range` unique, si bien qu'un téléchargement
  interrompu dans le navigateur reprend là où il s'est arrêté
  (`bytes=N-`) au lieu de repartir de zéro. Une plage valide répond 206
  avec la tranche exacte et un `Content-Range` correct ; une plage
  au-delà de la fin du fichier obtient une 416 ; tout ce qui est
  malformé ou multi-plages reçoit toujours le fichier entier (200
  simple), et chaque téléchargement annonce `Accept-Ranges: bytes`.
- **L'onglet montre le transfert, et quitter en cours de route demande
  confirmation** : pendant qu'un zip ou un envoi est réellement en
  route, le titre de la page porte le pourcentage (`42% · OpenDrop` —
  volontairement neutre en langue) et un seul garde-fou `beforeunload`
  demande au navigateur de confirmer au lieu de laisser tomber le
  transfert. Le titre nu `OpenDrop` revient à chaque sortie — succès,
  annulation, zip annulé, erreurs — pour qu'un transfert fini ne laisse
  jamais derrière lui une invite « quitter le site ? ». Pas d'API
  Notification : la demande de permission ne vaut pas l'interface.
- **Installable comme application (PWA)** : un manifeste web, de vraies
  icônes (192 + 512 + maskable 512 + favicon) et un petit service
  worker rendent OpenDrop installable sur téléphone comme sur
  ordinateur. Le worker est network-first pour la coquille : le serveur
  vivant répond toujours, et le cache n'est que le repli hors ligne —
  une mise à jour ne peut donc jamais enfermer les utilisateurs sur une
  ancienne interface, et tout vieux cache est abandonné dès qu'un
  nouveau worker s'active. `/api` — envois, téléchargements, réponses
  Range — n'est jamais intercepté.
- **Le desktop annonce ses nouveautés, dans la fenêtre et en
  français** : après une mise à jour, l'application propose les notes de
  version une fois par version sous forme de popup fixe DANS la fenêtre
  principale (fond assombri, fermeture par la ✕, Échap ou un clic
  au-dehors, corps toujours défilant dans son cadre) — titres et puces
  gardent leur forme, et les liens des notes sont de vrais liens : un
  clic les ouvre dans le navigateur, l'infobulle montre l'URL et un
  clic droit la copie. GitHub ne portant que le corps anglais, une
  interface française rend une traduction livrée avec l'application,
  écrite à la main (`whatsnew.fr.md`, réécrite à chaque bump de version
  à côté de la section du changelog qu'elle traduit, sa première ligne
  nommant la version qu'elle concerne) ; bundle absent, en-tête
  malformé ou dérive de version retombent tous sur le corps anglais —
  la fenêtre ne meurt jamais pour une traduction, et ne peut jamais
  montrer les notes françaises d'une autre version. Le titre suit aussi
  la langue (FR « Quoi de neuf », EN « What's new »). Le premier
  lancement n'établit qu'en silence la ligne de base de la version ; la
  nouvelle version est mémorisée dans `config.json` avant tout
  aller-retour réseau, si bien qu'avec GitHub injoignable rien ne
  s'affiche et l'invite ne peut ni boucler ni ralentir le démarrage.
  L'intégration continue desktop lance maintenant les tests unitaires
  (`dotnet test`) avant publication.
- **Le pipeline de release raconte toute l'histoire** : chaque release
  porte désormais la section `## [<version>]` correspondante de ce
  changelog comme notes de release GitHub (fixée à la création — les
  corps existants ne sont jamais réécrits, et une tag sans section
  garde les notes auto-générées en repli), reçoit des captures
  FR/EN × clair/sombre de l'application via un job CI dédié, et le
  dépôt est analysé par CodeQL (Python + JavaScript à chaque push sur
  main, chaque pull request, et une exécution hebdomadaire).

### Sécurité

- Onze suites, 445 vérifications au total — les dix suites Python en
  portent 429 et la nouvelle `tests/test_e2e.py` en porte 16 : chromium,
  firefox et webkit pilotent la vraie interface contre un vrai serveur
  (envoi en une seule tranche, envoi en deux tranches avec annulation,
  reprise Range, la garde `beforeunload`/titre d'onglet, le
  rechargement service-worker de la PWA), webkit n'étant exclu que des
  scénarios à deux tranches par une limite de pilote imprimée et
  documentée. `test_beta --large` ajoute 75 vérifications (75/75) et
  les tests unitaires du desktop 57 (`dotnet test` en CI).
