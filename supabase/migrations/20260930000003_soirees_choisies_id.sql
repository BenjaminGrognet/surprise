-- The app inserts a chosen evening without an id: the database draws one, as the web client did.
alter table public.soirees_choisies alter column id set default gen_random_uuid()::text;
