-- Le Livre des Secrets: at the end of a kept evening, or the day after, each of the couple seals one page of its
-- book — a photo, a note. Sealed is final (no update): the history then keeps the memory instead of the route.
-- Each one reads the other's page only once their own is sealed.

create table public.souvenirs (
  soiree_id text not null references public.soirees_choisies(id) on delete cascade,
  author uuid not null default auth.uid() references auth.users(id) on delete cascade,
  note text not null default '',
  photo text, -- its path in the souvenirs bucket: <soiree_id>/<author>/<file>
  sealed_at timestamptz not null default now(),
  primary key (soiree_id, author)
);

alter table public.souvenirs enable row level security;

-- Whether the signed-in account sealed its page of this evening: a definer function, a policy on souvenirs
-- can't read souvenirs itself.
create function public.sealed_by_me(sid text) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.souvenirs where soiree_id = sid and author = auth.uid())
$$;

revoke all on function public.sealed_by_me(text) from public, anon;
grant execute on function public.sealed_by_me(text) to authenticated;

-- The evening must be one the account sees (soirees_choisies' own policies: its instigateur, its passager).
create policy "read the book" on public.souvenirs
  for select using (
    exists (select 1 from public.soirees_choisies s where s.id = soiree_id)
    and (author = auth.uid() or public.sealed_by_me(soiree_id))
  );
create policy "seal my page" on public.souvenirs
  for insert with check (
    author = auth.uid() and exists (select 1 from public.soirees_choisies s where s.id = soiree_id)
  );

-- The photos, private: read through signed links, under the same rule as the notes.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('souvenirs', 'souvenirs', false, 15728640, array['image/*'])
on conflict (id) do nothing;

create policy "drop a fragment" on storage.objects
  for insert to authenticated with check (
    bucket_id = 'souvenirs'
    and (storage.foldername(name))[2] = auth.uid()::text
    and exists (select 1 from public.soirees_choisies s where s.id = (storage.foldername(name))[1])
    and not public.sealed_by_me((storage.foldername(name))[1])
  );
create policy "see the fragments" on storage.objects
  for select to authenticated using (
    bucket_id = 'souvenirs'
    and exists (select 1 from public.soirees_choisies s where s.id = (storage.foldername(name))[1])
    and ((storage.foldername(name))[2] = auth.uid()::text or public.sealed_by_me((storage.foldername(name))[1]))
  );
