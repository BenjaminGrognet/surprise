-- Emails beside the phone's notifications (surprise.courriers): the key moments of each kept evening, by email to its
-- accounts — the instigateur's reminders, the passager's sealed letter and eve, the morning after, their turn — and the
-- invitations an instigateur sends by email from the app. What was sent is noted, so that nothing goes twice; anyone may
-- stop them, from the app or from a link in each email.

-- An account's choice: its emails or none (no row: yes). Its own row only.
create table public.email_prefs (
  user_id uuid primary key default auth.uid() references auth.users(id) on delete cascade,
  emails boolean not null default true,
  updated_at timestamptz not null default now()
);
alter table public.email_prefs enable row level security;
create policy "read my email choice" on public.email_prefs for select using (auth.uid() = user_id);
create policy "make my email choice" on public.email_prefs for insert with check (auth.uid() = user_id);
create policy "change my email choice" on public.email_prefs for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- An invitation to an evening sent by email (its passagers' link, or a band's complices'), to an address the
-- instigateur gives: the server sends it (sent_at). Seen by the evening's organisers.
create table public.email_invitations (
  id uuid primary key default gen_random_uuid(),
  soiree_id text not null references public.soirees_choisies(id) on delete cascade,
  email text not null,
  role text not null default 'passager' check (role in ('passager', 'complice')),
  invited_by uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  sent_at timestamptz
);
create index email_invitations_soiree on public.email_invitations (soiree_id);
alter table public.email_invitations enable row level security;
create policy "the organisers see the invitations sent" on public.email_invitations
  for select using (public.organises(soiree_id) or invited_by = auth.uid());

-- Through this function only: its instigateur (a complice too, for the passagers' link of a band's evening), a valid
-- address, an evening still to come, and few of them — nobody mails strangers through Secret Date.
create function public.invite_by_email(sid text, address text, as_role text default 'passager') returns uuid
language plpgsql security definer set search_path = public as $$
declare
  s public.soirees_choisies;
  made uuid;
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  select * into s from public.soirees_choisies where id = sid;
  if not found or not (s.user_id = auth.uid() or (as_role = 'passager' and public.invited_to(sid, 'complice'))) then
    raise exception 'Cette soirée n''est pas gardée sur votre compte.';
  end if;
  if as_role not in ('passager', 'complice') or (as_role = 'complice' and s.formule <> 'squad') then
    raise exception 'Invitation inconnue.';
  end if;
  if s.day is not null and s.day < current_date then
    raise exception 'Cette soirée est passée.';
  end if;
  address := lower(trim(address));
  if address !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' or length(address) > 254 then
    raise exception 'Cet email n''est pas valide.';
  end if;
  if (select count(*) from public.email_invitations where invited_by = auth.uid() and created_at > now() - interval '1 day') >= 20 then
    raise exception 'Trop d''invitations envoyées aujourd''hui : réessayez demain.';
  end if;
  if (select count(*) from public.email_invitations where soiree_id = sid) >= s.personnes + 4 then
    raise exception 'Assez d''invitations pour cette soirée : partagez plutôt son lien.';
  end if;
  insert into public.email_invitations (soiree_id, email, role) values (sid, address, as_role) returning id into made;
  return made;
end $$;
revoke all on function public.invite_by_email(text, text, text) from public, anon;
grant execute on function public.invite_by_email(text, text, text) to authenticated;

-- What the server sent, once each: an evening's moment to a recipient (an address, or a device's account for a push).
create table pipeline.courriers (
  soiree_id text not null,
  moment text not null,
  recipient text not null,
  sent_at timestamptz not null default now(),
  primary key (soiree_id, moment, recipient)
);

-- Addresses that stopped the emails from a link, account or not.
create table pipeline.courriels_stop (
  address text primary key,
  stopped_at timestamptz not null default now()
);
