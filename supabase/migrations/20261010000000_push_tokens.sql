-- Push notifications (Firebase Cloud Messaging): each device's FCM token, the browser's or the Android phone's, kept
-- for the account signed in on it, so that the server can reach it (surprise.push). A device has one account at a
-- time: signed in on another, its token goes with it; signed out, it is forgotten. Gone with the account (cascade).

create table public.push_tokens (
  token text primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  platform text not null check (platform in ('web', 'android')),
  updated_at timestamptz not null default now()
);

create index push_tokens_user on public.push_tokens (user_id);

alter table public.push_tokens enable row level security;

create policy "read my devices" on public.push_tokens for select using (auth.uid() = user_id);
create policy "forget my device" on public.push_tokens for delete using (auth.uid() = user_id);

-- The token is the device's own: whoever holds it signs it in to their account, even from another one's (the phone
-- passed on, a sign-out that never reached the server), hence a definer function.
create function public.register_push_token(token text, platform text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  insert into public.push_tokens as t (token, user_id, platform)
  values (register_push_token.token, auth.uid(), register_push_token.platform)
  on conflict on constraint push_tokens_pkey
  do update set user_id = auth.uid(), platform = excluded.platform, updated_at = now();
end $$;

revoke all on function public.register_push_token(text, text) from public, anon;
grant execute on function public.register_push_token(text, text) to authenticated;
