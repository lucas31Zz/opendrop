# OpenDrop - Model de menace

## Objectif

OpenDrop est un outil de transfert de fichiers sur reseau local (LAN).
Il est concu pour un usage personnel, dans un reseau domestique ou bureautique.

Installation et prise en main : voir [README.md](README.md).

---

## Ce qu'OpenDrop protege

### 1. Acces non autorise

- Chaque session a un token aleatoire de 32 caracteres ([a-zA-Z0-9],
  62^32 combinaisons)
- Les tokens expirent apres une duree configurable
  (`session_expires_in` dans config.json, defaut: 1 heure)
- Les tokens expires sont supprimes automatiquement
- Un nettoyage periodique des sessions expirees tourne en arriere-plan
- L'origine des requetes (`Origin`) est comparee a l'URL reelle du serveur
  (HTTPS + IP + port) : toute origine etrangere, et surtout une origine en
  HTTP, donne 403
- Sans QR code, le code de session (6 caracteres, alphabet sans ambiguite :
  31 lettres/chiffres sans O/0/I/1/L, soit 31^6 = 887 503 681 combinaisons)
  debloque l'appareil : il est borne a 5 essais / minute / IP, la comparaison
  se fait en temps constant (`secrets.compare_digest`), insensible a la casse
  et aux separateurs
- Le code n'a pas d'expiration propre : il vit aussi longtemps que
  `session.json` et ne change qu'a la rotation (bouton Reset du bureau,
  `--rotate-token`, case "Nouveau token au demarrage"). A la rotation, le
  code precedent devient invalide immediatement (teste)
- Le code reste utilisable une fois le jeton expire : c'est la fonction de
  secours (teste)
- Le deverrouillage delivre un nouveau jeton de 32 caracteres avec les memes
  droits : chaque appareil debloque a son propre jeton, aucun droit n'est
  granulaire
- Chaque route marquee "jeton obligatoire" au tableau de la section 5 est
  verifiee cote serveur, jeton absent ou expire donne 403

### 2. Chemins dangereux

- A l'envoi, le nom est ramene au nom de base (basename), les caracteres
  dangereux (`< > : " / \ | ? *`, controles) sont remplaces par `_`, les
  points et espaces de bord sont retires, et les noms reserves Windows
  (CON, PRN, COM1...) sont ecartes : il ne reste que le nom du fichier
- Au telechargement, le chemin est resolu contre le dossier de partage
  (is_safe_path, avec `realpath`) : toute tentative de sortir du dossier
  (`..`, separateur `/`, lien symbolique) donne 400 "Chemin non autorise"
- Seuls les fichiers du dossier de partage sont accessibles en telechargement

### 3. Deni de service

- Rate limiting par IP :
  - Upload: 10 requetes / minute
  - Download: 30 requetes / minute
  - General (toutes les routes /api/ et /qr): 120 requetes / minute
  - Deverrouillage de session: 5 requetes / minute
- Limite de taille: 10 Go par fichier (MAX_UPLOAD_SIZE). Le corps de la
  requete est strictement borne a Content-Length : mentir sur la longueur
  n'autorise pas a depasser la limite, et un envoi tronque est rejete puis
  supprime
- Cette limite porte sur chaque fichier, pas sur le total recu : voir la
  section "Remplissage du disque" (quota global optionnel) pour la suite
- L'upload est lu et ecrit en flux (blocs de 64 Ko) : un fichier de 10 Go
  n'est jamais charge entier en memoire
- L'IP client est toujours celle de la connexion TCP ; X-Forwarded-For n'est
  pris en compte que si "trust_proxy" est active dans config.json (proxy de
  confiance), sinon il serait contournable pour esquiver le rate limiting

### 4. Fuite d'informations

- Pas de traceback dans les reponses HTTP
- Messages d'erreur generiques pour les erreurs internes
- Les chemins reels du serveur ne sont pas exposes (voir section 6)
- L'en-tete `Server` ne porte que `OpenDrop`, sans version de Python
- Les reponses d'erreur HTML sont courtes, echappees et embarquent les
  memes en-tetes de securite que le reste

### 5. Routes et jetons

Table de verite testee par `python -m tests.test_routes` :

| Route | Acces | Remarque |
|---|---|---|
| `POST /api/upload` | jeton obligatoire | rate limit 10/min par IP |
| `GET /api/files` | jeton obligatoire | liste du dossier de partage (fichiers proposes) |
| `GET /api/progress` | jeton obligatoire | progression d'upload |
| `GET /api/quota` | jeton obligatoire | usage + quota global |
| `GET /api/download/*` | jeton obligatoire | rate limit 30/min par IP |
| `GET /qr` | jeton obligatoire | rate limit 120/min (PNG encode le token) |
| `POST /api/session/unlock` | code a 6 caracteres | rate limit 5/min par IP, reponse = jeton |
| `GET /api/info` | public | route de decouverte (ip + port) pour le desktop et le probe ; le bloc `session` (nb de sessions actives, duree) ne sort que pour un porteur de jeton valide, et un mauvais jeton donne 403 |
| `GET /`, `/style.css`, `/app.js` | public | shell de l'interface web, aucun secret |
| route `/api/*` inconnue | - | 404 JSON `{"error": ..., "code": 404}` |
| page HTML inconnue | - | 404 HTML court, sans detail interne |

- Ni jeton ni code de session n'apparaissent dans les pages HTML, les
  erreurs ou `/api/info` ; seuls `/qr` (par conception) et la reponse de
  `POST /api/session/unlock` (delivree au detenteur du code) transportent
  le jeton
- Le nom de fichier en telechargement est encode en fallback ASCII puis
  `filename*=UTF-8''...` : un nom non Latin-1 ne casse plus l'en-tete et
  aucun caractere de controle (CR/LF) ne peut y etre injecte

### 6. Chemins absolus

Teste par `python -m tests.test_paths` :

- La reponse d'upload ne contient que `filename`, `size` et `sha256` : le
  chemin reel du serveur (`str(dest)`) n'y figure plus, il ne sort que
  dans la console du serveur
- `GET /api/files` ne rend que `{name, size}` par fichier
- `GET /api/progress` ne contient aucun chemin (etat : fichier, taille,
  recu, vitesse, erreur)
- Les messages d'erreur sont des chaines fixes (`errors.py`) : aucun
  `OSError` brut, aucune stack trace, aucun chemin de dossier
- Les erreurs d'ecriture disque (`DiskError`) ne portent que la raison
  systeme (`[Errno 28] No space left on device`) : le nom de fichier ou de
  dossier n'y figure pas, il ne sort donc ni dans la reponse 507 ni dans le
  message d'erreur affiche
- Les journaux du serveur masquent les secrets : `?token=...` et
  `?code=...` sont remplaces par `token=***` / `code=***` avant impression.
  Rediriger les sorties du serveur vers un fichier ne met donc ni le jeton
  ni le code sur le disque
- Les assets (`/`, `/style.css`, `/app.js`) ne contiennent aucun chemin
  local : l'interface ne connait que des URLs relatives
- Le dossier de reception et le dossier de partage sont affiches dans les
  Reglages de l'application : interface locale uniquement, jamais servie
  en reseau
- Les traces avec chemins reels (`[OpenDrop] Fichier recu: ... ->
  C:\...`) vont dans la console/les logs locaux du serveur, pas dans une
  reponse HTTP

---

## Ce qu'OpenDrop ne protege PAS

### Reseau

- Le trafic est chiffre en transit : HTTPS force, TLS 1.2 minimum (voir la
  section "Certificat TLS")
- Le certificat est auto-signe : aucune autorite ne garantit l'identite du
  serveur. Un attaquant present sur le meme reseau peut proposer son propre
  certificat ; il faut accepter celui de la machine OpenDrop, jamais celui
  d'un autre appareil
- Le token est place dans l'URL (?token=...) : il peut rester dans
  l'historique du navigateur, les favoris et les logs du serveur
- Un ancien QR code en http:// ne fonctionne plus : le serveur n'ecoute
  qu'en HTTPS. Rescanne le QR affiche par l'application bureau

### Authenticite

- OpenDrop ne verifie pas l'identite des appareils
- Quiconque a le token peut envoyer/recevoir des fichiers
- La securite d'acces repose sur l'imprevisibilite cryptographique du
  token (32 caracteres aleatoires)

### Donnees

- Pas de chiffrement au repos
- Le SHA-256 est calcule a l'ecriture, octet par octet, sur ce qui est
  reellement ecrit, et il n'est renvoye que si la frontiere finale du corps
  a ete vue : un envoi tronque ou une ecriture qui echoue au dernier bloc
  donne 400/507, le fichier partiel est supprime et aucun hash n'est rendu.
  Rien ne le compare automatiquement cote reception : l'interface web
  l'affiche, l'emetteur doit le verifier
- Les fichiers supprimes ne sont pas irreversiblement effaces

### Remplissage du disque

- La limite de 10 Go vaut par fichier, pas pour l'ensemble des fichiers
  recus : rien n'empeche d'envoyer des dizaines de fichiers de moins de
  10 Go jusqu'a saturer le disque de destination
- Quota global optionnel sur le dossier de reception
  (`global_quota_bytes` dans config.json, en octets ; 0 ou cle absente =
  illimite). Regle dans les Reglages de l'application, champ "Quota global
  du dossier de reception" : nombre entier (sans unite = Go, d'ou "500
  vaut 500 Go") ou avec unite (go, mo, kb, tb ; "500 mo" vaut 500 Mo),
  virgule ou point acceptes, 0 = illimite. Une valeur illisible est
  refusee (message d'erreur), jamais ignoree silencieusement ; une valeur
  negative (config editee a la main) est ramenee a 0, c'est-a-dire illimite,
  plutot que d'etre interpretee comme une limite impossible a satisfaire.
  Le quota est verifie sur l'en-tete (Content-Length) avant la reception :
  un envoi qui ferait depasser le total est refuse en 507
  ("Quota global atteint : X utilise sur Y") sans ecrire de fichier, apres
  absorption d'un morceau du corps pour que le client lise bien le message
  - La reservation est atomique (verrou) : deux envois simultanes ne peuvent
    pas passer sous la limite ensemble, l'un des deux est refuse en 507 et
    le total reste inferieur ou egal au quota (teste)
  - Le quota est accepte au poids exact (comparaison `>` : usage + taille =
    quota passe, l'octet suivant est refuse), teste en HTTP
  - Par defaut le quota est desactive : le remplissage du disque reste
    possible sans limite d'ensemble tant que l'utilisateur n'en a pas regle
    un
  - Chaque reservation est liberee, y compris si l'ecriture echoue ou si le
    corps est invalide : aucune place fantome n'est perdue
- Avant l'enregistrement d'un quota superieur a 20 % de l'espace libre du
  disque, l'application affiche un avertissement ("A vos risques et
  perils") et n'enregistre que si l'utilisateur confirme
- Suivi en direct : l'application desktop affiche "usage / quota" (vert
  tant que la limite n'est pas atteinte, rouge ensuite, mis a jour toutes
  les 3 s sans redemarrage) et l'interface web la meme ligne en haut des
  onglets "Envoyer" et "Telecharger". Le web lit GET /api/quota (token
  obligatoire, sinon 403) toutes les 5 s et apres chaque envoi ; le champ
  "usage_bytes" inclut les envois en cours (reservation comprise)
- Pas de verification d'espace libre avant ecriture : le manque de place
  n'est detecte qu'en cours d'ecriture. Le quota, lui, ne compte que les
  fichiers deja presents dans le dossier de reception : il ne dit rien de
  l'espace libre restant sur le disque, ni de ce que les autres dossiers ou
  applications en font
- Dans ce cas le serveur repond 507 (Espace disque insuffisant), supprime
  le fichier partiel et echoue proprement : aucun fichier tronque ne reste.
  Cela vaut aussi quand la fermeture du fichier echoue au dernier bloc
  (flush final) : le 507 est rendu et le hash n'est pas delivre
- Le rate limiting d'upload (10/min) ralentit la cadence sans limiter le
  volume total

### Validation

- OpenDrop ne valide pas le contenu des fichiers
- Les fichiers dangereux (.exe, .bat, etc.) peuvent etre recus
- C'est a l'utilisateur de verifier ce qu'il ouvre

---

## Certificat TLS

OpenDrop parle uniquement en HTTPS. Le certificat est genere localement au
premier demarrage : il est auto-signe, donc le navigateur affiche un
avertissement de confiance a la premiere connexion. C'est attendu.

### Emplacement

- Dossier : `%LOCALAPPDATA%\OpenDrop\certs\`
- Fichiers : `server.crt` (certificat) et `server.key` (cle privee, droits 600)
- Algorithme : cle EC P-256, auto-signe, SHA-256, validite 397 jours
- SAN : `localhost`, le nom de la machine, `127.0.0.1` et l'IP courante du LAN

### Regeneration automatique

Le certificat est regenere au demarrage du serveur si :

- le fichier est absent ou illisible,
- il expire dans moins de 30 jours,
- l'IP actuelle n'est plus dans les SAN (changement DHCP),
- la cle ne correspond plus au certificat,
- l'extension EKU serverAuth manque (exigee par iOS/Safari).

### Regeneration manuelle

1. Fermer OpenDrop (l'application bureau et son serveur).
2. Supprimer le dossier `%LOCALAPPDATA%\OpenDrop\certs\`.
3. Relancer OpenDrop : un nouveau certificat est cree automatiquement.

Le token, le QR code et le code de session ne changent PAS lors d'une
regeneration (ils ne changent que sur bouton Reset, minuterie ou case
"Nouveau token au demarrage"). En cas de doute, rescanner le QR affiche par
le bureau reste sans risque : c'est la source de verite.

### Premier acces depuis un telephone

Le certificat auto-signe declenche un ecran d'avertissement. Ne clique pas
sur "Arreter" : accepte celui de la machine OpenDrop uniquement.

Chrome / Android :

1. « Votre connexion n'est pas privée »
2. « Avancé »
3. « Continuer vers *votre-ip* (non sécurisé) »

Safari / iOS :

1. « Cette connexion n'est pas privée »
2. « Afficher les détails du site web »
3. « Visiter ce site web »

Firefox :

1. « La connexion n'est pas sécurisée »
2. « Continuer au poste de travail (non sécurisé) »

Si le certificat a ete regenere (IP changee, expiration, suppression du
dossier certs), l'avertissement revient : il faut l'accepter a nouveau.

### Choisir une IP stable

Le certificat contient l'IP courante. Si le routeur attribue une autre IP
(DHCP), le certificat est regenere et l'avertissement revient sur chaque
telephone. Pour l'eviter : reserve l'IP de la machine dans les parametres
DHCP du routeur (bail fixe / reservation DHCP). L'IP reste alors la meme et
le certificat reste valable jusqu'a son expiration (397 jours).

### Ce que le chiffrement couvre

- Fait : URL, token et contenu des fichiers transitent chiffres dans le LAN.
  Une ecoute passive (tcpdump, Wireshark) ne voit que du TLS
- Limite : pas de verification d'identite par une autorite de confiance
  (certificat auto-signe). L'usager doit accepter manuellement ; accepter le
  certificat d'un autre appareil rendrait la protection illusoire
- Pas fait : chiffrement au repos, ni attestation de l'identite des appareils
  qui possedent le token

---

## Verification

Tout ce qui precede est couvert par des tests automatises (a lancer depuis
la racine du depot, Python 3.12, aucun framework externe) :

| Commande | Ce qu'elle prouve | Resultat |
|---|---|---|
| `python -m tests.test_security` | tokens, chemins, limites de taille, origine, corps incomplet, echec d'ecriture, journaux sans secret | 36/36 |
| `python -m tests.test_routes` | table de verite des routes (section 5) | 44/44 |
| `python -m tests.test_paths` | aucun chemin absolu en reponse (section 6) | 43/43 |
| `python -m tests.test_quota` | quota global, reservations simultanees, remplissage exact, 507 | 40/40 |
| `python -m tests.test_sessions` | sessions, expiration, code de session, rotation via `opendrop.main` | 34/34 |
| `python -m tests.test_tls` | certificat auto-signe, cle/cert, EKU, renouvellement, HTTPS force | 15/15 |
| `python -m tests.test_server` | routes generales, port occupe, demarrage rapide | 11/11 |
| `python -m tests.test_beta` (+ `--large`) | parc complet, lots de fichiers, traversales | 64/64 et 76/76 |

---

## Model de menace

| Menace | Protection | Statut |
|---|---|---|
| Acces sans token | Jeton obligatoire pour toute route portant des donnees ; `/api/info` public sans secret (voir section 5) | Fait |
| Requete depuis un autre site | Origine (`Origin`) comparee a l'URL reelle du serveur : 403 sinon | Fait |
| Force brute du code de session | Code a 6 caracteres (31^6), 5 essais / minute / IP, rotation a la demande | Fait |
| Token brute-force | 32 caracteres aleatoires (62^32 combinaisons) | Fait |
| Token expire | Expiration configurable + nettoyage automatique ; le code de secours reste utilisable | Fait |
| Path traversal | Validation des chemins avec is_safe_path | Fait |
| Remplissage disque | 10 Go par fichier + quota global optionnel (507, reservation atomique) | Partiel |
| DoS par requetes | Rate limiting par IP | Fait |
| Fuite de stack trace | Pas de traceback dans les reponses | Fait |
| Fuite de chemin absolu | Reponses sans chemin serveur (upload = nom + taille + hash), erreurs disque sans chemin | Fait |
| Fuite de secret dans les journaux | `token=` et `code=` remplaces par `***` dans les journaux du serveur | Fait |
| Interception reseau | HTTPS force (TLS 1.2+), certificat auto-signe | Fait |
| Chiffrement en transit | HTTPS force sur toutes les routes API | Fait |
| Chiffrement au repos | Non protege | Futur |
| Attestation d'identite | Certificat auto-signe, acceptation manuelle (teste : non approuve par defaut) | Limite |
| Verification integrite | SHA-256 rendu seulement si le corps est complet ; affiche, pas de comparaison automatique | Fait |

---

## Signaler une vulnerabilite

Si vous trouvez une faille de securite, ne la publiez pas publiquement
(ici ni en issue). Deux canaux, par ordre de preference :

1. **Formulaire prive GitHub** : onglet *Security* du depot >
   *Report a vulnerability*. Le signalement est chiffre et reste confidentiel.
2. **E-mail** : lucasbertholon1@gmail.com (objet : « OpenDrop - securite »).

Merci d'indiquer la route concernee, les etapes de reproduction et l'impact
eventuel. Reponse sous quelques jours ; aucun recours contre un signalement
de bonne foi.

---

## Licence

OpenDrop est publie sous licence [MIT](LICENSE) - voir aussi
[CONTRIBUTING.md](CONTRIBUTING.md). Utilisez-le sous votre propre
responsabilite.
