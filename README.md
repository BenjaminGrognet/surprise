# surprise
## Collecteurs

```bash
uv run pytest
# Que Faire à Paris : résumé des fiches retenues / rejetées (6 prochaines semaines)
uv run python -m surprise.collectors.que_faire_a_paris
# … en local dans data/surprise.db (SQLite, ignoré par git)
uv run python -m surprise.collectors.que_faire_a_paris --store local
# … ou les payloads bruts dans Supabase (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
uv run python -m surprise.collectors.que_faire_a_paris --store supabase
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
| Shotgun | `shotgun` | pages Paris et genres + schema.org MusicEvent |
| BilletRéduc | `billetreduc` | page Paris + schema.org Event |
| Time Out Paris | `time_out` | sitemaps (60 jours) + schema.org Review des lieux |
| Le Bonbon | `le_bonbon` | sitemaps + blocs pratiques des articles |
| Articles « couple » (Hati Hati, Ryo, Love'n'Room, LoveCapsule, blog Funbooker, Petit Futé) | `selections_couple` | une idée par intertitre ou lien de réservation, lieu sur OSM |

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
quand ils n'ont pas de réservation en ligne.

## Enrichissement

Images et descriptions courtes des activités collectées (seules les nouvelles sont traitées) :

```bash
uv run python -m surprise.enrich
```

- Image : photo de la source, sinon `og:image` du site officiel, sinon Google Places si `GOOGLE_PLACES_API_KEY`
  est définie (seul l'identifiant du lieu est stocké, la photo est chargée à l'affichage avec son crédit).
- Lieu : coordonnées, horaires et, s'il manque, adresse depuis OpenStreetMap (Nominatim, 1 requête/s),
  cherchés par nom et code postal.
- Réservation : lien « Réserver » du site officiel si la fiche n'en a pas ; si le lien de la fiche mène à la page
  du spectacle sur le site du lieu, son bouton « Acheter » vers la billetterie.
- Description : rédigée par Claude si `ANTHROPIC_API_KEY` est définie (modèle : `SURPRISE_LLM_MODEL`,
  `claude-opus-5-5` par défaut), à partir du texte de la source (`lead_text` : texte de la fiche ou de l'article,
  gardé pour ce prototype perso) ou de l'extrait du site officiel.

`--refresh` retraite aussi les activités déjà enrichies, `--source` limite à une source, `--no-descriptions`
se passe de Claude.

## Disponibilités

Vérifie pour une date si les activités de la base locale sont réservables à 2 (créneaux horaires et formule),
sans compte : Funbooker, Come to Paris, puis Zenchef, SevenRooms et 4escape quand le lien de réservation (ou la
page où il mène) passe par eux. Bookeo n'est pas vérifiable (captcha). Les activités rejetées en modération et
celles sans moteur pris en charge sont ignorées.

```bash
uv run python -m surprise.availability 2026-10-09
uv run python -m surprise.availability 2026-10-09 --source funbooker --party 4 --limit 10
```

## Modération

Interface locale pour relire les activités collectées (`--store local`) et les valider ou les rejeter :

```bash
uv run python -m surprise.admin
```

Ouvre http://127.0.0.1:8000 (`--port` pour changer, `--db` pour une autre base). Raccourcis : `j`/`k` naviguer,
`v` valider, `r` rejeter, `a` remettre en attente, `o` ouvrir la fiche source, `z` annuler. Filtre par source. Les décisions sont conservées
d'une collecte à l'autre ; une fiche modifiée par la source après décision est marquée « Modifiée ».
