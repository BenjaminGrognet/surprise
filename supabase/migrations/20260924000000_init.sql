create extension if not exists postgis with schema extensions;

create type public.activity_kind as enum ('permanent', 'temporary');
create type public.moderation_status as enum ('proposed', 'approved', 'rejected');
create type public.price_unit as enum ('per_person', 'per_couple', 'per_group');
create type public.provenance_entity as enum ('venue', 'activity', 'occurrence', 'offer');

create function public.set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table public.sources (
  id text primary key,
  name text not null,
  tier smallint not null check (tier between 1 and 4),
  license text,
  base_url text,
  affiliate_possible boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.raw_records (
  id uuid primary key default gen_random_uuid(),
  source_id text not null references public.sources (id),
  external_id text not null,
  url text,
  payload jsonb not null,
  content_hash text not null,
  fetched_at timestamptz not null default now(),
  unique (source_id, external_id, content_hash)
);

create index raw_records_source_fetched_idx on public.raw_records (source_id, fetched_at desc);

create table public.venues (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text,
  -- Paris intra-muros only (hard filter): 75001–75020, plus 75116.
  postal_code text not null check (postal_code ~ '^750(0[1-9]|1[0-9]|20)$' or postal_code = '75116'),
  arrondissement smallint generated always as (
    case when postal_code = '75116' then 16 else right(postal_code, 2)::smallint end
  ) stored,
  location extensions.geography(point, 4326),
  website text,
  opening_hours jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index venues_location_idx on public.venues using gist (location);
create trigger venues_set_updated_at before update on public.venues
  for each row execute function public.set_updated_at();

create table public.activities (
  id uuid primary key default gen_random_uuid(),
  venue_id uuid references public.venues (id) on delete set null,
  title text not null,
  description text,
  kind public.activity_kind not null,
  starts_on date,
  ends_on date,
  duration_minutes integer check (duration_minutes > 0),
  website text,
  image_url text,
  image_license text,
  image_source_url text,
  -- Soft filter: null = unknown, evaluated on occurrences / opening hours.
  is_evening boolean,
  status public.moderation_status not null default 'proposed',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (ends_on is null or starts_on is null or ends_on >= starts_on),
  check (image_url is null or image_license is not null)
);

create index activities_venue_idx on public.activities (venue_id);
create index activities_status_idx on public.activities (status);
create trigger activities_set_updated_at before update on public.activities
  for each row execute function public.set_updated_at();

create table public.occurrences (
  id uuid primary key default gen_random_uuid(),
  activity_id uuid not null references public.activities (id) on delete cascade,
  starts_at timestamptz not null,
  ends_at timestamptz,
  check (ends_at is null or ends_at > starts_at),
  unique (activity_id, starts_at)
);

create index occurrences_starts_at_idx on public.occurrences (starts_at);

create table public.offers (
  id uuid primary key default gen_random_uuid(),
  activity_id uuid not null references public.activities (id) on delete cascade,
  label text,
  is_free boolean not null default false,
  price_min numeric(10, 2) check (price_min >= 0),
  price_max numeric(10, 2) check (price_max >= 0),
  currency char(3) not null default 'EUR',
  price_unit public.price_unit not null default 'per_person',
  booking_url text,
  online_booking boolean,
  paid_booking boolean,
  affiliate_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (price_min is null or price_max is null or price_max >= price_min),
  check (not is_free or coalesce(price_max, 0) = 0)
);

create index offers_activity_idx on public.offers (activity_id);
create trigger offers_set_updated_at before update on public.offers
  for each row execute function public.set_updated_at();

create table public.provenance (
  id uuid primary key default gen_random_uuid(),
  raw_record_id uuid not null references public.raw_records (id) on delete cascade,
  entity_type public.provenance_entity not null,
  entity_id uuid not null,
  fields text[] not null default '{}',
  created_at timestamptz not null default now()
);

create index provenance_entity_idx on public.provenance (entity_type, entity_id);

-- Collectors write with the service role (bypasses RLS). The public API only
-- exposes moderated content; raw_records and provenance stay private.
alter table public.sources enable row level security;
alter table public.raw_records enable row level security;
alter table public.venues enable row level security;
alter table public.activities enable row level security;
alter table public.occurrences enable row level security;
alter table public.offers enable row level security;
alter table public.provenance enable row level security;

create policy "sources are public" on public.sources
  for select to anon, authenticated using (true);

create policy "approved activities are public" on public.activities
  for select to anon, authenticated using (status = 'approved');

create policy "venues of approved activities are public" on public.venues
  for select to anon, authenticated using (
    exists (select 1 from public.activities a where a.venue_id = venues.id and a.status = 'approved')
  );

create policy "occurrences of approved activities are public" on public.occurrences
  for select to anon, authenticated using (
    exists (select 1 from public.activities a where a.id = occurrences.activity_id and a.status = 'approved')
  );

create policy "offers of approved activities are public" on public.offers
  for select to anon, authenticated using (
    exists (select 1 from public.activities a where a.id = offers.activity_id and a.status = 'approved')
  );

insert into public.sources (id, name, tier, license, base_url, affiliate_possible) values
  ('que_faire_a_paris', 'Que Faire à Paris', 1, 'ODbL', 'https://opendata.paris.fr', false),
  ('openagenda', 'OpenAgenda', 1, 'variable', 'https://openagenda.com', false),
  ('datatourisme', 'DATAtourisme', 1, 'Licence Ouverte Etalab', 'https://www.datatourisme.fr', false),
  ('paris_musees', 'Paris Musées', 1, null, 'https://www.parismusees.paris.fr', false),
  ('manual', 'Ajout manuel', 4, null, null, false);
