-- Sortir de la routine (docs/complicite.md, phase 4): the programme « 4 semaines pour se retrouver » — each week an
-- evening (its wishes for the form), a question to ask each other and a défi, bolder week after week — started by a
-- duo when it likes; and the morning after's review on the Livre's page: the favourite moment of the evening (its
-- « à refaire » and « à éviter » are the couple's votes, public.gouts).

create table public.programme (
  semaine smallint primary key check (semaine between 1 and 4),
  titre text not null,
  texte text not null,
  envies text[] not null, -- wishes of the evening form (surprise.quiz.ENVIES)
  question text not null,
  defi text not null
);
alter table public.programme enable row level security;
create policy "the programme is for every account" on public.programme for select to authenticated using (true);

insert into public.programme (semaine, titre, texte, envies, question, defi) values
  (1, 'Se retrouver', 'Une soirée simple, rien que vous deux : retrouver le plaisir d''être ensemble, sans programme chargé.',
   array['nous', 'cocooning'], 'Qu''est-ce qui t''a donné envie de moi, au tout début ?',
   'Chaque soir de la semaine, dix minutes sans écran, rien qu''à deux.'),
  (2, 'Se redécouvrir', 'Apprendre quelque chose ensemble : la nouveauté partagée rapproche plus que les habitudes.',
   array['curieux', 'creer'], 'Quelle part de toi aimerais-tu que je découvre ?',
   'Faites une chose que vous n''avez jamais faite à deux, même toute petite.'),
  (3, 'Se surprendre', 'Sortir des sentiers battus : des jeux, des défis, des lieux où vous n''auriez jamais pensé aller.',
   array['surprise', 'jouer'], 'Quel rêve as-tu mis de côté, que l''on pourrait réaliser ensemble ?',
   'Organisez chacun une surprise d''une heure pour l''autre.'),
  (4, 'Se promettre', 'Une grande soirée pour clore le mois : celle dont vous vous souviendrez longtemps.',
   array['romantique', 'pimenter'], 'Que veux-tu que l''on garde de ce mois ?',
   'Écrivez-vous une lettre sur ce que ce mois a changé, et lisez-la au dessert.');

-- The duo's programme: the day it began (its weeks follow from it), started again at will.
create table public.programmes_duo (
  duo_id uuid primary key references public.duos(id) on delete cascade,
  started_on date not null default public.paris_today()
);
create table public.programme_faits (
  duo_id uuid not null references public.duos(id) on delete cascade,
  started_on date not null,
  semaine smallint not null references public.programme(semaine),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  done_at timestamptz not null default now(),
  primary key (duo_id, started_on, semaine, user_id)
);
alter table public.programmes_duo enable row level security;
alter table public.programme_faits enable row level security;
create policy "read our programme" on public.programmes_duo for select using (duo_id = public.my_duo());
create policy "read our programme's défis" on public.programme_faits for select using (duo_id = public.my_duo());

create function public.commencer_programme() returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.duo_complete() then
    raise exception 'Formez d''abord votre duo : le programme se vit à deux.';
  end if;
  if exists (select 1 from public.programmes_duo where duo_id = public.my_duo() and public.paris_today() - started_on < 28) then
    raise exception 'Votre programme est en cours : il se recommence une fois ses quatre semaines passées.';
  end if;
  insert into public.programmes_duo (duo_id, started_on) values (public.my_duo(), public.paris_today())
  on conflict (duo_id) do update set started_on = excluded.started_on;
end $$;

-- The programme as the duo lives it: the week it is in (1 to 4; 5 once over), each week open or still ahead, and its
-- défi ticked by each.
create function public.mon_programme(d date default public.paris_today()) returns json
language sql stable security definer set search_path = public as $$
  with mine as (select started_on from public.programmes_duo where duo_id = public.my_duo()),
  now_in as (select least(5, (d - started_on) / 7 + 1)::int as semaine from mine)
  select case when not exists (select 1 from mine) then json_build_object('started_on', null, 'semaine', 0, 'semaines', '[]'::json)
  else json_build_object(
    'started_on', (select started_on from mine),
    'semaine', (select semaine from now_in),
    'semaines', (select json_agg(json_build_object(
        'semaine', p.semaine, 'titre', p.titre, 'texte', p.texte, 'envies', p.envies, 'question', p.question, 'defi', p.defi,
        'ouverte', p.semaine <= (select semaine from now_in),
        'fait_par_moi', exists (select 1 from public.programme_faits f, mine where f.duo_id = public.my_duo()
                                and f.started_on = mine.started_on and f.semaine = p.semaine and f.user_id = auth.uid()),
        'fait_par_l_autre', exists (select 1 from public.programme_faits f, mine where f.duo_id = public.my_duo()
                                and f.started_on = mine.started_on and f.semaine = p.semaine and f.user_id <> auth.uid())
      ) order by p.semaine) from public.programme p)
  ) end
$$;

create function public.programme_fait(semaine_faite smallint) returns void
language plpgsql security definer set search_path = public as $$
declare
  started date := (select started_on from public.programmes_duo where duo_id = public.my_duo());
begin
  if started is null then
    raise exception 'Commencez d''abord le programme.';
  end if;
  if semaine_faite > least(4, (public.paris_today() - started) / 7 + 1) then
    raise exception 'Cette semaine n''est pas encore ouverte.';
  end if;
  insert into public.programme_faits (duo_id, started_on, semaine, user_id)
  values (public.my_duo(), started, semaine_faite, auth.uid()) on conflict do nothing;
end $$;

revoke all on function public.commencer_programme() from public, anon;
revoke all on function public.mon_programme(date) from public, anon;
revoke all on function public.programme_fait(smallint) from public, anon;
grant execute on function public.commencer_programme() to authenticated;
grant execute on function public.mon_programme(date) to authenticated;
grant execute on function public.programme_fait(smallint) to authenticated;

-- The morning after: each one's favourite moment of an evening (a step's id), read by the evening's people once their
-- own is given, as the Livre's pages.
create table public.bilans (
  soiree_id text not null references public.soirees_choisies(id) on delete cascade,
  author uuid not null default auth.uid() references auth.users(id) on delete cascade,
  prefere text not null, -- the step: source_id:external_id
  prefere_titre text not null default '',
  created_at timestamptz not null default now(),
  primary key (soiree_id, author)
);
alter table public.bilans enable row level security;

create function public.reviewed_by_me(sid text) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.bilans where soiree_id = sid and author = auth.uid())
$$;
revoke all on function public.reviewed_by_me(text) from public, anon;
grant execute on function public.reviewed_by_me(text) to authenticated;

create policy "read the reviews" on public.bilans for select using (
  exists (select 1 from public.soirees_choisies s where s.id = soiree_id)
  and (author = auth.uid() or public.reviewed_by_me(soiree_id))
);
create policy "give my review" on public.bilans for insert with check (
  author = auth.uid() and exists (select 1 from public.soirees_choisies s where s.id = soiree_id and s.day <= public.paris_today())
);

-- The gauge, the programme's défis counted with the week's.
create or replace function public.complicite() returns json
language sql stable security definer set search_path = public as $$
  with two as (
    select user_id from public.duo_members where duo_id = public.my_duo()
    union select auth.uid()
  ), lived as (
    select s.id from public.soirees_choisies s
    where s.formule = 'duo' and s.day < public.paris_today()
      and (s.user_id = auth.uid() or exists (select 1 from public.soiree_invites i where i.soiree_id = s.id and i.user_id = auth.uid()))
  ), quiz as (
    select a.semaine, a.question_id, a.moi, a.devine, b.moi as sien_moi, b.devine as sien_devine
    from public.quiz_reponses a
    join public.quiz_reponses b on b.duo_id = a.duo_id and b.semaine = a.semaine and b.question_id = a.question_id and b.author <> a.author
    where a.duo_id = public.my_duo() and a.author = auth.uid()
  )
  select json_build_object(
    'duo', public.my_duo() is not null,
    'complet', public.duo_complete(),
    'soirees', (select count(*) from lived),
    'pages', (select count(*) from public.souvenirs p where p.soiree_id in (select id from lived) and p.author in (select user_id from two)),
    'reponses', (select count(*) from (
      select day from public.reponses_du_jour where duo_id = public.my_duo() group by day having count(*) = 2
    ) paired),
    'quiz', (select count(*) from (select semaine from quiz group by semaine having count(*) = 8) finished),
    'devinettes', (select count(*) filter (where devine = sien_moi) + count(*) filter (where sien_devine = moi) from quiz),
    'defis', (select count(*) from (
      select semaine from public.defis_faits where duo_id = public.my_duo() group by semaine having count(*) = 2
    ) both_done) + (select count(*) from (
      select started_on, semaine from public.programme_faits where duo_id = public.my_duo() group by started_on, semaine having count(*) = 2
    ) programme_done)
  )
$$;
