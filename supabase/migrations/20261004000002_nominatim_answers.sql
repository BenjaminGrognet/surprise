-- Nominatim's answer to each question (surprise.enrich: osm_place, osm_area, osm_address), answer null when nothing
-- was found; asked again after 3 months. An address is asked once, not again at each collection or renormalization:
-- Nominatim answers one request per second.
create table if not exists pipeline.nominatim_answers (
  question text primary key,
  answer jsonb,
  checked_at timestamptz not null default now()
);
