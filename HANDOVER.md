# Handover — 15 octobre 2026

Pour reprendre le travail dans une nouvelle session. Ce fichier n'est pas commité ; il peut être supprimé une fois lu.

## En bref

- **Demande 1** (idées, ergonomie et fluidité, guide de déploiement) : **terminée, rien n'est commité.** La question
  posée à l'utilisateur, « Je commite le tout ? », attend toujours sa réponse. Ne pas commiter sans son accord.
- **Demande 2** (« Conçois ceci pour moi » : les fonctionnalités de complicité retenues) : **commencée seulement.**
  Le modèle de données a été lu, aucun fichier n'est écrit. C'est la prochaine étape (section 4).

## 1. Travail terminé, non commité

### Fluidité (mesurée)
| Changement | Fichiers | Gain |
|---|---|---|
| Cache du navigateur : scripts, polices et images à hash gardés un an (`immutable`), le reste `no-store` ; les copies d'images gardées un mois, sans gzip | `src/surprise/quiz.py` (`web_cache`, `IMAGE_CACHE`), `src/surprise/admin.py` (`_send`) | un rechargement : 2,9 Mo → 0 Ko |
| Logo de l'en-tête en copie 256 px | `app/assets/images/logo-secretdate-256.jpg`, `app/src/components/logo-secretdate.tsx` | 1,6 Mo → 20 Ko |
| Options du formulaire chargées dès l'accueil, une seule requête en vol, réessai si le serveur ne répond pas | `app/src/lib/api.ts` (`once`, `known`, `knownSoiree`, `prefetchSoiree`), `app/src/app/soiree.tsx`, `app/src/app/index.tsx` | plus d'écran « Chargement… » |
| Données de l'accueil lues en parallèle | `app/src/app/index.tsx` (`Promise.all`) | |
| Copies d'images réduites à 1 200 px (JPEG progressif 82, PNG si transparence, original gardé si GIF ou pas plus léger) | `src/surprise/images.py` (`lighter`), Pillow ajouté dans `pyproject.toml` | 5,5 Mo → 2,4 Mo sur les copies actuelles |

### Ergonomie
- Boutons « en cours » : `PrimaryButton busy` (`app/src/components/buttons.tsx`, `spinner.tsx`) ; « On scelle
  l'intrigue… » (`route-result.tsx`), « Connexion… » / « Création du compte… » (`auth-form.tsx`).
- Le bouton du formulaire n'est plus grisé si une réponse manque : il fait défiler jusqu'à la question (dîner ou
  humeur) et l'entoure d'or. `useBringIntoView()` dans `app/src/components/screen.tsx`, utilisé dans `soiree.tsx`.
- Page d'entrée sur téléphone : la connexion d'abord, l'explication instigateur / invité dessous (`compte.tsx`).
- Zones de toucher agrandies sur « Changer », « Retirer », « Lire la suite » (`route-result.tsx`, `hitSlop`).

### Déploiement
- [docs/deployer.md](docs/deployer.md) (remplace `docs/heberger-oracle.md`) : coûts, Oracle Always Free pas à pas,
  Supabase, sauvegardes, surveillance, limites du gratuit, app téléphone ; §13 justifie de garder les images sur le
  disque du serveur plutôt que dans Supabase Storage.
- [deploy/](deploy/) : `installer.sh <domaine>` (Caddy HTTPS, service `surprise`, collecte de nuit à `--limit 50`,
  sauvegarde `pg_dump` chaque nuit), `deployer.sh` (mise à jour après un push), unités systemd, `Caddyfile`.
  `.gitattributes` force LF sur ces scripts.
- App mobile : [app/eas.json](app/eas.json) ; `app/app.config.js` lit `GOOGLE_SERVICES_JSON` (variable fichier EAS).
- README : lien vers le guide, note sur la réduction des images et le cache.

### Tests ajoutés
- `tests/test_deploy.py` : chaque `ExecStart` des unités passe par l'argparse du module (collecte à `--limit 50`, sans
  `--refresh`, enrichissement sans `--claude`, serveur sur 127.0.0.1 derrière le port du `Caddyfile`), scripts en LF
  et `bash -n`.
- `tests/test_quiz.py`, `tests/test_images.py` : en-têtes de cache, `lighter`.
- `app/tests/api/options.test.ts` : chargement unique, réessai.
- `app/e2e/fluidite.spec.ts` : 3 tests au format téléphone (bouton qui guide, bouton « en cours », connexion visible).

### État des tests
Au commit : pytest 395/395, Jest 89/89, e2e 16/16. `test_real_catalogue.py::test_a_couple_changes_a_step…` était instable (tirage `lucky()` sur la base de prod du jour) : graine fixée dans le test.

### Pas vérifié en vrai
- Les scripts `deploy/` n'ont pas tourné sur une vraie machine Oracle (syntaxe et cohérence avec le code seulement).
- Aucun build EAS : il faut le compte Expo de l'utilisateur.

### À faire côté utilisateur
- Retirer `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_SECRET_KEY` de `app/.env` : aucun code ne s'en sert, et ce fichier
  est copié sur le serveur.

### Message de commit proposé (si l'utilisateur dit oui)
Dans le style des commits récents (une phrase en anglais) :

> Faster and easier to use: the browser keeps the app's hashed scripts, fonts and images (a reload from 2.9 MB to
> nothing), a 20 KB logo instead of 1.6 MB, the evening form's options loaded from the home and tried again when the
> server does not answer, its button leading to the missing question instead of greyed, buttons saying what they do
> while the server works, the sign-in first on a phone, bigger touch targets; image copies resized to 1200 px (3 to 7
> times lighter), kept on the server rather than in Supabase Storage; and how to put it all online for free on Oracle
> Cloud (docs/deployer.md, deploy/: one command for HTTPS, the server and its emails, the nightly collection at
> --limit 50 and a nightly backup), EAS ready for the phone app

## 2. Décisions prises

- **Images : pas de Supabase Storage.** 5 Go de trafic par mois sur le plan gratuit, partagés avec toute l'app, contre
  10 To sur Oracle ; les images ne servent que jusqu'au jour de la soirée ; l'app a une image de secours ; la
  sauvegarde de nuit les couvre. À la place : réduction à 1 200 px et cache d'un mois.
- **Sous-ensemble des polices : écarté** (environ 25 % de gain seulement, une fois le cache en place).
- **Défilement vers la question manquante : mesuré au moment de l'appui** (`measureInWindow`). Sur le web,
  `onLayout` de react-native-web ne se déclenche que si la taille change, pas la position.

## 3. Les idées : ce que l'utilisateur a retenu

La liste complète (A1 à F M6) est dans le transcript de la session précédente. Retenues dans « Conçois ceci pour moi » :

- **A. Complicité** : 1 Question du jour (réponses scellées), 2 Quiz « Vous connaissez-vous vraiment ? » (série
  mensuelle), 3 Défis de la semaine (validés par les deux, points et badges), 4 Jauge vivante (paliers qui
  débloquent une option secrète, une intrigue spéciale, un thème), 5 Cartes du soir (gages pour Secret Squad).
  L'utilisateur demande aussi de **trouver des sources pour alimenter questions, défis et activités, et de les
  stocker en base**.
- **B. Dates** : 7 Dates qui comptent (3 semaines avant : email + notification avec 3 intrigues composées), 8 Conseils
  de saison (Fête de la musique, Nuit Blanche, Halloween, Noël ; email aux couples sans soirée prévue), 9 « Il y a un
  an… » (photo du Livre + « On remet ça ? »), 10 Météo (plan B couvert 48 h avant).
- **C. Routine** : 11 Programme « 4 semaines pour se retrouver », 14 Mode « Ce soir » (spontané, autour de soi, les
  3 heures qui viennent), 16 Bilan du lendemain (3 questions sur l'écran du Livre, qui affinent les goûts).

Sans réponse : A6, C12, C13, C15, D17 à D20, E21 à E25, et la monétisation M1 à M6. Proposé, pas encore demandé :
rédiger `docs/monetisation.md` une fois M1 à M6 choisis.

## 4. Prochaine étape : concevoir puis construire

Commencer par un document de conception, `docs/complicite.md`, à montrer à l'utilisateur, puis construire par phases,
chaque phase avec ses tests aux trois couches.

### Ce qu'il faut savoir du modèle actuel
- **Plus de table `couples`** (supprimée par `20261002000000_passager_per_evening.sql`) : les invités sont par soirée,
  dans `public.soiree_invites` (rôle `passager` ou `complice`), avec les fonctions `invited_to(sid, as_role)` et
  `organises(sid)`.
- `public.souvenirs` : le Livre, avec le principe du scellé (`sealed_by_me`) à réutiliser pour la question du jour.
- `public.gouts` : votes ±1 par activité, lus par la composition (`Request.tastes`), à réutiliser pour le bilan.
- `pipeline.courriers(soiree_id, moment, recipient)` : chaque email envoyé une fois, **toujours lié à une soirée**.
- Dernière migration : `20261012000000_courriers.sql`. Les suivantes en `20261013…`.
- Jauge actuelle : `app/src/lib/complicity.ts`, un point par soirée à deux vécue, 5 niveaux (Premiers regards → Âmes
  complices).
- Emails : `src/surprise/courriers.py` — `Moment` (l. 87), `plan()` (l. 140), `due()` 9 h–21 h (l. 250), `letter()`
  (l. 289), `run()` (l. 381).
- Plan B existant (une étape remplacée, le reste gardé) : `app/src/components/organiser.tsx:58`.
- `Request` de la composition : `src/surprise/parcours.py:131`. Il n'a **pas de point de départ** (lat/lon, rayon) :
  à ajouter pour le mode « Ce soir ».

### Pistes de conception (à valider dans le document)
- **Le duo** : `public.duos` qui relie deux comptes, créé quand un passager rejoint une soirée à deux (ou par un code
  depuis « Mon couple ») ; un duo par compte ; le quitter le supprime. Les questions, quiz, défis et la jauge s'y
  rattachent.
- **Tables de contenu** (lisibles par les comptes connectés, remplies par la migration) : questions du jour, questions
  de quiz (série par mois : souvenirs, rêves, goûts), défis de la semaine, cartes du soir (conversation / défi / gage,
  par formule et par rôle d'étape), saisons (dates fixes ; Nuit Blanche, date variable à saisir chaque année),
  programme 4 semaines (semaine → audace de la soirée, question, défi).
- **Sources du contenu** : textes originaux en français, écrits pour l'app, **inspirés** et non recopiés (droit
  d'auteur) de : Aron et al. 1997 (les « 36 questions », révélation progressive), Gottman (« love maps », rituels de
  connexion), la théorie de l'expansion de soi d'Aron (les activités nouvelles partagées rapprochent). Les citer
  comme inspiration dans le document.
- **Réponses** par duo, lues scellées ; défis validés par les deux ; manches de quiz.
- **Jauge** : des points pour les soirées, les pages du Livre scellées, les paires de réponses, les quiz, les défis ;
  paliers qui débloquent l'option secrète, l'intrigue spéciale, le thème. Étendre `complicity.ts`.
- **B7, B8, B9** : de nouveaux moments d'email **sans soirée** → une table d'envois à part, par exemple
  `pipeline.rappels(user_id, key, recipient)`, et `dates_cles` côté compte. B7 compose les 3 intrigues côté serveur.
- **B10** : Open-Meteo, 48 h avant, pour les étapes en plein air ; réutiliser le plan B. Open-Meteo est gratuit pour
  un usage **non commercial** : à revoir si la monétisation démarre.
- **C14** : `expo-location` (et la géolocalisation du navigateur), un point de départ et un rayon dans `Request`,
  début maintenant, fin dans 3 heures.
- **C16** : sur `app/src/app/livre.tsx`, les votes dans `gouts` et un moment préféré (colonne sur `souvenirs`).

### Phasage proposé
1. Document `docs/complicite.md`, puis migration : duo, tables de contenu et leur contenu, RLS.
2. A1 Question du jour + A4 Jauge vivante.
3. A2 Quiz, A3 Défis, A5 Cartes du soir.
4. B7 à B10 (moments côté serveur).
5. C11, C14, C16.

## 5. Règles du projet (rappel, voir CLAUDE.md)

- Toute fonctionnalité vient avec ses tests : `uv run pytest`, `npm test` dans `app/`, `npm run e2e`. Les trois passent
  avant un commit.
- Les tests lisent les activités de prod en lecture seule (`tests/prod_activities.py`) ; tout ce qu'ils écrivent va dans
  le Supabase local (`npm run db:start`), jamais en prod.
- Collecte toujours avec `--limit 50`. Enrichissement sans appel extérieur, `--claude` seulement sur demande.
- L'app marche sans clé Anthropic : les règles sont le vrai chemin.
- Site = l'app Expo construite pour le web ; le Python ne fournit que l'API et la modération.

## 6. Pièges rencontrés

- **e2e** : un serveur d'aperçu laissé sur le port 8011 sans `MAIL_SECRET` fait échouer `emails.spec.ts` (Playwright
  le réutilise). L'arrêter avant `npm run e2e`.
- **Lint React Compiler** (`react-hooks/refs`) : pas de lecture de ref pendant le rendu, ni d'objet de refs ; des
  `useRef` séparés et des gestionnaires en ligne.
- **Jest** : après un échec, attendre un tick avant de réessayer, sinon la promesse rejetée en vol est réutilisée.

## 7. Commandes

```bash
npm --prefix app run db:start
```

```bash
uv run pytest -q
```

```bash
npm --prefix app test
```

```bash
npm --prefix app run e2e
```
