-- Curation media (tier 3): discovery signal only. Only the entity (name, venue,
-- dates, official link) is kept; no text or image from the site is republished.
insert into public.sources (id, name, tier, license, base_url, affiliate_possible) values
  ('paris_zigzag', 'Paris ZigZag', 3, 'tous droits réservés', 'https://www.pariszigzag.fr', false);
