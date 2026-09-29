-- The collection pipeline's working tables, mirroring surprise.local_store (SQLite): the latest normalization of
-- each raw record, moderation decisions, enrichment (image, place, description), keywords and the booking engines'
-- answers. The Python scripts reach them through the Postgres connection (SUPABASE_DB_URL); the schema is not
-- exposed to the API roles.
create schema if not exists pipeline;
revoke all on schema pipeline from anon, authenticated;

insert into public.sources (id, name, tier, license, base_url, affiliate_possible) values
  ('time_out_hotels', 'Time Out Paris (hôtels)', 3, 'tous droits réservés', 'https://www.timeout.fr/paris/hotels', false),
  ('nuits_couple', 'Nuits en amoureux (love rooms, hôtels insolites)', 3, 'tous droits réservés', null, false)
on conflict (id) do nothing;

create table pipeline.normalized (
  source_id text not null references public.sources (id),
  external_id text not null,
  content_hash text not null,
  activity jsonb,
  rejection text,
  normalized_at timestamptz not null default now(),
  primary key (source_id, external_id)
);

create table pipeline.moderation (
  source_id text not null,
  external_id text not null,
  status text not null check (status in ('approved', 'rejected')),
  content_hash text not null,
  decided_at timestamptz not null default now(),
  primary key (source_id, external_id)
);

create table pipeline.enrichment (
  source_id text not null,
  external_id text not null,
  image_url text,
  image_origin text,
  place_id text,
  site_excerpt text,
  description text,
  description_model text,
  booking_url text,
  latitude double precision,
  longitude double precision,
  opening_hours text,
  osm_address text,
  osm_url text,
  enriched_at timestamptz not null default now(),
  primary key (source_id, external_id)
);

create table pipeline.keywords (
  source_id text not null,
  external_id text not null,
  keywords jsonb not null,
  computed_at timestamptz not null default now(),
  primary key (source_id, external_id)
);

create table pipeline.availability (
  source_id text not null,
  external_id text not null,
  day date not null,
  party integer not null,
  engine text,
  available boolean,
  slots jsonb not null,
  detail text not null,
  checked_at timestamptz not null default now(),
  primary key (source_id, external_id, day, party)
);
