-- Sources of the evenings' gaps: nightlife ticketing, escape and immersive games, unusual outings, leisure venues.
insert into public.sources (id, name, tier, license, base_url, affiliate_possible) values
  ('sortir_a_paris', 'Sortir à Paris', 3, 'tous droits réservés', 'https://www.sortiraparis.com', false),
  ('dice', 'Dice', 2, 'tous droits réservés', 'https://dice.fm', false),
  ('escape_game', 'EscapeGame.fr', 2, 'tous droits réservés', 'https://www.escapegame.fr', false),
  ('osm_loisirs', 'Loisirs OpenStreetMap', 1, 'ODbL', 'https://www.openstreetmap.org', false);
