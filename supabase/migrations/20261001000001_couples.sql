-- Two accounts per couple. The instigateur makes the profile and orders the evenings; the passager, invited
-- by a link (invite_code), only ever gets the clues. Any account without a couple, or the one that created it,
-- is an instigateur; an account that joined one is its passager. One couple per instigateur, one per passager.

create table public.couples (
  id uuid primary key default gen_random_uuid(),
  instigateur uuid not null unique references auth.users(id) on delete cascade,
  instigateur_email text, -- shown to the passager: who invited them
  passager uuid unique references auth.users(id) on delete set null,
  passager_email text,
  invite_code text not null unique default substr(md5(gen_random_uuid()::text), 1, 12),
  created_at timestamptz not null default now(),
  joined_at timestamptz
);

alter table public.couples enable row level security;

create policy "select own couple" on public.couples
  for select using (auth.uid() = instigateur or auth.uid() = passager);
create policy "instigateur creates the couple" on public.couples
  for insert with check (auth.uid() = instigateur and passager is null);
-- No update: a new invitation (or a passager let go) is a fresh couple, the old one deleted.
create policy "instigateur deletes the couple" on public.couples
  for delete using (auth.uid() = instigateur);

-- The passager joins through the code: they can't read the couple before joining, hence a definer function.
create function public.join_couple(code text) returns void
language plpgsql security definer set search_path = public as $$
declare
  c public.couples;
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  select * into c from public.couples where invite_code = code for update;
  if not found then
    raise exception 'Invitation introuvable : demandez un nouveau lien.';
  end if;
  if c.instigateur = auth.uid() then
    raise exception 'C''est votre propre invitation : envoyez-la à votre passager.';
  end if;
  if c.passager is not null and c.passager <> auth.uid() then
    raise exception 'Cette invitation a déjà été acceptée.';
  end if;
  if exists (select 1 from public.couples where instigateur = auth.uid()) then
    raise exception 'Ce compte organise déjà ses propres intrigues : créez un autre compte pour être passager.';
  end if;
  if exists (select 1 from public.couples where passager = auth.uid() and id <> c.id) then
    raise exception 'Ce compte est déjà le passager d''une autre intrigue.';
  end if;
  update public.couples set passager = auth.uid(), passager_email = auth.jwt() ->> 'email', joined_at = now()
  where id = c.id;
end $$;

revoke all on function public.join_couple(text) from public, anon;
grant execute on function public.join_couple(text) to authenticated;

-- The passager sees the evenings their instigateur keeps (the app shows them only as clues).
create policy "passager reads the couple's evenings" on public.soirees_choisies
  for select using (
    exists (select 1 from public.couples c where c.instigateur = soirees_choisies.user_id and c.passager = auth.uid())
  );
