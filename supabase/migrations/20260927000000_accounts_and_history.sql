-- Real accounts (Supabase Auth, email + password) for the couple, on top of the anonymous
-- local profile (surprise.quiz still works without an account). An account's couple profile
-- lives here, one row per user; the couple's past evenings they actually picked (one of the
-- three routes proposed) go in soirees_choisies. The browser talks to both tables directly
-- with the anon key and the user's own session: RLS is the only guard, there is no server code
-- in between.

alter table public.couple_profiles add column if not exists user_id uuid references auth.users(id) on delete cascade;
create unique index if not exists couple_profiles_user_id_key on public.couple_profiles(user_id) where user_id is not null;

create policy "select own profile" on public.couple_profiles
  for select using (auth.uid() = user_id);
create policy "insert own profile" on public.couple_profiles
  for insert with check (auth.uid() = user_id);
create policy "update own profile" on public.couple_profiles
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- One evening actually chosen among the (up to three) routes proposed on a /parcours page.
create table public.soirees_choisies (
  id text primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  page_name text not null,
  route_index integer not null,
  title text not null,
  pitch text not null,
  vibes text[] not null default '{}',
  day date,
  chosen_at timestamptz not null default now()
);

alter table public.soirees_choisies enable row level security;

create policy "select own history" on public.soirees_choisies
  for select using (auth.uid() = user_id);
create policy "insert own history" on public.soirees_choisies
  for insert with check (auth.uid() = user_id);
