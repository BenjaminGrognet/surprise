# surprise

Prototype perso : sorties originales en couple à Paris. Les commandes sont dans le README.

## Consignes

- Collecte : lancer toutes les sources (que_faire_a_paris, paris_zigzag, funbooker, paris_friendly,
  paris_city_game, come_to_paris, paris_secret, concerts_paris, paris_jetaime, paris_jetaime_billetterie,
  visit_paris_region, explore_paris, wecandoo, fever, getyourguide, tiqets, civitatis, eventbrite, shotgun,
  billetreduc, time_out, le_bonbon, selections_couple, osm_restaurants, time_out_hotels, nuits_couple,
  sortir_a_paris, dice, escape_game, osm_loisirs), chacune avec `--store local --limit 50`. Jamais sans limite : on valide le
  fonctionnement ensemble, source par source, sur un petit volume.
- Enrichissement : `--no-descriptions` tant que les descriptions Claude ne sont pas demandées ;
  `--source` pour ne retraiter que les sources modifiées.
- Images : prendre celles des sites (source ou site officiel) sans se soucier des licences pour
  l'instant ; garder l'origine pour pouvoir changer de stratégie si le produit est commercialisé.
- Textes : le texte des médias (Paris ZigZag, Paris-Friendly, Paris Secret, Sortir à Paris) est gardé (`lead_text`) pour que Claude en
  rédige la description ; à retirer avant tout usage public.
- Base : ne garder que des activités possibles pour un couple, vraiment réservables ou gratuites ;
  les autres sont rejetées à la collecte. Exception : bars, clubs, boîtes de nuit et restaurants (dansants ou non)
  sont gardés s'ils sont ouverts, marqués « non réservable » sans réservation en ligne. Les rejetées restent en base,
  à part dans la modération (« Écartées à la collecte »), pour améliorer les règles.
- Données manquantes d'une fiche (adresse, horaires, coordonnées) : scraping ciblé de sources publiques ;
  OpenStreetMap (Nominatim) d'abord, déjà branché dans l'enrichissement.
- La base locale `data/surprise.db` n'est pas versionnée : elle se recrée en relançant les collecteurs.
