-- A composed evening's candidates (surprise.parcours.Candidate, each activity by its key), kept while the couple
-- picks one of its routes: a redraw (a step, a route) starts from them instead of reading the whole base and
-- checking the booking engines again. They go once a route is chosen, or after a few hours (the engines' answers age).
create table if not exists pipeline.soiree_candidates (
  soiree_id text not null references pipeline.soirees (id) on delete cascade,
  request integer not null,  -- its evening in soirees.requests
  candidates jsonb not null,
  created_at timestamptz not null default now(),
  primary key (soiree_id, request)
);

-- Once the couple chose a route, the evening is that route alone (route 0): the other routes go, and the
-- evening's id is enough to find it (the app's links lose their &route=, which let anyone open another route).
alter table pipeline.soirees add column if not exists chosen_at timestamptz;

-- The evenings already kept: each one keeps its route only.
create temporary table kept as
  select distinct on (page_name) page_name, route_index, chosen_at
  from public.soirees_choisies order by page_name, chosen_at desc;
delete from pipeline.soiree_steps s using kept k where s.soiree_id = k.page_name and s.route <> k.route_index;
delete from pipeline.soiree_routes r using kept k where r.soiree_id = k.page_name and r.route <> k.route_index;
update pipeline.soiree_steps s set route = 0 from kept k where s.soiree_id = k.page_name;
update pipeline.soiree_routes r set route = 0 from kept k where r.soiree_id = k.page_name;
update pipeline.soirees p set chosen_at = k.chosen_at from kept k where p.id = k.page_name;
drop table kept;

alter table public.soirees_choisies drop column route_index;
-- One kept evening per page: keeping it again (a second tap) changes nothing.
create unique index if not exists soirees_choisies_page_name_key on public.soirees_choisies (page_name);
