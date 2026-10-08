# surprise

Tout lancer soi-même : double-cliquer sur `lancer.cmd` (serveur + app Expo), `collecte.cmd` (collecte, 200 fiches par source) ou `admin.cmd` (modération) ; détail dans
[docs/lancer-en-local.md](docs/lancer-en-local.md).

## Tests

```bash
# Python : collecte, composition, le parcours du couple par l'API (~45 s)
uv run pytest
# Dans app/, Docker Desktop ouvert : un Supabase local pour les comptes, puis les comptes et les notifications
# (Jest, ~20 s) et le site dans un navigateur (Playwright : compte, soirée, étape changée, passager invité, soirée
# Secret Squad, notifications push)
npm run db:start
npm test
npm run e2e
```

Les tests de l'API (`tests/test_real_catalogue.py`) et du navigateur composent sur les **activités de prod** : celles
du Supabase du projet (`SUPABASE_DB_URL` de `.env`, lu même sans `--env-file`), pour le vendredi qui vient, comme l'app
le propose. Elles sont lues par une connexion qui refuse toute écriture (`PostgresStore(read_only=True)`), puis gardées
12 h dans `data/tests/` (les lire prend une quinzaine de secondes) ; la base est recalculée à chaque lancement avec le
code du moment (filtres, tags, originalité). Comptes, soirées, candidats et vérifications restent dans le Supabase local
ou le store du test : rien n'est jamais écrit en prod, et aucun moteur de réservation n'est interrogé (pas de dîner :
il en faut une table confirmée en direct). Sans `.env` ni copie gardée, ces tests sont sautés et le site des tests ne
démarre pas. Pour relire la prod tout de suite :

```bash
SURPRISE_PROD_REFRESH=1 uv run pytest tests/test_real_catalogue.py
```

`npm test` reprend la réponse de `supabase status` (`node_modules/.cache`, revérifiée en une requête), et `npm run e2e`
ne refait le build web que si l'app ou ses variables ont changé (`E2E_REBUILD=1` pour le forcer).

## Collecteurs

```bash
# Que Faire à Paris : résumé des fiches retenues / rejetées (6 prochaines semaines)
uv run python -m surprise.collectors.que_faire_a_paris
# … dans Supabase (SUPABASE_DB_URL dans .env)
uv run --env-file .env python -m surprise.collectors.que_faire_a_paris --store supabase
# … ou hors ligne dans data/surprise.db (SQLite, ignoré par git)
uv run python -m surprise.collectors.que_faire_a_paris --store local
```

### Base

Tout le pipeline (payloads bruts, normalisation, modération, enrichissement, mots-clés, disponibilités) vit dans
Supabase : `public.raw_records` et le schéma privé `pipeline` (migration `20260929000000_pipeline_store.sql`), non
exposé aux clés de l'API. Les scripts Python s'y connectent en Postgres par `SUPABASE_DB_URL` ; sans elle, ils
retombent sur `data/surprise.db`, mêmes tables. L'hôte direct `db.<projet>.supabase.co` n'a qu'une adresse IPv6 :
prendre l'URL du *session pooler* (IPv4), `postgresql://postgres.<projet>:<mot de passe>@aws-0-eu-west-2.pooler.supabase.com:5432/postgres`.
Tous les scripts se lancent avec `uv run --env-file .env …` pour la lire.

```bash
# copie une base SQLite locale dans Supabase (seules les lignes absentes sont ajoutées)
uv run --env-file .env python -m surprise.local_store --db data/surprise.db
```

Ménage des activités passées (dernière séance, fin de période, ou rejet « passé ») que nul historique ne garde (étape
d'une soirée choisie, vote d'un compte) : pages brutes, fiche, modération, enrichissement, mots-clés, disponibilités, et
les étapes des soirées jamais choisies qui les montraient. Sans `--apply`, compte seulement, par source :

```bash
uv run --env-file .env python -m surprise.purge
uv run --env-file .env python -m surprise.purge --apply
```

Les migrations (`supabase/migrations/`) s'appliquent au Supabase du projet avec `supabase db push`, qui ne passe que
celles que son historique (`supabase_migrations.schema_migrations`) ne connaît pas encore. L'historique a été remis à
jour le 6 octobre 2026 (`supabase migration repair --status applied`, les 26 premières vérifiées une à une) : les
migrations d'avant avaient été passées à la main. Depuis `app/`, avec l'URL de `.env` :

```bash
uv run --env-file ../.env sh -c 'npx supabase db push --workdir .. --db-url "$SUPABASE_DB_URL" --dry-run'
```

Puis sans `--dry-run` si la liste est la bonne. À passer depuis le 8 octobre 2026 : `20261011000000_no_licenses.sql`
(plus de licence sur les sources ni les images) et `20261012000000_courriers.sql` (les emails).

### Collecte complète

`surprise.collect` lance les 30 sources, 4 à la fois (`--jobs`). Chaque source enregistre par lots de 50 fiches au
fil de l'eau, et une source en échec n'arrête pas les autres. Une page de détail encore fraîche n'est pas relue
et ne compte pas dans `--limit` : un nouveau passage à `--limit 50` lit 50 fiches de plus.
Le délai est donné par `FRESH_DAYS` dans chaque collecteur : 2 jours pour les événements (Shotgun, Dice, BilletRéduc,
Eventbrite, Fever), 14 pour les catalogues d'activités, 30 pour les lieux (OSM, hôtels, escape games, Time Out),
7 par défaut (médias). Ses payloads stockés (`_page`) sont renormalisés à la date du jour, sauf si le sitemap la dit
modifiée depuis (Paris ZigZag). Une page de réservation ou un site officiel n'est vérifié qu'une fois par mois
(`pipeline.page_checks`, migration `20260930000000_page_checks.sql`), et une fois par passage même si 46 concerts y
renvoient. Ces vérifications se font à 16 en parallèle, une seule à la fois par site. Nominatim reste à 1 requête/s ;
chacune de ses réponses (adresse trouvée ou lieu introuvable) est gardée 3 mois (`pipeline.nominatim_answers`, migration
`20261004000002_nominatim_answers.sql`) : une adresse n'est demandée qu'une fois, pas à chaque collecte ou
renormalisation. Un échec de Nominatim n'est pas gardé.

```bash
uv run --env-file .env python -m surprise.collect --limit 50
# certaines sources, en relisant tout, 20 min au plus chacune
uv run --env-file .env python -m surprise.collect --source fever --source tiqets --refresh --minutes 20
```

Paris ZigZag (média de curation : nom, lieu, dates, lien officiel, photo et texte de l'article ; ses listes pour
une bande d'amis, EVJF et karaokés, `paris_zigzag.GROUP_ARTICLES`, lues d'abord quel que soit leur âge) :

```bash
uv run python -m surprise.collectors.paris_zigzag --store local
```

Funbooker (annonces parisiennes), Paris-Friendly (bons plans, du plus récent au plus ancien) et Paris City Game
(annuaire d'activités) : faits, prix et photo de la page. `--limit N` arrête la collecte après N fiches :

```bash
uv run python -m surprise.collectors.funbooker --store local --limit 50
uv run python -m surprise.collectors.paris_friendly --store local --limit 50
uv run python -m surprise.collectors.paris_city_game --store local --limit 50
```

Come to Paris (billetterie : fiches produit en français, hors offres saisonnières et groupes) et Paris Secret
(média : cartes Fever et blocs pratiques des articles des 60 derniers jours, du plus récent au plus ancien) :

```bash
uv run python -m surprise.collectors.come_to_paris --store local --limit 50
uv run python -m surprise.collectors.paris_secret --store local --limit 50
```

Autres sources, chacune par sa voie la plus robuste (même options) :

| Source | Module | Voie |
|---|---|---|
| concerts.paris | `concerts_paris` | API JSON ouverte (feed GEO, 30 req/min) |
| Paris je t'aime (agenda) | `paris_jetaime` | API JSON ouverte `api.parisjetaime.com` |
| Paris je t'aime (billetterie) | `paris_jetaime_billetterie` | sitemap + état Nuxt de la page |
| VisitParisRegion | `visit_paris_region` | sitemap + HTML de la fiche |
| Explore Paris | `explore_paris` | liste des visites + HTML (séances datées), lieu par le métro sur OSM |
| Wecandoo | `wecandoo` | sitemap + JSON embarqué (`:page-props`) |
| Fever | `fever` | page Paris + schema.org Event |
| GetYourGuide | `getyourguide` | sitemaps d'activités + schema.org, point de rendez-vous |
| Tiqets | `tiqets` | sitemap produits + schema.org, lieu par le nom sur OSM |
| Civitatis | `civitatis` | sitemap + schema.org, point de rendez-vous (coordonnées) |
| Eventbrite | `eventbrite` | pages de recherche Paris (ItemList schema.org) + page de l'événement |
| Shotgun | `shotgun` | page Paris cumulative (`?page=N`, agrandie jusqu'à la fin) + schema.org MusicEvent, arrêt hors fenêtre |
| BilletRéduc | `billetreduc` | page Paris + schema.org Event |
| Time Out Paris | `time_out` | sitemaps (60 jours) + schema.org Review des lieux |
| Le Bonbon | `le_bonbon` | sitemaps + blocs pratiques des articles |
| Time Out Paris (hôtels) | `time_out_hotels` | sitemaps (toutes les pages `/paris/hotels/`) + schema.org Review, nom par le titre de la page, prix de la nuit dans le texte (sinon l'échelle €€€) ; gardé si son site passe par un moteur de réservation hôtelier (D-EDGE, SynXis, Mews, Reservit, Booking.com…) |
| Nuits en amoureux (Loveroomers, Love'nSpa, Love Île-de-France ; guides Love Room Guide, The Love Room, Cupiroom, Weekendlove) | `nuits_couple` | catalogues : une fiche schema.org LodgingBusiness par chambre (sitemaps Loveroomers, `products.json` Shopify de Love'nSpa, liens de la page Paris de Love Île-de-France) ; guides : une chambre par intertitre, lieu sur OSM |
| Articles « couple » (Hati Hati, Ryo, Love'n'Room, LoveCapsule, blog Funbooker, Petit Futé) | `selections_couple` | une idée par intertitre ou lien de réservation, lieu sur OSM |
| Articles « entre potes » (Topito, Le Bonbon, Paris ZigZag : bars à jeux, karaokés, bars d'anniversaire, restos festifs, activités entre amis) | `selections_squad` | comme les articles « couple » ; le lieu d'un intertitre qui le décrit (« PAN, le premier bar à tir », « Le plus tardif : la Noche à Pigalle », « Miami Boulevard — Paris 1 »), celui d'une fiche Funbooker ou Privateaser liée, sinon OSM |
| Privateaser | `privateaser` | liste des bars à réserver à Paris (`?page=N`, jusqu'à une page sans nouveau bar) + microdonnées schema.org du bar (adresse, coordonnées, horaires) et ses formules avec leur jauge (« Réserver quelques tables 1-440 personnes ») : la plus petite et la plus grande bande qu'il prend ; réserver des tables est gratuit, la réservation elle-même (`/booking/`) est fermée aux robots, donc pas vérifiée ; dix secondes entre deux pages (son CloudFront bloque en 403 un robot plus rapide), arrêt après trois pages sans réponse |
| Restaurants OpenStreetMap | `osm_restaurants` | Overpass (restaurants de Paris avec site) + site du restaurant : gardé s'il passe par un moteur de réservation (Zenchef, SevenRooms, TheFork…), sur sa page ou sa page « Réserver » |
| Sortir à Paris | `sortir_a_paris` | d'abord les articles de ses guides pour une bande d'amis (EVJF, EVG, anniversaire entre adultes, bars karaoké : `GUIDES`, environ 175 articles), quels que soient leur rubrique et leur âge ; puis les sitemaps (60 jours) des rubriques insolite, soirées, spectacles, gaming, Halloween et bars + bloc « Informations pratiques » (microdonnées schema.org Place, dates, tarifs, site officiel, réservation) ; articles sans lieu écartés |
| Dice | `dice` | sitemaps : événements de Paris (adresse en « -paris-tickets ») de la fenêtre, par le jour de leur adresse + schema.org MusicEvent ; une soirée qui finit après 2 h est du clubbing |
| EscapeGame.fr | `escape_game` | sitemap des salles de Paris (escape games, action games, réalité virtuelle, expériences immersives) + fiche HTML (joueurs, durée, prix, adresse, bouton « Réserver » vers le site de l'enseigne) ; salle à 3 joueurs minimum écartée |
| Loisirs OpenStreetMap | `osm_loisirs` | Overpass (karaoké, lancer de hache, laser game, réalité virtuelle, bowling, mini-golf, trampoline, hammam, escalade, piscine ; bars à fléchettes ou billard) + site du lieu comme pour les restaurants ; la nature du lieu dans le titre (« Escalade : Arkose ») ; bars gardés sans réservation |

Sans collecteur : Que faire à Paris (paris.fr) est déjà l'open data collecté, Weezevent n'a pas de catalogue
public (reconnu comme billetterie), Fnac Spectacles ne répond pas aux robots, Le Petit Journal n'a pas d'édition Paris.
Les données manquantes (code postal d'un point de rendez-vous, d'un lieu nommé) viennent d'OpenStreetMap (Nominatim).

Si `opendata.paris.fr` ne résout pas (DNS d'entreprise), passer par le miroir Opendatasoft :

```bash
OPENDATA_PARIS_URL=https://parisdata.opendatasoft.com uv run python -m surprise.collectors.que_faire_a_paris
```

Seules les activités gratuites ou réservables en ligne sont gardées : lien de réservation (ou site officiel, ou sa
page « Réserver ») menant à une billetterie ou un moteur de réservation reconnu (`surprise/booking.py`). Les autres
sont rejetées avec le motif « ni gratuit ni réservable en ligne » : elles restent en base, à part dans la modération
(onglet « Écartées à la collecte »), pour affiner les règles ou en repêcher. Exception : bars, clubs et restaurants sont gardés
tant qu'ils sont ouverts (rejet « fermé définitivement » si la source ou le site le dit), marqués « Non réservable »
quand ils n'ont pas de réservation en ligne. Comptent aussi comme réservation en ligne : une page billetterie du site
du lieu (« …/fr/tickets/… »), et le formulaire d'un organisateur (Google Forms, Tally…) sur une page qui demande de
réserver ou de s'inscrire. Sur Paris ZigZag, la page officielle d'un bloc pratique est le lien qui nomme le lieu ou le
spectacle ; sa billetterie est suivie de là.

Chaque fiche gardée dit comment elle se réserve (`activity.booking`, badge en modération) : `gratuit`, `creneau`
(un moteur donne les créneaux d'une date : Funbooker, Wecandoo, Come to Paris, Zenchef, SevenRooms, 4escape ; avec
l'identifiant du lieu chez lui, `check` = « zenchef:351778 », trouvé dans le lien, la page ou sa page « Réserver » ;
pour Funbooker, l'identifiant et les formules de l'annonce, lus une fois sur son API et gardés un mois avec les
vérifications de pages : une soirée ne demande que les créneaux, pour 2 comme pour un groupe),
`billetterie` (réservable en ligne, créneaux non vérifiables) ou `sans_resa` (bar, club, restaurant sans réservation
en ligne). Les soirées ne vérifient en direct que les `creneau`, sans relire le site du lieu. Rattrapage des fiches
collectées avant (relit une fois les pages Zenchef, SevenRooms et 4escape, pour leur identifiant) :
`uv run --env-file .env python -m surprise.renormalize --source <id>`.

Tous les motifs de rejet d'une fiche sont gardés (« jeune public · passé »), un badge chacun dans la modération : la
fiche est construite quand même, sauf si un motif l'en empêche (sans nom, sans lieu, hors zone, invalide, page
illisible). Celles-là apparaissent aussi dans « Écartées à la collecte », avec leur titre et le lien de la source,
sans pouvoir être validées. La réservation n'est vérifiée que pour une fiche sans autre motif (pas de requête perdue).

Zone : Paris et la proche banlieue qu'atteint le métro (`METRO_TOWNS` dans `surprise/models.py` : Boulogne, Montreuil,
Saint-Denis, Vincennes, Ivry…) ; ailleurs, rejet « hors Paris et proche banlieue ». Les parcours gardent au plus 35 min
de trajet entre deux étapes.

Règles changées : `uv run python -m surprise.renormalize --rejet "<motif>"` (ou `--source <id>`) normalise de nouveau
les pages déjà collectées, puis revérifie la réservation, sans rien recollecter. `--rejet` prend les fiches qui ont ce
motif parmi les autres. Les fiches passent à 32 en parallèle, une page à la fois par site, enregistrées par lots de 200 :
un passage interrompu garde ce qu'il a fait.

## Enrichissement

Images et descriptions courtes des activités collectées (seules les nouvelles sont traitées) :

```bash
uv run python -m surprise.enrich
```

- Image : photo de la source, sinon `og:image` du site officiel, sinon Google Places si `GOOGLE_PLACES_API_KEY`
  est définie (seul l'identifiant du lieu est stocké, la photo est chargée à l'affichage avec son crédit).
- Lieu : coordonnées, horaires et, s'il manque, adresse depuis OpenStreetMap, cherchés par nom puis par distance
  ou code postal : d'abord dans les lieux nommés de Paris téléchargés une fois par semaine depuis Overpass
  (`data/osm_paris.json`), sinon par Nominatim (1 requête/s). La réponse de chaque lieu est gardée 3 mois
  (`pipeline.osm_places`, migration `20260930000001_osm_places.sql`). Un événement qui a déjà ses coordonnées
  s'en passe : les horaires du lieu ne disent rien de ses dates.
- Réservation : lien « Réserver » du site officiel si la fiche n'en a pas ; si le lien de la fiche mène à la page
  du spectacle sur le site du lieu, son bouton « Acheter » vers la billetterie.
- Description : par défaut, sans appel extérieur, les premières phrases (280 caractères au plus) du texte de la
  source (`lead_text` : texte de la fiche ou de l'article), sinon de l'extrait du
  site officiel, nettoyées (balises, titre de page, listes, emojis) ; `description_model` vaut alors `extrait`.
  Avec `--claude`, rédigée par Claude (`ANTHROPIC_API_KEY`, modèle `SURPRISE_LLM_MODEL`, `claude-opus-5-5` par
  défaut). Une activité déjà enrichie ne reçoit que sa description, sans rien télécharger.

`--refresh` retraite aussi les activités déjà enrichies, `--source` limite à une source, `--no-descriptions`
se passe des descriptions.

Images qui ne s'affichent pas (lien mort, refus d'être montrées sur un autre site) :

```bash
uv run --env-file .env python -m surprise.images
```

Chaque image est demandée comme le ferait un navigateur depuis l'app, une à la fois par site. Une image morte est
remplacée par l'`og:image` du site officiel si celle-ci s'affiche, sinon notée morte (`pipeline.page_checks`,
moteur `image`, revue après un mois) : l'activité n'est plus proposée dans les parcours. Les images vérifiées il y a
moins d'un mois sont passées (`--refresh` pour tout revoir). Les parcours vérifient en plus les images de leurs étapes
avant de les proposer, de la même façon : une image morte y est d'abord remplacée par celle du site officiel ;
sans elle, ou si l'image ne répond pas, l'étape est remplacée.

À l'essai, ces filtres sont coupés (`IMAGE_FILTERS = False` dans `surprise/parcours.py`) : une activité sans photo, ou à
la photo morte, peut être proposée, et l'app montre alors sa bannière (ci-dessous). `True` les remet.

Dans l'app, une image d'étape qui ne charge pas est redemandée après 2 s, puis signalée au serveur
(`POST /api/images/broken`), qui la revérifie et la remplace ou la note morte de la même façon ; à défaut, l'étape
montre une bannière de l'app selon son genre, jamais un blanc. Les images d'une soirée gardée sont copiées dans
`data/images` au moment du choix et servies de là : elles tiennent jusqu'au jour J.

## Tags et vibes

`surprise/tags.py` décrit chaque activité par des **tags** précis (mini-golf, céramique, rooftop, aux chandelles…),
en trois facettes : activité, cadre, moment. Les tags donnent les **vibes**, les envies larges du questionnaire client
(Bouger, Relever un défi, Rire, Créer, Savourer, Se détendre, S'émerveiller, Vibrer en musique, Faire la fête,
Se cultiver, Prendre l'air, Frissonner, L'insolite, Pimenter, Romantique) : un mini-golf est « Bouger » et « Relever un défi ».
Calculés à la lecture par des règles sur le titre et le lieu (plus les catégories), ils s'affinent sans recollecter ;
la modération les affiche et filtre par vibe.

Un spectacle qui porte un repas dans son titre (« Dîner De Famille », « Le Dîner de cons ») n'est pas un dîner. Le texte
le dit : une catégorie de scène (théâtre, humour, spectacle, cabaret, concert), ou « théâtre », « comédie »,
« spectacle », « stand-up », « mise en scène »… dans le titre, le lieu ou la description. Il perd alors le tag « dîner »,
donc la vibe « Savourer », et la composition en fait une sortie. Exceptions : un restaurant reste un restaurant, et un
spectacle dont le texte dit que le repas est compris (dîner-spectacle, dîner & revue, « dîner compris ») garde son repas.

```bash
uv run python -m surprise.tags --untagged   # couverture par tag et vibe, activités sans vibe
```

## Mots-clés et originalité

`surprise/keywords.py` relève dans tous les textes d'une activité (titre, lieu, texte de la source, extrait du site,
description) les mots qui disent son ambiance, en facettes : ambiance (intimiste, secret, rétro…), cadre (vue
panoramique, cave voûtée, au bord de l'eau…), expérience (immersif, fait main, en duo…), moment, cuisine. Ils sont
stockés (table `keywords`) et affichés en modération et dans les parcours.

`surprise/originality.py` note chaque activité de 0 (vue partout) à 100 (une histoire à raconter), avec ses raisons :
cadre ou expérience insolite, rareté de son genre dans la base, mots-clés (« secret », « éphémère »…), repérage par un
média de curation ; pénalités pour les classiques touristiques, les grandes salles, les chaînes. Calculé à la lecture ;
la modération le montre et trie dessus, les parcours le pondèrent par l'audace du couple.

```bash
uv run python -m surprise.keywords       # calcule et enregistre les mots-clés
uv run python -m surprise.originality    # répartition, les plus originales et les plus classiques
```

## Disponibilités

Vérifie pour une date si les activités de la base locale sont réservables à 2 (créneaux horaires et formule),
sans compte : Funbooker, Wecandoo, Come to Paris, Zenchef, SevenRooms et 4escape, celles dont la collecte a trouvé le
moteur et l'identifiant (`booking.check`). Bookeo n'est pas vérifiable (captcha). Les activités rejetées en modération et
celles sans moteur pris en charge sont ignorées.

```bash
uv run python -m surprise.availability 2026-10-09
uv run python -m surprise.availability 2026-10-09 --source funbooker --party 4 --limit 10
```

## Parcours de soirée

À partir d'une date, d'un budget approximatif pour deux, d'une plage horaire et d'envies (vibes), propose trois
soirées différentes, chaque étape enchaînable (durée, trajet à pied ou en métro, attente courte) et gratuite ou
réservable ce soir-là :

```bash
uv run python -m surprise.parcours 2026-10-09 --budget 150 --de 19:00 --a 00:30 --vibes romantique,musique,savourer
```

- Étapes retenues : séance datée ce soir-là avec billetterie (séances concerts.paris, Que Faire à Paris, Shotgun…),
  créneau libre pour 2 vérifié en direct (Funbooker, Wecandoo, Come to Paris, Zenchef, SevenRooms, 4escape ; réponses
  gardées 6 h, enregistrées en une écriture ; au plus 5 vérifications par moteur et par soirée, les meilleures, 2 pour
  Come to Paris qui interroge son site 3 ou 4 fois par vérification, chacune dans sa session : un moteur est interrogé
  toutes les demi-secondes, ses vérifications se suivent, alors que celles de moteurs différents vont ensemble),
  lieu gratuit ouvert à cette heure, ou bar / club sans réservation (marqué comme tel, `--strict` les
  exclut). Un dîner n'est proposé qu'avec une table confirmée ; une pièce « jusqu'en décembre » sans ses dates, jamais.
- Choix : envies demandées, romantisme, originalité (sources de curation, lieux insolites), photo ; une pièce ou un
  stand-up ordinaire (originalité < 45) passe après l'insolite, d'autant plus que le couple est audacieux (sauf le
  stand-up quand il veut rire) ; budget au plus +20 % ; pas deux sorties du même genre ; trois parcours sans étape ni lieu communs, dans des quartiers différents.
- Trame imposée et plusieurs soirs : `--trame apero,insolite,fete` fixe les étapes dans l'ordre (`apero`, `diner`,
  `fete` ou une vibe), `--parcours N` le nombre de parcours, plusieurs dates les répartissent sur ces soirs (sans
  étape commune), `--trajet-max` borne les trajets. Un bar d'apéro peut être écourté (45 min au moins) pour attraper
  une séance ; on reste en club jusqu'à la fin de la soirée. `--decoucher` finit chaque parcours dans une chambre
  (catégorie `hotel` : hôtels Time Out, love rooms) à 30 min au plus de la dernière étape, de préférence dans le
  budget de la nuit, romantique ou insolite, jamais la même pour deux parcours. La nuit a son propre budget, ajouté à
  celui de la soirée : `--budget-nuit`, sinon 1,5 fois `--budget` (entre 120 et 600 €) ; une chambre ne le dépasse pas
  de plus de 20 %. Son prix s'affiche à part (« + 180 € la nuit »).
  Une chambre n'est jamais une étape de la soirée elle-même :

  ```bash
  uv run python -m surprise.parcours 2026-10-02 2026-10-03 2026-10-09 2026-10-10 --budget 150 --de 19:00 --a 04:00 \
    --vibes insolite,fete --trame apero,insolite,fete --parcours 10 --trajet-max 30
  ```
- `--checks N` : vérifications en direct au plus (60 par défaut, 0 = cache seul), huit à la fois, chaque site
  interrogé au plus toutes les demi-secondes. Titres et pitchs par règles, sans IA : ce qu'est chaque étape et le
  quartier (« Jeux d'adresse et danse le long du canal Saint-Martin »), puis la soirée pas à pas avec trajets et prix.
  Si `ANTHROPIC_API_KEY` est définie, Claude les réécrit en arrière-plan (`--no-claude` sinon) : la page s'affiche
  aussitôt et se recharge sur ses titres, après une composition comme après un redessin. Le questionnaire charge les activités à son démarrage et les recharge en arrière-plan toutes les
  15 minutes.
- Affichage : dans l'app (`/soiree?soiree=<nom>`, ouverte à la fin ; le serveur `surprise.quiz` doit tourner) —
  trois frises (photos, horaires, trajets vers Google Maps, bouton « Réserver » sous chaque étape).
- Régénérer : l'app propose
  « ↻ Tout le parcours » (une autre soirée, différente des deux autres) et « ↻ Changer » sur chaque étape (une autre
  activité du même rôle ou de la même étape de la trame, qui s'enchaîne avec ses voisines ; un bar voisin est écourté
  ou prolongé). Une étape changée ne ramène jamais une activité déjà proposée sur la page, même vendue sous une autre
  fiche (même titre) : quand les candidats gardés sont épuisés, le serveur en cherche d'autres (`more_candidates` :
  les moteurs de réservation interrogés pour des activités du même rôle pas encore vérifiées ce soir-là, jusqu'à
  `SEARCH_ROUNDS` tours), puis répond « plus d'autre activité qui s'enchaîne à cette étape ce soir-là » (409, affiché
  par l'app) plutôt que de tourner en rond. Un parcours redessiné cherche de même, puis se rabat sur celui qui reprend le
  moins d'activités déjà vues. Tant qu'aucun parcours n'est choisi, la régénération
  part des candidats gardés à la composition (`pipeline.soiree_candidates`, 6 h au plus, un nouveau tirage de hasard
  à chaque fois, ceux trouvés en cherchant ajoutés) : ni relecture de la base, ni vérification en direct tant qu'ils
  suffisent. Une fois un parcours gardé
  (`POST /api/parcours/<nom>/routes/<i>/choose`), la soirée n'a plus que lui (route 0, les autres et les candidats
  effacés) et son nom suffit à la retrouver (`/revelation?soiree=<nom>`) ; changer une étape ensuite revérifie en
  direct. Les parcours sont gardés
  dans la base, lisibles en SQL (migration `20260930000002_profiles_soirees.sql`) : `pipeline.soirees` (le nom de
  la page pour identifiant, la demande), `pipeline.soiree_routes` (titre, pitch, score de chaque parcours) et
  `pipeline.soiree_steps`, chaque étape liée à son activité (`source_id`, `external_id`) avec ses horaires et
  l'activité telle qu'elle était (`step`) ; une étape régénérée y reste, marquée `replaced_at`. Les activités déjà
  proposées sont celles de ces étapes.
- Images : BilletRéduc interdit l'affichage de ses affiches ailleurs que chez lui (`Cross-Origin-Resource-Policy`) ;
  elles sont copiées une fois dans `data/images` (800 px) et servies de là, en modération comme dans les parcours.

Vibes possibles : bouger, defi, rire, creer, savourer, detente, emerveiller, musique, fete, cultiver, flaner,
frisson, insolite, coquin, romantique. « Pimenter » (tag `coquin` : burlesque, effeuillage, Crazy Horse,
pole dance, visite érotique…) est une envie de soirée ; « Le coquin, l'effeuillage » peut être refusé dans le profil.

## Questionnaire client

Douze questions ludiques sur ce qui dure (où en est le couple, énergie, ce qui fait une soirée réussie, audace,
assiette, musique, fin de soirée habituelle, ce qu'on ne veut jamais, budget, jour de la première sortie, prénoms)
dessinent le profil du couple : vibes pondérées, persona (« Les Explorateurs », « Les Épicuriens »…), audace, refus,
genres préférés, envie d'un dîner, budget. Aucune heure précise n'est demandée. Profil et réponses sont stockés
(`pipeline.profiles`).

« Sur quelles musiques vibrez-vous ? » (autant de genres qu'on veut, ou aucun) filtre les concerts et soirées club
(`surprise.genres`) : le genre vient de la source quand elle le dit (concerts.paris), sinon du titre et du lieu, puis
des textes. Un concert d'un genre non coché est écarté ; un concert au genre non reconnu reste proposable ; les
concerts classiques (Candlelight…) restent toujours possibles, pour une occasion.

Chaque soirée se prépare à part, sur sa propre page (`/soiree`, avec `#p=<profil>` ou sans profil) : jusqu'à trois
envies (« Faire la fête », « Cocooning », « Romantique », « Surprenez-nous »…), si l'on dîne ou pas (obligatoire :
« on aura déjà mangé » écarte les formules repas — dîners-croisières, dîners-spectacles, restaurants — mais garde
les bars, caves, bars à vins, planches et rooftops pour boire un verre, et les concerts d'un club-restaurant),
« Et après ? » (rentrer, ou découcher : la soirée finit dans un hôtel ou une love room proche, voir `--decoucher`), une
occasion éventuelle et le jour.
Les envies se mêlent : chacune apporte ses vibes à tour de rôle, la soirée commence à l'heure la plus tôt et finit à
la plus tardive, et ce qu'une envie écarte revient si une autre le demande (cocooning puis fête : le club reste).
Les refus, le budget, l'audace et les goûts sont ceux du profil, ou des réglages par défaut sans profil. Les refus
(« être en maillot de bain », « le vide », « la foule »…) visent des tags, des mots-clés ou des catégories.

Sur chaque étape proposée ou gardée, l'instigateur vote d'un pouce : « on aime ce genre » ou « pas pour nous »
(table `gouts`, migration `20261006000000_gouts.sql`, un vote par activité et par compte, revus et retirés depuis le
compte). Chaque nouvelle soirée les envoie (`votes`) : le genre d'une activité (ses tags « activité », sinon ses
catégories) gagne 1 point par vote pour (2,5 au plus) et en perd 2 par vote contre (5 au plus) ; à −2 net (deux « pas
pour nous »), il n'est plus proposé. L'activité votée contre elle-même ne revient jamais (`surprise.parcours.taste`).

```bash
uv run python -m surprise.quiz    # http://127.0.0.1:8001
uv run python -m surprise.quiz --host 0.0.0.0    # + accessible depuis un téléphone sur le même Wi-Fi
```

Un seul site, qui est l'app : le serveur sert le build web de l'app Expo (`app/dist`, `npm run build:web` dans
`app/`, refait par `lancer.cmd` à chaque lancement), l'API qu'elle appelle (`/api/…`) et la modération (`/admin`).
Il n'y a pas d'autre page client : toute évolution se fait dans `app/` et vaut pour le téléphone comme pour le site.
Le build web appelle l'API sur sa propre adresse ; en développement (`npm run web`, port 8081), sur
`EXPO_PUBLIC_API_URL`.

En développement, l'app sur 8081 a besoin du serveur 8001 : sans lui, une soirée affiche « L'enveloppe reste
close ». Lancé depuis le volet navigateur de Claude, il s'arrête dès que son onglet est fermé ; le lancer plutôt
dans un terminal à part, qui le garde tant qu'il reste ouvert :

```bash
uv run --env-file .env python -m surprise.quiz --no-open
```

Le site sur 8001 sert `app/dist` tel qu'il a été construit : après une modification de l'app, refaire
`npm run build:web` dans `app/` pour qu'il suive (8081, lui, lit le code en direct).

## Compte client et historique

L'app demande un compte (email + mot de passe, Supabase Auth) avant tout le reste : sans être connecté, seul
`/compte` s'affiche. Le compte garde le profil et l'historique des soirées vraiment réalisées (celle choisie parmi
les trois parcours proposés) sur n'importe quel appareil. Le navigateur parle directement à Supabase avec la clé
anon ; la sécurité (chacun ne voit que ses données) vient uniquement des policies RLS des migrations
(`couple_profiles.user_id`, table `soirees_choisies`) — il n'y a pas de code serveur entre les deux.

L'instigateur fait le profil, commande les soirées, voit la feuille de route et coche ses réservations
(`save_booked`, colonne `soirees_choisies.booked`) ; il invite un passager par soirée, un seul au plus pour un couple
(table `soiree_invites`, lien `invite_code` de `soirees_choisies`), par un lien depuis la révélation de la soirée
(`/invitation?code=…`, fonction `join_evening`) ; une autre soirée peut avoir un autre passager (`reset_passager` le
renvoie et renouvelle le lien). Une soirée Secret Squad (plus bas) a toute une bande d'invités. Le passager a son
propre compte, ne voit que le compte à rebours, les indices et le programme voilé des soirées où il est invité ; chaque
étape voilée porte un mot mystère (« Vertige », « Gourmandise »… tiré de ses ambiances, `stepWords` dans
`app/src/lib/clues.ts`), le premier dès le départ, les autres au fil des derniers jours. À son tour, il peut faire le
quiz et composer ses propres soirées (« À votre tour de surprendre ») : il en est l'instigateur, et `join_evening`
accepte un compte qui garde déjà des soirées (migration `20261005000000_passager_composes.sql`). Un compte passager
d'au moins une soirée est passager (accueil et barre du bas), tout autre est instigateur ; chaque soirée s'affiche du
côté du compte (`eveningRole`).
L'instigateur peut supprimer une soirée passée (Mes soirées, livre et photos avec) et chacun son compte
(`delete_my_account`, photos retirées avant). Limite connue : le passager pourrait lire les données d'une soirée par
l'API (l'app seule les voile).


### Secret Squad : une soirée entre potes

Au début de chaque commande (`/soiree`), deux formules : **Secret Date**, à deux, et **Secret Squad**, entre potes (EVJF,
EVG, anniversaire, pot de départ, retrouvailles, sortie d'équipe, ou juste l'envie). La même mécanique, son propre look :
la palette « Néon de minuit » (nuit bleu asphalte, orange néon, l'or champagne de la marque ; `Palettes.squad` de
`app/src/constants/theme.ts`, posée par `<PaletteProvider name="squad">` sur la commande, l'accueil, la révélation, le
livre et l'historique de la soirée), la boule à facettes à la place de l'émeraude (`components/disco-ball.tsx`), le
badge « Squad », et ses mots (« la bande » où un couple dit « votre passager » ; indices, mots mystères, notifications,
widget, carte postale et carton en tiennent compte).

- **Combien** : de 2 à 10, l'instigateur compris (`quiz.SQUAD_PERSONNES`) ; à deux, une soirée avec un pote,
  pas un date : les prix restent par personne, les offres pour un couple écartées. Mesuré le 6 octobre 2026 sur 48
  activités réservables en ligne : 27 acceptent 2 personnes, 26 en acceptent 6, 16 en acceptent 10, 9 seulement 12.
  Chaque vérification de disponibilité demande pour la bande entière (`Request.party`).
- **Ses envies et occasions** (`quiz.SQUAD_ENVIES`, `SQUAD_OCCASIONS`, `GET /api/soiree?formule=squad`) : trinquer,
  chanter à tue-tête, se défier entre potes… ; plus de romantique, de cocooning ni de love room (la bande rentre). Un
  EVJF/EVG favorise les offres faites pour (tag `evjf`), chanter favorise karaoké et quiz. Les vibes ont leurs mots de
  bande (`SQUAD_VIBE_LABELS` : « Fous rires », « Défis entre potes »…).
- **Le budget** se donne par personne (moins de 30 €, 30 à 60 €, 60 à 100 €, on ne compte pas ; 60 € sans choix) ;
  chaque prix compte la bande (`parcours.price_for` : par personne × N, par couple × N/2, par groupe une fois), et
  l'app affiche la part de chacun.
- **Le choix des activités** (`parcours.affinity`) : ce qui se partage (quiz, karaoké, escape game, murder party, jeux,
  danse, dégustations…) compte là où la romance compte pour deux. Une offre pour deux dans son titre (massage en duo,
  love room) n'est jamais proposée à une bande ; une offre EVJF/EVG jamais à un couple ; une activité n'est proposée
  qu'à son nombre de participants (`Activity.players_min/max` : les joueurs d'un escape game, la jauge d'une fiche
  Funbooker, « De 4 à 10 personnes » ; « Une personne » n'y dit rien, une dégustation réservée place par place l'affiche
  aussi). À partir de 6, un bar sans réservation pèse moins.
- **Le profil du couple ne s'applique pas** (`quiz.squad_profile`) ; les votes et les soirées déjà faites, si.
- **Les invités** (migration `20261007000000_secret_squad.sql`) : `soirees_choisies.formule` et `personnes`, table
  `soiree_invites` (passagers et complices, pour les deux formules ; un couple n'a qu'un passager), deux liens par
  soirée de bande : celui des invités (`invite_code`, les indices seulement, un seul lien pour tout le groupe) et
  celui des complices (`soiree_codes`, que seuls l'instigateur et les complices lisent), qui voient tout le programme
  et cochent les réservations (les témoins d'un EVJF). `join_evening` refuse au-delà des places ; l'instigateur
  retire un invité, un invité peut partir. Le livre a autant de pages que la bande. La jauge de complicité ne compte
  que les soirées à deux.

```bash
# une soirée Secret Squad en ligne de commande : huit, 400 € pour toute la bande
uv run --env-file .env python -m surprise.parcours 2026-10-16 --squad 8 --budget 400 --vibes rire,fete
```

Une soirée gardée prend un nom secret, vu des deux (« Le Pacte de l'Île Saint-Louis ») : un mot d'intrigue tiré de
son ambiance et le quartier de son étape la plus centrale, jamais un lieu (un quartier qui porte le nom d'un lieu de la
soirée est sauté). Règles sans Claude (`parcours.secret_title`), envoyé avec chaque parcours (`secret_title`) et figé
à la garde dans `soirees_choisies.secret_title` (migration `20261001000003_secret_title.sql`).

Le Livre des Secrets (`/livre?soiree=…`) : en fin de soirée (sa dernière étape commencée) puis les jours
suivants, chacun des deux scelle une page — une photo, un mot (table `souvenirs`, photos dans le bucket privé
`souvenirs`, lues par liens signés). Scellée, une page ne se modifie plus ; on ne lit celle de l'autre qu'après avoir
scellé la sienne (fonction `sealed_by_me`). Mes soirées (`/historique`) n'en montrent plus que la photo et les
notes, le long d'un fil d'or, de plus en plus patinées avec l'âge ; le parcours n'y apparaît plus.

Les notifications (`app/src/lib/story.ts` pour ce qu'elles disent, `notifications.ts` pour leur programmation) : sur
le téléphone seulement (rien sur le web), programmées sur l'appareil, sans serveur, d'après les soirées du compte (à
venir et du dernier mois). Le passager vit sa semaine en chapitres, sur un compte à rebours :
- le pli scellé à J-7 (le jour et l'heure, rien d'autre) ;
- un indice chaque matin à 9 h (« J-3 · La garde-robe ») et les mots mystères l'après-midi ;
- la veille au soir, puis le jour J en crescendo (« H-2 · Le compte à rebours », « H-1 · Le départ ») ;
- chaque voile qui se lève, son mot mystère devenu un nom (« « Velours » prend un nom : … ») ;
- le lendemain, le Livre des Secrets ; quatre jours après, « À votre tour » (sauf si une autre soirée est déjà gardée).

L'instigateur reçoit :
- les réservations encore à faire (J-6, J-3, J-1, jusqu'à ce qu'elles soient cochées) ;
- l'invitation pas encore envoyée (J-5, J-2) ;
- une fois le passager arrivé, chaque indice du matin quand il le reçoit (« Dans l'ombre ») ;
- la veille, l'heure du départ, puis l'heure de partir vers chaque étape suivante ;
- le lendemain, le livre et les pouces ; trois semaines après, la prochaine intrigue (sauf si une autre soirée est déjà gardée).

Rien entre 22 h et 9 h, sauf pendant la soirée elle-même. Ce qui tombe à moins de 20 min d'écart part en une seule
notification. Au plus 60 notifications sont programmées (iOS en garde 64).

Tout est reprogrammé au retour dans l'app et à chaque changement (soirée gardée, réservation cochée, plan B, mode de
dévoilement), et effacé à la déconnexion ; hors ligne, rien ne bouge. Toucher une notification ouvre sa page. Les
coulisses de l'instigateur montrent la semaine du passager telle que son téléphone la dira.

Limites : le téléphone du passager n'apprend un changement (plan B, mode) qu'en rouvrant l'app ; les emails et les pushes
web (ci-dessous) partent, eux, du serveur. L'icône Android des notifications (monochrome) reste à fournir avant
publication.

### Emails (et pushes web) des soirées

`surprise.courriers` envoie par email, en plus des notifications, les moments clés de chaque soirée gardée, et les mêmes
en push aux navigateurs qui l'ont accepté (sur le web, aucune notification locale ne sonne ; les téléphones gardent les
leurs) :
- **l'instigateur** : la soirée gardée (ses réservations à faire, avec leurs liens, et le lien d'invitation tant que
  personne n'a rejoint), les réservations encore à faire à J-3 (18 h), l'invitation pas encore envoyée à J-2, le Livre
  des Secrets le lendemain, et trois semaines après, la prochaine intrigue (sauf si une autre soirée est gardée) ;
- **le passager** : le pli scellé à J-7 (le jour et l'heure, rien d'autre ; tout de suite s'il rejoint plus tard), la
  veille, le Livre des Secrets, et à J+4 « À votre tour » (sauf s'il a composé une soirée depuis) ;
- **les complices** d'une soirée de bande : les réservations encore à faire et le Livre des Secrets ;
- **une adresse donnée dans l'app** : l'invitation par email (carte « Votre passager » ou « Votre bande », champ
  « Ou par email »), tout de suite. Fonction `invite_by_email` : l'instigateur seul (ou un complice, pour le lien des
  invités), une adresse valide, une soirée à venir, au plus 20 par jour et par compte et quelques-unes par soirée
  (migration `20261012000000_courriers.sql`).

Chaque moment part une fois (`pipeline.courriers`), entre 9 h et 21 h (sauf une invitation), tant qu'il a un sens. Personne
ne reçoit ce qu'il a arrêté : Mon compte › Emails (`public.email_prefs`), ou le lien en bas de chaque email
(`/compte?stop=…&t=…`, signé par `MAIL_SECRET`, aussi en un clic depuis la messagerie, `List-Unsubscribe`, vers
`POST /api/courriels/stop`), qui note l'adresse (`pipeline.courriels_stop`). Les emails ont leur texte et leur HTML, aux
couleurs de la nuit et de l'or ; leurs liens mènent à l'app (`APP_URL`), ceux des réservations sont des liens partenaires
quand un programme est configuré (plus bas, « Liens partenaires »).

Le connecteur est le SMTP de n'importe quel fournisseur (Brevo, Mailjet, Resend, Gmail, OVH…), `surprise.mail` :

```bash
# .env, pour le serveur seulement
SMTP_URL=smtps://utilisateur:mot-de-passe@smtp-relay.brevo.com:465   # smtp://…:587 pour STARTTLS
MAIL_FROM=Secret Date <bonjour@secretdate.fr>
MAIL_SECRET=une-longue-phrase-secrete   # signe les liens qui arrêtent les emails
APP_URL=https://secretdate.fr           # l'adresse publique de l'app (http://127.0.0.1:8001 par défaut)
```

```bash
# ce qui partirait maintenant, sans rien envoyer
uv run --env-file .env python -m surprise.courriers --dry-run
# un passage, ou un toutes les dix minutes
uv run --env-file .env python -m surprise.courriers
uv run --env-file .env python -m surprise.courriers --loop 10
# ou avec le serveur, un passage toutes les dix minutes tant qu'il tourne
uv run --env-file .env python -m surprise.quiz --courriers
```

Sans `SMTP_URL`, aucun email ne part (les pushes web, si `FIREBASE_SERVICE_ACCOUNT` est là) ; sans `MAIL_SECRET`, le lien
en bas des emails mène à Mon compte, où les arrêter.

### Notifications push (Firebase Cloud Messaging)

Les pushes envoyés par le serveur (`app/src/lib/push.ts` côté app, `surprise.push` côté serveur), sur le web et Android :
- **Activation** : Mon compte › Notifications, « Activer les notifications » demande la permission. Le jeton FCM de
  l'appareil est alors gardé pour le compte (table `push_tokens`, fonction `register_push_token`). Il est repris à
  chaque démarrage (FCM le renouvelle) et oublié à la déconnexion. Un appareil n'a qu'un compte : connecté à un autre,
  son jeton le suit.
- **Web** : le SDK web de Firebase et son service worker (`app/public/firebase-messaging-sw.js`). Le push s'affiche même
  la page fermée ; le toucher ouvre sa page.
- **Android** : le jeton FCM natif d'expo-notifications. Accepter les notifications du téléphone (indices, rappels) le
  garde aussi. Il faut `app/google-services.json` (pris par `app.config.js` s'il est là) et une build de développement.
- **iOS** : pas de FCM, qui demanderait le SDK natif de Firebase ; ses notifications locales restent.

Le message est le même partout : des données seules (`title`, `message`, et `body`, un JSON de la page à ouvrir), le
format qu'expo-notifications affiche. Un jeton que FCM ne connaît plus (app désinstallée, permission retirée) est oublié
à l'envoi. Les moments clés des soirées partent en push vers les navigateurs avec les emails (`surprise.courriers`, plus
haut) ; les téléphones Android ont leurs notifications locales.

Mise en place, dans la console Firebase (un projet) :
1. Paramètres du projet › Vos applications : une app Web, dont les valeurs vont dans `app/.env`. Une clé Web Push
   (VAPID) du projet est facultative : sans elle, Firebase prend la sienne.
2. Une app Android `fr.secretdate.app` : son `google-services.json` dans `app/`.
3. Comptes de service › Générer une nouvelle clé privée : le fichier JSON hors du dépôt (par exemple dans `data/`,
   ignoré par git), son chemin dans `.env`.
4. La migration `push_tokens` appliquée au Supabase du projet (`supabase db push`, plus haut).

```bash
# app/.env, lu au build : publiques par nature, comme la clé anon
EXPO_PUBLIC_FIREBASE_API_KEY=...
EXPO_PUBLIC_FIREBASE_PROJECT_ID=...
EXPO_PUBLIC_FIREBASE_SENDER_ID=...
EXPO_PUBLIC_FIREBASE_APP_ID=...
# facultative : Cloud Messaging › Certificats Web Push
EXPO_PUBLIC_FIREBASE_VAPID_KEY=...
# .env, pour le serveur seulement : la clé du compte de service (son chemin, ou son contenu JSON)
FIREBASE_SERVICE_ACCOUNT=data/firebase-service-account.json
```

```bash
# un push test vers chaque appareil du compte
uv run --env-file .env python -m surprise.push vous@exemple.fr
# simulé : ce que FCM recevrait, sans rien envoyer
uv run --env-file .env python -m surprise.push vous@exemple.fr --dry-run
```

Le widget de l'écran d'accueil (« Prochaine soirée »), `app/src/lib/widget.ts` pour ce qu'il montre, `src/widgets/`
pour son dessin. Il montre :
- le nom secret de la prochaine soirée et son compte à rebours (« J-3 », « Demain · 19:30 », « Ce soir · 19:30 ») ;
- pour le passager, son dernier indice ;
- pour l'instigateur, les réservations encore à faire, puis le jour J l'étape suivante.

Toucher le widget ouvre la soirée. Le téléphone reçoit une chronologie pour les dix jours à venir (une entrée par
changement : chaque minuit, chaque indice, chaque étape, la fin), renouvelée avec les notifications (`lib/phone.ts`).
- **iPhone** : `expo-widgets`, en petit, moyen et sur l'écran verrouillé. Le plugin crée la cible du widget
  (`fr.secretdate.app.widgets`) et son groupe d'apps (`group.fr.secretdate.app`).
- **Android** : `react-native-android-widget`. La chronologie est gardée sur le téléphone, et le widget se redessine
  seul toutes les demi-heures (gestionnaire enregistré dans `app/index.js`, l'entrée de l'app).
- Le module d'Expo ne fait encore qu'une ébauche sur Android, d'où deux bibliothèques.
- Il faut une build de développement (pas Expo Go). Le projet Android se génère (`npx expo prebuild`) ; le projet iOS
  se génère sur un Mac ou dans EAS.
- Les identifiants `fr.secretdate.app…` sont à confirmer avant la première build : ils ne changent plus une fois l'app
  publiée.

La carte postale (`app/src/lib/postcard.ts`, `components/postcard.tsx`), en bas de la révélation, pour les deux :
- une image de story (1080 x 1920) avec le nom secret, le jour et l'heure, et les mots mystères tels que le passager
  les connaît (« ? » tant qu'un mot n'est pas venu) ;
- les étapes seulement une fois la soirée finie : partagée avant, elle ne dévoile rien ;
- partagée depuis un téléphone (`react-native-view-shot`, `expo-sharing`), téléchargée sur le web (`html-to-image`).

Le carton d'invitation (`app/src/lib/invitation-card.ts`), dans la carte « Votre passager » tant que personne n'a
rejoint la soirée :
- un carton A6 à imprimer, avec le nom secret, le jour et l'heure, et un QR code vers le lien d'invitation, pour le
  glisser sous un oreiller ;
- imprimé ou envoyé en PDF depuis un téléphone (`expo-print`) ; ouvert dans une fenêtre qui lance l'impression sur le web.

```bash
# app/.env, lu au build : publiques par nature (clé anon), jamais la service role key
EXPO_PUBLIC_SUPABASE_URL=...
EXPO_PUBLIC_SUPABASE_ANON_KEY=...
```

Sans ces variables, l'app reste fermée : `/compte` annonce que les comptes ne sont pas configurés. Dans les réglages Auth
de Supabase, désactiver la confirmation par email a du sens pour un usage personnel à deux.

### Liens partenaires (affiliation)

Les liens « Réserver » des soirées servies par l'API (`parcours.soiree_json`) et des emails deviennent des liens
partenaires dès que l'identifiant du programme est dans `.env` (`surprise.affiliation` ; démarches dans
[docs/affiliation.md](docs/affiliation.md)) ; sans lui, ou pour un site sans programme, le lien reste tel quel. Le nom de
la page de la soirée sert de sous-identifiant (quelle soirée a mené à une réservation, rien sur le couple) ; `partner`
le dit sur chaque étape, et Mon compte prévient que certains liens sont partenaires.

```bash
# .env
GETYOURGUIDE_PARTNER_ID=...   # ?partner_id=…&cmp=<page>
CIVITATIS_AID=...             # ?aid=…&cmp=<page>
AWIN_PUBLISHER_ID=...         # le lien profond d'Awin, clickref=<page>
AWIN_MERCHANTS=fnacspectacles.com:1234,thefork.fr:5678,tiqets.com:9012   # l'identifiant de chaque site sur Awin
```

## Modération

Interface locale pour relire les activités collectées (dans Supabase, ou la base SQLite sans `SUPABASE_DB_URL`) et
les valider ou les rejeter :

```bash
uv run --env-file .env python -m surprise.admin
```

Ouvre http://127.0.0.1:8000/admin (`--port` pour changer, `--db` pour une autre base) ; aussi servie par le
questionnaire sur http://127.0.0.1:8001/admin. Onglet, filtres et fiche active restent dans l'adresse
(`#tag=coquin&fiche=…`) : un retour ou un rechargement retrouve la sélection. Filtre par tag, ou clic sur un tag d'une fiche. Raccourcis : `j`/`k` naviguer,
`v` valider, `r` rejeter, `a` remettre en attente, `o` ouvrir la fiche source, `z` annuler. Filtre par source. Les décisions sont conservées
d'une collecte à l'autre ; une fiche modifiée par la source après décision est marquée « Modifiée ».
