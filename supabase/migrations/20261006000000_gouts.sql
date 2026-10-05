-- The couple's tastes: on a step of an evening they compose or organise, the instigateur says « on aime ce genre »
-- (+1) or « pas pour nous » (-1). Sent with each new evening, the server draws from them the kinds of outing to
-- favour or to leave out (surprise.parcours.tastes_from); the activity voted down itself is never proposed again.
-- Each account its own, as its profile; gone with the account (cascade).

create table public.gouts (
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  activity_id text not null, -- source_id:external_id, as the server names a step
  vote smallint not null check (vote in (-1, 1)),
  title text not null default '', -- the step's name when voted: the account page lists them
  voted_at timestamptz not null default now(),
  primary key (user_id, activity_id)
);

alter table public.gouts enable row level security;

create policy "read my tastes" on public.gouts for select using (auth.uid() = user_id);
create policy "vote" on public.gouts for insert with check (auth.uid() = user_id);
create policy "change my vote" on public.gouts for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "withdraw my vote" on public.gouts for delete using (auth.uid() = user_id);
