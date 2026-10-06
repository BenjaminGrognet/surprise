-- Secret Squad: an evening for a band of friends (3 to 10: a hen or stag party, a birthday…), beside Secret Date's
-- for two. A kept evening says its formula and how many go out. Its guests are no longer one passager on its row but
-- its invites (soiree_invites), for both formulas: a couple's evening has one passager at most; a band's as many guests
-- as it has places, passagers (the clues only) and complices — friends in on the secret (a hen party's witnesses), who
-- see the whole evening and tick its bookings, and who join by a link of their own (soiree_codes, which a passager
-- never reads: it would lift the veil).

alter table public.soirees_choisies
  add column formule text not null default 'duo' check (formule in ('duo', 'squad')),
  add column personnes integer not null default 2 check (personnes between 2 and 10),
  add constraint soirees_choisies_party check ((formule = 'duo') = (personnes = 2));

create table public.soiree_invites (
  soiree_id text not null references public.soirees_choisies(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  email text,
  role text not null default 'passager' check (role in ('passager', 'complice')),
  joined_at timestamptz not null default now(),
  primary key (soiree_id, user_id)
);
create index soiree_invites_user_idx on public.soiree_invites(user_id);
alter table public.soiree_invites enable row level security;

-- The passagers already joined, as the evenings' first invites.
insert into public.soiree_invites (soiree_id, user_id, email, role, joined_at)
select id, passager, passager_email, 'passager', coalesce(joined_at, now())
from public.soirees_choisies where passager is not null;

drop policy "passager reads their evenings" on public.soirees_choisies;
alter table public.soirees_choisies drop column passager, drop column passager_email, drop column joined_at;

-- Whether the signed-in account is a guest of this evening (as this role, if given): a definer function, so that the
-- policies of soirees_choisies and soiree_invites can ask without reading each other under their own rules.
create function public.invited_to(sid text, as_role text default null) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.soiree_invites
    where soiree_id = sid and user_id = auth.uid() and (as_role is null or role = as_role)
  )
$$;
revoke all on function public.invited_to(text, text) from public, anon;
grant execute on function public.invited_to(text, text) to authenticated;

create function public.organises(sid text) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.soirees_choisies where id = sid and user_id = auth.uid())
$$;
revoke all on function public.organises(text) from public, anon;
grant execute on function public.organises(text) to authenticated;

-- Each guest reads the evening (its book and photos follow: their policies ask soirees_choisies).
create policy "guests read their evenings" on public.soirees_choisies
  for select using (public.invited_to(id));

-- The band, seen by its instigateur and by each of its guests; the instigateur lets one go, a guest may leave.
create policy "the band sees the band" on public.soiree_invites
  for select using (public.organises(soiree_id) or public.invited_to(soiree_id));
create policy "let a guest go, or leave" on public.soiree_invites
  for delete using (public.organises(soiree_id) or user_id = auth.uid());

-- The complices' link of a band's evening, drawn when it is kept: read by its instigateur and its complices only.
create table public.soiree_codes (
  soiree_id text primary key references public.soirees_choisies(id) on delete cascade,
  complice_code text not null unique default substr(md5(gen_random_uuid()::text), 1, 12)
);
alter table public.soiree_codes enable row level security;
create policy "the organisers read the complices link" on public.soiree_codes
  for select using (public.organises(soiree_id) or public.invited_to(soiree_id, 'complice'));

create function public.complice_code_for_a_band() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if new.formule = 'squad' then
    insert into public.soiree_codes (soiree_id) values (new.id);
  end if;
  return new;
end $$;
create trigger complice_code_for_a_band after insert on public.soirees_choisies
  for each row execute function public.complice_code_for_a_band();

-- A guest joins by the evening's link: the passagers' (invite_code) or the complices' (soiree_codes), while it has
-- places (personnes, the instigateur counted). The role joined is returned; a guest already in keeps theirs.
drop function public.join_evening(text);
create function public.join_evening(code text) returns text
language plpgsql security definer set search_path = public as $$
declare
  s public.soirees_choisies;
  joined text := 'passager';
  already text;
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  select * into s from public.soirees_choisies where invite_code = code for update;
  if not found then
    select e.* into s from public.soirees_choisies e join public.soiree_codes c on c.soiree_id = e.id
    where c.complice_code = code for update of e;
    if not found then
      raise exception 'Invitation introuvable : demandez un nouveau lien.';
    end if;
    joined := 'complice';
  end if;
  if s.user_id = auth.uid() then
    raise exception '%', case when s.formule = 'squad' then 'C''est votre propre invitation : envoyez-la à votre bande.'
                              else 'C''est votre propre invitation : envoyez-la à votre passager.' end;
  end if;
  select role into already from public.soiree_invites where soiree_id = s.id and user_id = auth.uid();
  if found then
    return already;
  end if;
  if (select count(*) from public.soiree_invites where soiree_id = s.id) >= s.personnes - 1 then
    raise exception '%', case when s.formule = 'squad' then 'La bande est au complet : demandez une place de plus à l''organisateur.'
                              else 'Cette invitation a déjà été acceptée.' end;
  end if;
  insert into public.soiree_invites (soiree_id, user_id, email, role)
  values (s.id, auth.uid(), auth.jwt() ->> 'email', joined);
  return joined;
end $$;
revoke all on function public.join_evening(text) from public, anon;
grant execute on function public.join_evening(text) to authenticated;

-- Its passagers let go, a fresh link drawn for the evening (its complices stay).
create or replace function public.reset_passager(sid text) returns void
language plpgsql security definer set search_path = public as $$
begin
  update public.soirees_choisies
  set invite_code = substr(md5(gen_random_uuid()::text), 1, 12)
  where id = sid and user_id = auth.uid();
  if not found then
    raise exception 'Soirée introuvable.';
  end if;
  delete from public.soiree_invites where soiree_id = sid and role = 'passager';
end $$;

-- What is booked for the evening, ticked by its instigateur or one of its complices (Les Coulisses).
create function public.save_booked(sid text, steps text[]) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not (public.organises(sid) or public.invited_to(sid, 'complice')) then
    raise exception 'Cette soirée n''est pas gardée sur votre compte.';
  end if;
  update public.soirees_choisies set booked = steps where id = sid;
end $$;
revoke all on function public.save_booked(text, text[]) from public, anon;
grant execute on function public.save_booked(text, text[]) to authenticated;
