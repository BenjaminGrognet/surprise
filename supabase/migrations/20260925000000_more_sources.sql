-- Official agendas (tier 1), ticketing and activity marketplaces (tier 2, bookable,
-- affiliation often possible) and curation media or blogs (tier 3).
-- Personal prototype: facts, texts and photos are kept.
insert into public.sources (id, name, tier, license, base_url, affiliate_possible) values
  ('concerts_paris', 'concerts.paris', 2, 'tous droits réservés', 'https://concerts.paris', false),
  ('paris_jetaime', 'Paris je t''aime', 1, 'tous droits réservés', 'https://agenda.parisjetaime.com', false),
  ('paris_jetaime_billetterie', 'Paris je t''aime (billetterie)', 2, 'tous droits réservés', 'https://ticket.parisjetaime.com', false),
  ('visit_paris_region', 'VisitParisRegion', 1, 'tous droits réservés', 'https://www.visitparisregion.com', false),
  ('explore_paris', 'Explore Paris', 2, 'tous droits réservés', 'https://exploreparis.com', false),
  ('wecandoo', 'Wecandoo', 2, 'tous droits réservés', 'https://wecandoo.fr', true),
  ('fever', 'Fever', 2, 'tous droits réservés', 'https://feverup.com', true),
  ('getyourguide', 'GetYourGuide', 2, 'tous droits réservés', 'https://www.getyourguide.fr', true),
  ('tiqets', 'Tiqets', 2, 'tous droits réservés', 'https://www.tiqets.com', true),
  ('civitatis', 'Civitatis', 2, 'tous droits réservés', 'https://www.civitatis.com', true),
  ('eventbrite', 'Eventbrite', 2, 'tous droits réservés', 'https://www.eventbrite.fr', false),
  ('shotgun', 'Shotgun', 2, 'tous droits réservés', 'https://shotgun.live', false),
  ('billetreduc', 'BilletRéduc', 2, 'tous droits réservés', 'https://www.billetreduc.com', true),
  ('time_out', 'Time Out Paris', 3, 'tous droits réservés', 'https://www.timeout.fr/paris', false),
  ('le_bonbon', 'Le Bonbon', 3, 'tous droits réservés', 'https://www.lebonbon.fr/paris', false),
  ('selections_couple', 'Sélections couple (blogs)', 3, 'tous droits réservés', null, false);
