-- Outing types from the fixed taxonomy in src/surprise/categories.py.
alter table public.activities add column categories text[] not null default '{}';
create index activities_categories_idx on public.activities using gin (categories);
