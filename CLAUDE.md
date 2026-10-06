# surprise

Prototype perso : sorties originales en couple à Paris. Les commandes sont dans le README.

## Consignes

- Collecte : lancer toutes les sources (que_faire_a_paris, paris_zigzag, funbooker, paris_friendly,
  paris_city_game, come_to_paris, paris_secret, concerts_paris, paris_jetaime, paris_jetaime_billetterie,
  visit_paris_region, explore_paris, wecandoo, fever, getyourguide, tiqets, civitatis, eventbrite, shotgun,
  billetreduc, time_out, le_bonbon, selections_couple, osm_restaurants, time_out_hotels, nuits_couple,
  sortir_a_paris, dice, escape_game, osm_loisirs, selections_squad, privateaser), chacune avec `--store supabase --limit 50` (scripts lancés par
  `uv run --env-file .env …`), ou toutes ensemble par `python -m surprise.collect --limit 50`. Jamais sans limite : on valide le
  fonctionnement ensemble, source par source, sur un petit volume. Les pages encore fraîches ne sont pas relues
  (`FRESH_DAYS` par collecteur, 7 jours par défaut ; `--refresh` pour forcer).
- Enrichissement : descriptions extraites des textes par défaut, sans appel extérieur ; `--claude` seulement sur demande ;
  `--source` pour ne retraiter que les sources modifiées.
- Images : prendre celles des sites (source ou site officiel) sans se soucier des licences pour
  l'instant ; garder l'origine pour pouvoir changer de stratégie si le produit est commercialisé.
- Textes : le texte des médias (Paris ZigZag, Paris-Friendly, Paris Secret, Sortir à Paris) est gardé (`lead_text`) pour que Claude en
  rédige la description ; à retirer avant tout usage public.
- Base : ne garder que des activités possibles pour un couple ou une bande d'amis (Secret Squad, 3 à 10 : offres
  EVJF/EVG, escape games à 3 ou plus), vraiment réservables ou gratuites ; le parcours choisit selon la formule ;
  les autres sont rejetées à la collecte. Exception : bars, clubs, boîtes de nuit et restaurants (dansants ou non)
  sont gardés s'ils sont ouverts, marqués « non réservable » sans réservation en ligne. Les rejetées restent en base,
  à part dans la modération (« Écartées à la collecte »), pour améliorer les règles.
- Données manquantes d'une fiche (adresse, horaires, coordonnées) : scraping ciblé de sources publiques ;
  OpenStreetMap (Nominatim) d'abord, déjà branché dans l'enrichissement.
- Site web = l'app Expo (`app/`) construite pour le web (`npm run build:web` → `app/dist`, servie par `surprise.quiz`).
  Jamais de page client à part (HTML Python, `.web.tsx` d'écran) : tout se fait dans `app/` et vaut pour les deux.
  Le Python ne fournit que l'API (données, pas de mise en page) et la modération.
- Tests : toute fonctionnalité nouvelle ou modifiée vient avec ses tests, dans la même livraison, à chaque couche
  touchée : `uv run pytest` (collecte, composition, API), `npm test` dans `app/` (comptes, Supabase local) et
  `npm run e2e` (le site dans un navigateur : ce que voit le couple, images et textes compris). Les trois passent
  avant un commit. Jamais le Supabase du projet dans les tests : le local (`npm run db:start`, Docker).
- Base : Supabase (`public.raw_records` + schéma `pipeline`), par `SUPABASE_DB_URL` (session pooler IPv4). Sans elle,
  les scripts retombent sur `data/surprise.db` (non versionnée) ; `python -m surprise.local_store` la copie dans Supabase.
