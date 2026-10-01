-- The passager now belongs to an evening, not to the account: an instigateur can keep several evenings, each with
-- its own passager (one passager at most per evening), invited by a link from that evening. This replaces
-- public.couples. Also: an instigateur deletes a past evening (its book goes with it, cascade), and anyone deletes
-- their own account.

alter table public.soirees_choisies
  add column passager uuid references auth.users(id) on delete set null,
  add column passager_email text,
  add column invite_code text not null default substr(md5(gen_random_uuid()::text), 1, 12),
  add column joined_at timestamptz;
create unique index soirees_choisies_invite_code_key on public.soirees_choisies(invite_code);
create index soirees_choisies_passager_idx on public.soirees_choisies(passager);

-- The couples already formed: their passager joins every evening the instigateur has kept.
update public.soirees_choisies s
set passager = c.passager, passager_email = c.passager_email, joined_at = c.joined_at
from public.couples c
where c.instigateur = s.user_id and c.passager is not null;

drop policy "passager reads the couple's evenings" on public.soirees_choisies;
drop function public.join_couple(text);
drop table public.couples;

create policy "passager reads their evenings" on public.soirees_choisies
  for select using (auth.uid() = passager);

-- A past evening goes (its souvenirs follow). Only its instigateur, only once its day is over.
create policy "delete a past evening" on public.soirees_choisies
  for delete using (auth.uid() = user_id and (day is null or day < current_date));

-- The passager joins through the evening's code: they can't read the evening before joining, hence a definer function.
create function public.join_evening(code text) returns void
language plpgsql security definer set search_path = public as $$
declare
  s public.soirees_choisies;
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  select * into s from public.soirees_choisies where invite_code = code for update;
  if not found then
    raise exception 'Invitation introuvable : demandez un nouveau lien.';
  end if;
  if s.user_id = auth.uid() then
    raise exception 'C''est votre propre invitation : envoyez-la à votre passager.';
  end if;
  if s.passager is not null and s.passager <> auth.uid() then
    raise exception 'Cette invitation a déjà été acceptée.';
  end if;
  if exists (select 1 from public.soirees_choisies where user_id = auth.uid()) then
    raise exception 'Ce compte organise déjà ses propres intrigues : créez un autre compte pour être passager.';
  end if;
  update public.soirees_choisies
  set passager = auth.uid(), passager_email = auth.jwt() ->> 'email', joined_at = now()
  where id = s.id;
end $$;

revoke all on function public.join_evening(text) from public, anon;
grant execute on function public.join_evening(text) to authenticated;

-- Let the passager go, a fresh link drawn for the evening.
create function public.reset_passager(sid text) returns void
language plpgsql security definer set search_path = public as $$
begin
  update public.soirees_choisies
  set passager = null, passager_email = null, joined_at = null,
      invite_code = substr(md5(gen_random_uuid()::text), 1, 12)
  where id = sid and user_id = auth.uid();
  if not found then
    raise exception 'Soirée introuvable.';
  end if;
end $$;

revoke all on function public.reset_passager(text) from public, anon;
grant execute on function public.reset_passager(text) to authenticated;

-- The photos of an evening are removed (through the storage API) before it goes: its instigateur may delete them.
create policy "remove the fragments of my evening" on storage.objects
  for delete to authenticated using (
    bucket_id = 'souvenirs'
    and ((storage.foldername(name))[2] = auth.uid()::text
         or exists (select 1 from public.soirees_choisies s
                    where s.id = (storage.foldername(name))[1] and s.user_id = auth.uid()))
  );

-- Account deletion: the auth row goes, and with it the profile, the evenings, the pages (cascade); an evening
-- where the account was passager just loses its passager (set null).
create function public.delete_my_account() returns void
language plpgsql security definer set search_path = public, auth as $$
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  delete from auth.users where id = auth.uid();
end $$;

revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;
