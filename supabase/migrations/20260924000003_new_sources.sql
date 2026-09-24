-- Activity marketplace (tier 2, bookable, affiliation possible) and two curation
-- media (tier 3). Personal prototype: facts and the page image are kept.
insert into public.sources (id, name, tier, license, base_url, affiliate_possible) values
  ('funbooker', 'Funbooker', 2, 'tous droits réservés', 'https://www.funbooker.com', true),
  ('paris_friendly', 'Paris-Friendly', 3, 'tous droits réservés', 'https://www.paris-friendly.fr', false),
  ('paris_city_game', 'Paris City Game', 3, 'tous droits réservés', 'https://pariscitygame.fr', false);
