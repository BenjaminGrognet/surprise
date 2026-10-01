-- What the organiser has already booked for a kept evening (Les Coulisses, /revelation): the id
-- (source_id:external_id) of each step marked "réservé". Only the organiser's own rows, as for the rest of the history.

alter table public.soirees_choisies add column if not exists booked text[] not null default '{}';

create policy "update own history" on public.soirees_choisies
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
