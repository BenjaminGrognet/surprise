-- Paris restaurants bookable online, from OpenStreetMap (open data, ODbL: attribution, share-alike of the base).
insert into public.sources (id, name, tier, license, base_url, affiliate_possible) values
  ('osm_restaurants', 'Restaurants OpenStreetMap', 1, 'ODbL', 'https://www.openstreetmap.org', false);
