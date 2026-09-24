# surprise

Prototype perso : sorties originales en couple à Paris. Les commandes sont dans le README.

## Consignes

- Collecte : lancer toutes les sources (que_faire_a_paris, paris_zigzag, funbooker, paris_friendly,
  paris_city_game, come_to_paris, paris_secret), chacune avec `--store local --limit 50`. Jamais sans limite : on valide le
  fonctionnement ensemble, source par source, sur un petit volume.
- Enrichissement : `--no-descriptions` tant que les descriptions Claude ne sont pas demandées ;
  `--source` pour ne retraiter que les sources modifiées.
- Images : prendre celles des sites (source ou site officiel) sans se soucier des licences pour
  l'instant ; garder l'origine pour pouvoir changer de stratégie si le produit est commercialisé.
- Textes : le texte des médias (Paris ZigZag, Paris-Friendly, Paris Secret) est gardé (`lead_text`) pour que Claude en
  rédige la description ; à retirer avant tout usage public.
- Données manquantes d'une fiche (adresse, horaires, coordonnées) : scraping ciblé de sources publiques ;
  OpenStreetMap (Nominatim) d'abord, déjà branché dans l'enrichissement.
- La base locale `data/surprise.db` n'est pas versionnée : elle se recrée en relançant les collecteurs.
