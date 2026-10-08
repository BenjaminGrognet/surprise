# Lancer le projet soi-même (sans Claude)

## Le plus simple : double-cliquer

Trois fichiers à la racine du projet (double-clic, ou depuis un terminal) :

- **`lancer.cmd`** : le serveur (http://127.0.0.1:8001, modération sur `/admin`) et l'app Expo dans le navigateur,
  chacun dans sa fenêtre ; fermer la fenêtre l'arrête. Il reconstruit aussi le site (le build web de l'app, servi
  sur 8001) dans une fenêtre réduite qui se ferme seule : le site est toujours l'app du moment. Répondre `o` à « Aussi sur le téléphone ? » pour l'ouvrir
  aussi dans Expo Go (même Wi-Fi) : l'IP du PC est trouvée toute seule, scanner le QR code.
- **`collecte.cmd`** : collecte de toutes les sources, 200 fiches au plus chacune (ou d'une seule : taper son nom,
  ex. `fever`), puis enrichissement et mots-clés.
- **`admin.cmd`** : la modération seule, ouverte dans le navigateur (http://127.0.0.1:8000/admin) ; fermer la
  fenêtre l'arrête.

Seul prérequis : le fichier `.env` (étape 0 ci-dessous). Les dépendances de l'app s'installent au premier lancement.

La suite détaille ce que font les scripts, pour lancer les commandes à la main.

Tout se lance depuis un terminal (PowerShell ou Git Bash), à la racine du projet `C:\data\claude\surprise`, sauf
l'app Expo qui se lance depuis `app\`. Le détail de chaque commande et de ses options est dans le [README](../README.md).

## 0. Une seule fois : les prérequis

- **uv** (Python) : déjà installé (`uv --version`). Sinon : `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`.
- **Node.js** (pour Expo) : déjà installé (`node --version`). Sinon : https://nodejs.org (version LTS).
- **Dépendances Python** : `uv sync` (crée `.venv`, refait automatiquement par `uv run` si besoin).
- **Dépendances de l'app** : `cd app` puis `npm install`.
- **Fichiers de configuration** (jamais commités) :
  - `.env` à la racine : `SUPABASE_DB_URL` (URL du *session pooler*, voir README § Base) ; facultatifs : `ANTHROPIC_API_KEY` (titres des parcours et
    `enrich --claude`), `GOOGLE_PLACES_API_KEY` (photos), `SMTP_URL`, `MAIL_FROM`, `MAIL_SECRET` et `APP_URL` (les emails des
    soirées, README § Emails), les identifiants des programmes d'affiliation (README § Liens partenaires).
  - `app\.env` (modèle : `app\.env.example`) : `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY` et
    `EXPO_PUBLIC_API_URL=http://localhost:8001` (le serveur du questionnaire, **8001**, pas 8000).

Sans `--env-file .env`, les scripts n'ont pas `SUPABASE_DB_URL` et travaillent sur la base locale `data/surprise.db`.

## 1. La collecte

Toutes les sources, 50 fiches au plus chacune (toujours avec une limite) :

```bash
uv run --env-file .env python -m surprise.collect --limit 50
```

Une seule source (ou plusieurs, `--source` répétable) :

```bash
uv run --env-file .env python -m surprise.collect --source fever --limit 50
```

Ou le collecteur directement :

```bash
uv run --env-file .env python -m surprise.collectors.fever --store supabase --limit 50
```

Options utiles : `--refresh` relit aussi les pages encore fraîches, `--minutes 20` borne le temps par source,
`--jobs 4` le nombre de sources en parallèle. Liste des sources : README § Collecte complète.

Arrêter : `Ctrl+C`. Sous Windows, si des `python.exe` restent en tâche de fond :

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process
```

## 2. Après la collecte : enrichissement et mots-clés

```bash
uv run --env-file .env python -m surprise.enrich
uv run --env-file .env python -m surprise.keywords
```

`enrich` ne traite que les nouvelles activités (`--source <id>` pour une source, `--refresh` pour tout refaire,
`--claude` pour des descriptions rédigées par Claude, payant).

## 3. Le serveur (questionnaire + parcours + modération)

```bash
uv run --env-file .env python -m surprise.quiz
```

- Site : http://127.0.0.1:8001, le build web de l'app (`cd app` puis `npm run build:web` pour le refaire à la
  main) ; `/admin` pour la modération.
- `--no-open` pour ne pas ouvrir le navigateur, `--host 0.0.0.0` pour y accéder depuis un téléphone sur le même Wi-Fi.
- C'est ce serveur que l'app Expo interroge : il doit tourner avant de lancer l'app.

Modération seule (optionnel, déjà incluse dans le serveur ci-dessus) :

```bash
uv run --env-file .env python -m surprise.admin
```

→ http://127.0.0.1:8000/admin

## 4. L'app Expo

Dans un **deuxième terminal**, le serveur de l'étape 3 tournant dans le premier :

```bash
cd app
npm run web
```

→ http://localhost:8081 dans le navigateur.

### Sur le téléphone (Expo Go)

1. Installer **Expo Go** (App Store / Play Store). Téléphone et PC sur le même Wi-Fi.
2. Lancer le serveur Python accessible du réseau :
   `uv run --env-file .env python -m surprise.quiz --host 0.0.0.0 --no-open`
   (Windows peut demander d'autoriser Python dans le pare-feu : accepter pour les réseaux privés.)
3. Donner à l'app l'IP du PC (`ipconfig` → « Adresse IPv4 », ex. `192.168.1.20`) : sur le téléphone, `localhost`
   désigne le téléphone lui-même. Une variable définie dans le terminal l'emporte sur `app\.env` :
   `cd app`, puis `set EXPO_PUBLIC_API_URL=http://192.168.1.20:8001` (cmd) ou
   `$env:EXPO_PUBLIC_API_URL="http://192.168.1.20:8001"` (PowerShell).
4. Dans ce même terminal, `npx expo start`, et scanner le QR code affiché avec l'appareil photo (iPhone) ou Expo Go
   (Android). Si le téléphone ne se connecte pas (Wi-Fi d'entreprise), `npx expo start --tunnel`.

Après une modification de `app\.env`, relancer Expo (`npx expo start -c` vide le cache).

## 5. Autres commandes

```bash
uv run pytest                                                   # tests
uv run --env-file .env python -m surprise.parcours 2026-10-09 --budget 150 --de 19:00 --a 00:30 --vibes romantique,musique
uv run --env-file .env python -m surprise.availability 2026-10-09
uv run --env-file .env python -m surprise.local_store --db data/surprise.db   # copie la base locale dans Supabase
```

## En cas de problème

| Symptôme | Cause probable |
|---|---|
| L'app affiche une erreur `/api/quiz: …` ou reste vide | le serveur `surprise.quiz` ne tourne pas, ou `EXPO_PUBLIC_API_URL` ne pointe pas sur le port 8001 |
| « comptes non configurés » | `EXPO_PUBLIC_SUPABASE_*` manquants dans `app\.env` (puis refaire le build) |
| Le site (8001) n'a pas la dernière version de l'app | build pas refait : `npm run build:web` dans `app\` (ou relancer `lancer.cmd`) |
| La base est vide | commande lancée sans `--env-file .env` : elle a lu `data/surprise.db` au lieu de Supabase |
| Connexion à Supabase impossible | `SUPABASE_DB_URL` doit être l'URL du *session pooler* (IPv4), pas `db.<projet>.supabase.co` |
| `opendata.paris.fr` ne répond pas | préfixer par `OPENDATA_PARIS_URL=https://parisdata.opendatasoft.com` (Git Bash) |
| Le téléphone n'ouvre pas l'app après le QR code | Wi-Fi du PC en réseau « Public » : le pare-feu bloque Node (8081) et Python (8001). Le passer en « Privé » (Paramètres > Réseau et Internet > Wi-Fi > le réseau) |
| Port déjà utilisé | un ancien serveur tourne encore : le fermer, ou `--port 8002` |
