-- A couple's order (docs/complicite.md, A1): their profile first (surprise.quiz), then the questions du jour, from the
-- day after their first evening for two lived through the app, a little in their image: the journey from the lightest
-- to the most intimate stays, each duo's order moved by its profile's answers.

-- The duo's profile: the account's own, else its partner's (the latest). couple_profiles stays each one's to read: a
-- partner's is read through here only, and only its answers and profile.
create function public.profil_du_duo() returns json
language sql stable security definer set search_path = public as $$
  select json_build_object('answers', c.answers, 'profile', c.profile)
  from public.couple_profiles c
  where c.user_id = auth.uid() or c.user_id in (select user_id from public.duo_members where duo_id = public.my_duo())
  order by c.user_id = auth.uid() desc, c.created_at desc
  limit 1
$$;
revoke all on function public.profil_du_duo() from public, anon;
grant execute on function public.profil_du_duo() to authenticated;

-- The duo's evenings for two (the account's alone without a duo): chosen by one of them, or one of them invited to it.
create function public.soirees_du_duo() returns setof date
language sql stable security definer set search_path = public as $$
  with two as (select user_id from public.duo_members where duo_id = public.my_duo() union select auth.uid())
  select s.day from public.soirees_choisies s
  where s.formule = 'duo' and s.day is not null
    and (s.user_id in (select user_id from two)
         or exists (select 1 from public.soiree_invites i where i.soiree_id = s.id and i.user_id in (select user_id from two)))
$$;
revoke all on function public.soirees_du_duo() from public, anon;

-- Their first evening: the first lived (its day passed), else the next one chosen.
create function public.premiere_soiree() returns json
language sql stable security definer set search_path = public as $$
  select json_build_object(
    'vecue', (select min(day) from public.soirees_du_duo() day where day < public.paris_today()),
    'prevue', (select min(day) from public.soirees_du_duo() day where day >= public.paris_today()))
$$;
revoke all on function public.premiere_soiree() from public, anon;
grant execute on function public.premiere_soiree() to authenticated;

-- The questions du jour have begun on day d: the day after their first evening lived (or they already answered one).
create function public.questions_commencees(d date default public.paris_today()) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.soirees_du_duo() day where day < d)
      or exists (select 1 from public.reponses_du_jour where duo_id = public.my_duo() and day < d)
$$;
revoke all on function public.questions_commencees(date) from public, anon;
grant execute on function public.questions_commencees(date) to authenticated;

-- A question's place in the duo's journey: its rank, moved a little by the profile's answers; null, never for this
-- duo. A couple discovering each other meets the most intimate later, a long story sooner; a couple who laugh first
-- meets the absurd and the « tu préfères » sooner, a curious one the values; the bold the désir sooner, the classic
-- later, and never those who want nothing « coquin ». Without a profile, the journey as written.
create function public.rang_question(q public.questions_du_jour, a jsonb) returns integer
language sql immutable as $$
  select case
    when q.theme = 'désir' and coalesce(a->'eviter', '[]'::jsonb) ? 'coquin' then null
    else q.id
      + case when q.profondeur >= 3 then
          case a->>'couple' when 'debut' then 25 when 'installes' then -10 when 'longue' then -15 else 0 end else 0 end
      + case when q.theme in ('absurde', 'tu préfères') and coalesce(a->'reussie', '[]'::jsonb) ? 'rire' then -6 else 0 end
      + case when q.theme = 'valeurs' and coalesce(a->'reussie', '[]'::jsonb) ? 'appris' then -6 else 0 end
      + case when q.theme = 'désir' then
          case a->>'audace' when 'fou' then -12 when 'surprenez' then -6 when 'classique' then 15 else 0 end else 0 end
      + case when q.theme in ('nous', 'souvenirs') and a->>'debut_soiree' = 'cocon' then -4 else 0 end
      + case when q.theme = 'absurde' and a->>'debut_soiree' in ('defi', 'creer') then -4 else 0 end
      + case when q.theme = 'quotidien' and a->>'couple' = 'debut' then 10 else 0 end
  end
$$;

-- The day's question of the account's duo: the next of its journey, after as many as the days one of them answered
-- (both see the same, and it waits for them); once all met, the journey starts again.
create or replace function public.question_du_jour(d date default public.paris_today()) returns public.questions_du_jour
language sql stable security definer set search_path = public as $$
  with journey as (
    select q.*, public.rang_question(q, (public.profil_du_duo()->'answers')::jsonb) as rang from public.questions_du_jour q
  )
  select id, profondeur, theme, texte from journey where rang is not null
  order by rang, id
  offset mod(
    (select count(distinct day) from public.reponses_du_jour where duo_id = public.my_duo() and day < d)::int,
    greatest((select count(*) from journey where rang is not null), 1)::int)
  limit 1
$$;

-- The day's question for the account's duo, once begun (`commence`; before, their first evening: `premiere`), with
-- whether it follows their profile (`adaptee`).
create or replace function public.mon_jour(d date default public.paris_today()) returns json
language sql stable security definer set search_path = public as $$
  with started as (select public.questions_commencees(d) as yes),
  q as (select * from public.question_du_jour(d) where (select yes from started)),
  mine as (select texte from public.reponses_du_jour where duo_id = public.my_duo() and day = d and author = auth.uid()),
  theirs as (select texte from public.reponses_du_jour where duo_id = public.my_duo() and day = d and author <> auth.uid())
  select json_build_object(
    'day', d,
    'commence', (select yes from started),
    'premiere', case when not (select yes from started) then public.premiere_soiree() end,
    'adaptee', public.profil_du_duo() is not null,
    'question', (select json_build_object('id', id, 'texte', texte, 'theme', theme, 'profondeur', profondeur) from q),
    'mienne', (select texte from mine),
    'sienne_donnee', exists (select 1 from theirs),
    'sienne', case when exists (select 1 from mine) then (select texte from theirs) end
  )
$$;

-- The account answers today's question, once: its duo complete, its first evening lived.
create or replace function public.repondre_du_jour(texte text) returns void
language plpgsql security definer set search_path = public as $$
declare
  today date := public.paris_today();
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  if not public.duo_complete() then
    raise exception 'Formez d''abord votre duo : la question du jour se joue à deux.';
  end if;
  if not public.questions_commencees(today) then
    raise exception 'Vos questions du jour commencent au lendemain de votre première soirée à deux.';
  end if;
  if length(trim(coalesce(texte, ''))) = 0 then
    raise exception 'Écrivez votre réponse avant de la sceller.';
  end if;
  if public.answered_on(today) then
    raise exception 'Votre réponse est déjà scellée.';
  end if;
  insert into public.reponses_du_jour (duo_id, day, author, question_id, texte)
  values (public.my_duo(), today, auth.uid(), (select id from public.question_du_jour(today)), left(trim(texte), 1000));
end $$;
