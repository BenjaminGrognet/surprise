-- OpenStreetMap place of each venue (surprise.enrich), place null when none was found; asked again after 3 months.
create table pipeline.osm_places (
  name text not null,
  postal_code text not null,
  place jsonb,
  checked_at timestamptz not null default now(),
  primary key (name, postal_code)
);
