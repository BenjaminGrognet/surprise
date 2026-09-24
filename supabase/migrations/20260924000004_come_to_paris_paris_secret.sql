-- A ticketing marketplace (tier 2, bookable, affiliation possible) and a curation
-- media (tier 3). Personal prototype: facts, texts and photos are kept.
insert into public.sources (id, name, tier, license, base_url, affiliate_possible) values
  ('come_to_paris', 'Come to Paris', 2, 'tous droits réservés', 'https://www.cometoparis.com', true),
  ('paris_secret', 'Paris Secret', 3, 'tous droits réservés', 'https://parissecret.com', false);
