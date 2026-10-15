-- Les dates et les occasions (docs/complicite.md, phase 3). The dates that count for a duo — when they met, each one's
-- birthday — and Saint-Valentin for every duo: three weeks before, the server (surprise.rappels) composes three
-- intrigues for that day and says so by email and on the web; the seasons of Paris (Fête de la musique, Nuit Blanche,
-- Halloween, Noël), told on the home and by email to the accounts with no evening that day; an evening lived a year
-- ago, come back. Each reminder goes once (pipeline.rappels: the evenings' own emails, pipeline.courriers, belong to
-- an evening; these do not).

create table public.dates_cles (
  id uuid primary key default gen_random_uuid(),
  duo_id uuid not null references public.duos(id) on delete cascade,
  author uuid not null default auth.uid() references auth.users(id) on delete cascade,
  label text not null check (length(trim(label)) between 1 and 80),
  genre text not null check (genre in ('rencontre', 'anniversaire', 'autre')),
  mois smallint not null check (mois between 1 and 12),
  jour smallint not null check (jour between 1 and 31),
  pour uuid references auth.users(id) on delete cascade, -- whose birthday: only the other is reminded
  created_at timestamptz not null default now(),
  check (make_date(2024, mois, jour) is not null)
);
create index dates_cles_duo_idx on public.dates_cles(duo_id);
alter table public.dates_cles enable row level security;
create policy "read our dates" on public.dates_cles for select using (duo_id = public.my_duo());
create policy "note a date" on public.dates_cles for insert
  with check (duo_id = public.my_duo() and author = auth.uid()
              and (pour is null or exists (select 1 from public.duo_members m where m.duo_id = public.my_duo() and m.user_id = pour)));
create policy "forget a date" on public.dates_cles for delete using (duo_id = public.my_duo());

-- The three intrigues composed for a date, ready for the account: the page of the server's (soiree.tsx ?soiree=).
create table public.intrigues_pretes (
  user_id uuid not null references auth.users(id) on delete cascade,
  cle text not null, -- the reminder's key: date:<id>:<day>
  page_name text not null,
  day date not null,
  label text not null,
  created_at timestamptz not null default now(),
  primary key (user_id, cle)
);
alter table public.intrigues_pretes enable row level security;
create policy "read my ready intrigues" on public.intrigues_pretes for select using (user_id = auth.uid());

-- The seasons of Paris: a day (mois, jour) for those that come back each year, the days of each year in saison_dates
-- for those that move (Nuit Blanche: its date, said by the city each year, entered then). `jours`: how long it lasts.
create table public.saisons (
  id text primary key,
  nom text not null,
  texte text not null,
  deroule text not null,
  envies text[] not null, -- wishes of the evening form (surprise.quiz.ENVIES)
  mois smallint check (mois between 1 and 12),
  jour smallint check (jour between 1 and 31),
  jours smallint not null default 1 check (jours >= 1)
);
create table public.saison_dates (
  saison_id text not null references public.saisons(id) on delete cascade,
  debut date not null,
  primary key (saison_id, debut)
);
alter table public.saisons enable row level security;
alter table public.saison_dates enable row level security;
create policy "the seasons are for every account" on public.saisons for select to authenticated using (true);
create policy "the seasons' days are for every account" on public.saison_dates for select to authenticated using (true);

insert into public.saisons (id, nom, texte, deroule, envies, mois, jour, jours) values
  ('fete-de-la-musique', 'La Fête de la musique',
   'Le 21 juin, Paris joue dans chaque rue : une soirée qui suit la musique, d''une scène à l''autre.',
   'Un verre en terrasse avant que ça commence, un concert, puis on suit ce qui joue jusqu''au bout de la nuit.',
   array['musique', 'fete'], 6, 21, 1),
  ('nuit-blanche', 'La Nuit Blanche',
   'Une nuit entière d''art dans les rues : on flâne d''une œuvre à l''autre, et Paris ne dort pas.',
   'Un dîner léger, puis une marche de nuit entre les installations, un dernier verre à l''aube.',
   array['curieux', 'air'], null, null, 1),
  ('halloween', 'Halloween',
   'Le soir des frissons : une soirée qui fait un peu peur, à deux ou en bande.',
   'Un verre dans un bar étrange, une expérience à frissons, puis un dîner pour se remettre de ses émotions.',
   array['frissons'], 10, 31, 1),
  ('noel', 'Les lumières de Noël',
   'Décembre allume Paris : vitrines, marchés de Noël, vin chaud, et un dîner au chaud.',
   'Une balade sous les illuminations, un marché de Noël, puis une table qui sent la cannelle.',
   array['romantique', 'air'], 12, 1, 24);

-- The seasons whose window is not over at `d` and begins within two months: their next days.
create function public.saisons_a_venir(d date default public.paris_today())
returns table (id text, nom text, texte text, deroule text, envies text[], debut date, fin date)
language sql stable as $$
  with fixed as (
    select s.*, case
      when make_date(extract(year from d)::int, s.mois, s.jour) + (s.jours - 1) >= d then make_date(extract(year from d)::int, s.mois, s.jour)
      else make_date(extract(year from d)::int + 1, s.mois, s.jour)
    end as debut
    from public.saisons s where s.mois is not null
  ), moving as (
    select s.*, sd.debut from public.saisons s join public.saison_dates sd on sd.saison_id = s.id
  )
  select id, nom, texte, deroule, envies, debut, (debut + (jours - 1))::date as fin
  from (select * from fixed union all select * from moving) seasons
  where debut + (jours - 1) >= d and debut <= d + 60
  order by debut
$$;
grant execute on function public.saisons_a_venir(date) to authenticated;

-- The reminders sent: a date's, a season's, a year since an evening. Each once per account and channel.
create table pipeline.rappels (
  user_id uuid not null references auth.users(id) on delete cascade,
  cle text not null,
  recipient text not null, -- an address, or push:<user_id>
  sent_at timestamptz not null default now(),
  primary key (user_id, cle, recipient)
);
