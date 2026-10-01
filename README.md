# surprise

Tout lancer soi-même : double-cliquer sur `lancer.cmd` (serveur + app Expo), `collecte.cmd` (collecte, 200 fiches par source) ou `admin.cmd` (modération) ; détail dans
[docs/lancer-en-local.md](docs/lancer-en-local.md).

## Collecteurs

```bash
uv run pytest
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

### Collecte complète

`surprise.collect` lance les 30 sources, 4 à la fois (`--jobs`). Chaque source enregistre par lots de 50 fiches au
fil de l'eau, et une source en échec n'arrête pas les autres. Une page de détail encore fraîche n'est pas relue
et ne compte pas dans `--limit` : un nouveau passage à `--limit 50` lit 50 fiches de plus.
Le délai est donné par `FRESH_DAYS` dans chaque collecteur : 2 jours pour les événements (Shotgun, Dice, BilletRéduc,
Eventbrite, Fever), 14 pour les catalogues d'activités, 30 pour les lieux (OSM, hôtels, escape games, Time Out),
7 par défaut (médias). Ses payloads stockés (`_page`) sont renormalisés à la date du jour, sauf si le sitemap la dit
modifiée depuis (Paris ZigZag). Une page de réservation ou un site officiel n'est vérifié qu'une fois par mois
(`pipeline.page_checks`, migration `20260930000000_page_checks.sql`), et une fois par passage même si 46 concerts y
renvoient. Ces vérifications se font à 16 en parallèle, une seule à la fois par site. Nominatim reste à 1 requête/s.

```bash
uv run --env-file .env python -m surprise.collect --limit 50
# certaines sources, en relisant tout, 20 min au plus chacune
uv run --env-file .env python -m surprise.collect --source fever --source tiqets --refresh --minutes 20
```

Paris ZigZag (média de curation : nom, lieu, dates, lien officiel et photo de l'article, pas de texte) :

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
| Restaurants OpenStreetMap | `osm_restaurants` | Overpass (restaurants de Paris avec site) + site du restaurant : gardé s'il passe par un moteur de réservation (Zenchef, SevenRooms, TheFork…), sur sa page ou sa page « Réserver » |
| Sortir à Paris | `sortir_a_paris` | sitemaps (60 jours) des rubriques insolite, soirées, spectacles, gaming, Halloween et bars + bloc « Informations pratiques » (microdonnées schema.org Place, dates, tarifs, site officiel, réservation) ; articles sans lieu écartés |
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

Tous les motifs de rejet d'une fiche sont gardés (« jeune public · passé »), un badge chacun dans la modération : la
fiche est construite quand même, sauf si un motif l'en empêche (sans nom, sans lieu, hors zone, invalide, page
illisible). Celles-là apparaissent aussi dans « Écartées à la collecte », avec leur titre et le lien de la source,
sans pouvoir être validées. La réservation n'est vérifiée que pour une fiche sans autre motif (pas de requête perdue).

Zone : Paris et la proche banlieue qu'atteint le métro (`METRO_TOWNS` dans `surprise/models.py` : Boulogne, Montreuil,
Saint-Denis, Vincennes, Ivry…) ; ailleurs, rejet « hors Paris et proche banlieue ». Les parcours gardent au plus 35 min
de trajet entre deux étapes.

Règles changées : `uv run python -m surprise.renormalize --rejet "<motif>"` (ou `--source <id>`) normalise de nouveau
les pages déjà collectées, puis revérifie la réservation, sans rien recollecter. `--rejet` prend les fiches qui ont ce
motif parmi les autres.

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
  source (`lead_text` : texte de la fiche ou de l'article, gardé pour ce prototype perso), sinon de l'extrait du
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

## Tags et vibes

`surprise/tags.py` décrit chaque activité par des **tags** précis (mini-golf, céramique, rooftop, aux chandelles…),
en trois facettes : activité, cadre, moment. Les tags donnent les **vibes**, les envies larges du questionnaire client
(Bouger, Relever un défi, Rire, Créer, Savourer, Se détendre, S'émerveiller, Vibrer en musique, Faire la fête,
Se cultiver, Prendre l'air, Frissonner, L'insolite, Pimenter, Romantique) : un mini-golf est « Bouger » et « Relever un défi ».
Calculés à la lecture par des règles sur le titre et le lieu (plus les catégories), ils s'affinent sans recollecter ;
la modération les affiche et filtre par vibe.

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
sans compte : Funbooker, Wecandoo, Come to Paris, puis Zenchef, SevenRooms et 4escape quand le lien de réservation
ou le site officiel (ou la page où ils mènent) passe par eux. Bookeo n'est pas vérifiable (captcha). Les activités rejetées en modération et
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
  gardées 6 h), lieu gratuit ouvert à cette heure, ou bar / club sans réservation (marqué comme tel, `--strict` les
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
  ou prolongé). Les activités déjà proposées ne reviennent pas tant que d'autres conviennent ; celle qu'on change ne revient jamais,
  même vendue sous une autre fiche (même lieu ou même titre). Les parcours sont gardés
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

```bash
uv run python -m surprise.quiz    # http://127.0.0.1:8001
uv run python -m surprise.quiz --host 0.0.0.0    # + accessible depuis un téléphone sur le même Wi-Fi
```

Un seul site, qui est l'app : le serveur sert le build web de l'app Expo (`app/dist`, `npm run build:web` dans
`app/`, refait par `lancer.cmd` à chaque lancement), l'API qu'elle appelle (`/api/…`) et la modération (`/admin`).
Il n'y a pas d'autre page client : toute évolution se fait dans `app/` et vaut pour le téléphone comme pour le site.
Le build web appelle l'API sur sa propre adresse ; en développement (`npm run web`, port 8081), sur
`EXPO_PUBLIC_API_URL`.

## Compte client et historique

L'app demande un compte (email + mot de passe, Supabase Auth) avant tout le reste : sans être connecté, seul
`/compte` s'affiche. Le compte garde le profil et l'historique des soirées vraiment réalisées (celle choisie parmi
les trois parcours proposés) sur n'importe quel appareil. Le navigateur parle directement à Supabase avec la clé
anon ; la sécurité (chacun ne voit que ses données) vient uniquement des policies RLS des migrations
(`couple_profiles.user_id`, table `soirees_choisies`) — il n'y a pas de code serveur entre les deux.

Deux comptes par couple (table `couples`) : l'instigateur fait le profil, commande les soirées, voit la feuille de
route et coche ses réservations (`soirees_choisies.booked`) ; il invite le passager par un lien (`/invitation?code=…`,
fonction `join_couple`). Le passager a son propre compte, ne voit que le compte à rebours, les indices et le
programme voilé des soirées de son instigateur ; le quiz et `/soiree` lui sont fermés. Un compte sans couple est
instigateur. Limite connue : le passager pourrait lire les données d'une soirée par l'API (l'app seule les voile).

Une soirée gardée prend un nom secret, vu des deux (« Le Pacte de l'Île Saint-Louis ») : un mot d'intrigue tiré de
son ambiance et le quartier de son étape la plus centrale, jamais un lieu (un quartier qui porte le nom d'un lieu de la
soirée est sauté). Règles sans Claude (`parcours.secret_title`), envoyé avec chaque parcours (`secret_title`) et figé
à la garde dans `soirees_choisies.secret_title` (migration `20261001000003_secret_title.sql`).

Le Livre des Secrets (`/livre?soiree=…&route=…`) : en fin de soirée (sa dernière étape commencée) puis les jours
suivants, chacun des deux scelle une page — une photo, un mot (table `souvenirs`, photos dans le bucket privé
`souvenirs`, lues par liens signés). Scellée, une page ne se modifie plus ; on ne lit celle de l'autre qu'après avoir
scellé la sienne (fonction `sealed_by_me`). Les Archives (`/historique`) n'en montrent plus que la photo et les
notes, le long d'un fil d'or, de plus en plus patinées avec l'âge ; le parcours n'y apparaît plus.

```bash
# app/.env, lu au build : publiques par nature (clé anon), jamais la service role key
EXPO_PUBLIC_SUPABASE_URL=...
EXPO_PUBLIC_SUPABASE_ANON_KEY=...
```

Sans ces variables, l'app reste fermée : `/compte` annonce que les comptes ne sont pas configurés. Dans les réglages Auth
de Supabase, désactiver la confirmation par email a du sens pour un usage personnel à deux.

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
