-- Le duo, la question du jour et la jauge (docs/complicite.md, phase 1). The questions, quizzes, défis and the
-- complicity gauge belong to two people, not to an evening: the duo links two accounts, one duo per account. It forms
-- by itself when a passager joins an evening for two, or by a code from « Mon couple »; leaving it dissolves it.
-- Each day, one question for both, sealed as the Livre is: each reads the other's answer once their own is given.

-- Paris's day, the app's: a day's question changes at midnight in Paris, wherever the server runs.
create function public.paris_today() returns date
language sql stable as $$ select (now() at time zone 'Europe/Paris')::date $$;

create table public.duos (
  id uuid primary key default gen_random_uuid(),
  code text not null unique default substr(md5(gen_random_uuid()::text), 1, 8),
  created_at timestamptz not null default now()
);
create table public.duo_members (
  user_id uuid primary key references auth.users(id) on delete cascade, -- one duo per account
  duo_id uuid not null references public.duos(id) on delete cascade,
  email text,
  joined_at timestamptz not null default now()
);
create index duo_members_duo_idx on public.duo_members(duo_id);
alter table public.duos enable row level security;
alter table public.duo_members enable row level security;

-- The signed-in account's duo, and whether its two are there: definer functions, so that the policies can ask
-- without reading duo_members under its own rules.
create function public.my_duo() returns uuid
language sql stable security definer set search_path = public as $$
  select duo_id from public.duo_members where user_id = auth.uid()
$$;
create function public.duo_complete() returns boolean
language sql stable security definer set search_path = public as $$
  select count(*) = 2 from public.duo_members where duo_id = public.my_duo()
$$;
revoke all on function public.my_duo() from public, anon;
revoke all on function public.duo_complete() from public, anon;
grant execute on function public.my_duo() to authenticated;
grant execute on function public.duo_complete() to authenticated;

create policy "read my duo" on public.duos for select using (id = public.my_duo());
create policy "read my duo's two" on public.duo_members for select using (duo_id = public.my_duo());

-- Two accounts paired, if they can be: neither in a duo yet (a new one), or one waiting alone in its duo (the other
-- joins it). Otherwise nothing: an account already paired with someone else stays so.
create function public.pair_duo(one uuid, other uuid) returns void
language plpgsql security definer set search_path = public, auth as $$
declare
  d1 uuid := (select duo_id from public.duo_members where user_id = one);
  d2 uuid := (select duo_id from public.duo_members where user_id = other);
  joined uuid;
begin
  if one = other then
    return;
  end if;
  if d1 is null and d2 is null then
    insert into public.duos default values returning id into joined;
    insert into public.duo_members (user_id, duo_id, email)
    select id, joined, email from auth.users where id in (one, other);
  elsif d1 is not null and d2 is null and (select count(*) from public.duo_members where duo_id = d1) = 1 then
    insert into public.duo_members (user_id, duo_id, email) select id, d1, email from auth.users where id = other;
  elsif d2 is not null and d1 is null and (select count(*) from public.duo_members where duo_id = d2) = 1 then
    insert into public.duo_members (user_id, duo_id, email) select id, d2, email from auth.users where id = one;
  end if;
end $$;
revoke all on function public.pair_duo(uuid, uuid) from public, anon, authenticated;

-- A passager joining an evening for two pairs with its instigateur. A band's evening (Secret Squad) never does.
create function public.pair_on_join() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  s public.soirees_choisies;
begin
  select * into s from public.soirees_choisies where id = new.soiree_id;
  if new.role = 'passager' and s.formule = 'duo' then
    perform public.pair_duo(s.user_id, new.user_id);
  end if;
  return new;
end $$;
create trigger pair_on_join after insert on public.soiree_invites
  for each row execute function public.pair_on_join();

-- The couples already formed by their evenings for two: paired now, the latest evening first.
do $$
declare
  r record;
begin
  for r in
    select s.user_id as one, i.user_id as other
    from public.soiree_invites i join public.soirees_choisies s on s.id = i.soiree_id
    where i.role = 'passager' and s.formule = 'duo'
    order by i.joined_at desc
  loop
    perform public.pair_duo(r.one, r.other);
  end loop;
end $$;

-- « Mon couple »: the account's duo opened (alone until the other joins), its code to send.
create function public.open_duo() returns text
language plpgsql security definer set search_path = public, auth as $$
declare
  found_code text;
  made uuid;
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  select d.code into found_code from public.duos d where d.id = public.my_duo();
  if found_code is not null then
    return found_code;
  end if;
  insert into public.duos default values returning id, code into made, found_code;
  insert into public.duo_members (user_id, duo_id, email) values (auth.uid(), made, auth.jwt() ->> 'email');
  return found_code;
end $$;

create function public.join_duo(given text) returns void
language plpgsql security definer set search_path = public as $$
declare
  d public.duos;
  mine uuid := public.my_duo();
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  select * into d from public.duos where code = lower(trim(given)) for update;
  if not found then
    raise exception 'Code introuvable : demandez-le à nouveau à votre moitié.';
  end if;
  if mine = d.id then
    if (select count(*) from public.duo_members where duo_id = d.id) = 1 then
      raise exception 'C''est votre propre code : envoyez-le à votre moitié.';
    end if;
    return; -- already together
  end if;
  if (select count(*) from public.duo_members where duo_id = d.id) >= 2 then
    raise exception 'Ce duo est déjà complet.';
  end if;
  if mine is not null then
    if (select count(*) from public.duo_members where duo_id = mine) = 2 then
      raise exception 'Vous formez déjà un duo : quittez-le d''abord.';
    end if;
    delete from public.duos where id = mine; -- the account's own duo, still waiting alone, gives way
  end if;
  insert into public.duo_members (user_id, duo_id, email) values (auth.uid(), d.id, auth.jwt() ->> 'email');
end $$;

-- Leaving dissolves the duo: its answers go with it (cascade). The evenings and their Livre stay.
create function public.leave_duo() returns void
language sql security definer set search_path = public as $$
  delete from public.duos where id = public.my_duo()
$$;

revoke all on function public.open_duo() from public, anon;
revoke all on function public.join_duo(text) from public, anon;
revoke all on function public.leave_duo() from public, anon;
grant execute on function public.open_duo() to authenticated;
grant execute on function public.join_duo(text) to authenticated;
grant execute on function public.leave_duo() to authenticated;

-- The day's questions, written for the app in the spirit of the couple quizzes and question games (docs/complicite.md):
-- four paliers — 1 Pour rire (absurd, « tu préfères », daily traps), 2 Se raconter (memories, childhood), 3 Nous deux,
-- 4 À cœur ouvert —, in the order of the journey (id): a duo meets them one after the other, the next only once one of
-- them answered; a light one now and then on the way, to breathe.
create table public.questions_du_jour (
  id integer primary key,
  profondeur smallint not null check (profondeur between 1 and 4), -- the palier
  theme text not null,
  texte text not null
);
alter table public.questions_du_jour enable row level security;
create policy "the questions are for every account" on public.questions_du_jour for select to authenticated using (true);

insert into public.questions_du_jour (id, profondeur, theme, texte) values
  (1, 1, 'absurde', 'Si nos deux vies étaient une série, quel serait le titre de l''épisode d''aujourd''hui ?'),
  (2, 1, 'tu préfères', 'Tu préfères ne plus jamais manger de fromage, ou ne plus jamais faire la grasse matinée ?'),
  (3, 1, 'absurde', 'Quel animal serais-je, et lequel serais-tu ? Défends ton choix comme devant un jury.'),
  (4, 1, 'quotidien', 'Quel est l''achat le plus inutile de ta vie, que tu ne regrettes absolument pas ?'),
  (5, 1, 'absurde', 'On échange nos vies pendant vingt-quatre heures : que fais-tu en premier avec la mienne ?'),
  (6, 1, 'enfance', 'Quelle bêtise d''enfance n''as-tu jamais avouée à tes parents ? Il y a prescription.'),
  (7, 1, 'tu préfères', 'Tu préfères un dîner aux chandelles où l''on n''a pas le droit de parler, ou un fast-food où l''on n''a pas le droit de se taire ?'),
  (8, 1, 'quotidien', 'Quelle chanson chantes-tu sous la douche quand personne n''écoute ? Vraiment personne.'),
  (9, 1, 'absurde', 'Si on ouvrait un restaurant, quel serait son nom… et le plat qu''on raterait à chaque fois ?'),
  (10, 1, 'souvenirs', 'Quel est ton plus grand moment de solitude en public ?'),
  (11, 1, 'goûts', 'Quelle opinion culinaire défendrais-tu seul contre tous, jusqu''au bout ?'),
  (12, 1, 'absurde', 'Quel serait ton nom de scène si tu devenais une star de la chanson française ?'),
  (13, 1, 'tu préfères', 'Tu préfères voler, mais à un mètre du sol, ou être invisible, mais seulement quand personne ne te regarde ?'),
  (14, 1, 'quotidien', 'Quelle expression dis-tu tout le temps sans t''en rendre compte ? Si tu ne sais pas, je te le dirai.'),
  (15, 1, 'enfance', 'Quel poster était accroché au-dessus de ton lit à quatorze ans ?'),
  (16, 1, 'absurde', 'Dans un film catastrophe, lequel de nous deux disparaîtrait en premier, et par sa propre faute ?'),
  (17, 1, 'goûts', 'Quel est ton programme télé honteux, celui que tu ne cites jamais en soirée ?'),
  (18, 1, 'tu préfères', 'Tu préfères une semaine de camping sous la pluie avec moi, ou une semaine dans un palace avec ma famille ?'),
  (19, 1, 'quotidien', 'Quelle est ta technique secrète pour te rendormir à trois heures du matin ?'),
  (20, 1, 'absurde', 'Tu peux supprimer une seule tâche ménagère de l''univers, pour toujours : laquelle ?'),
  (21, 1, 'souvenirs', 'Quelle est la pire coupe de cheveux de ta vie, et qui en est responsable ?'),
  (22, 1, 'nous', 'Donne-moi un surnom ridicule, juste pour aujourd''hui. Je m''engage à y répondre.'),
  (23, 1, 'absurde', 'Notre couple en trois emojis : lesquels, et dans quel ordre ?'),
  (24, 1, 'goûts', 'Quel est le pire cadeau qu''on t''ait fait, et comment as-tu fait semblant d''être ravi ?'),
  (25, 1, 'quotidien', 'Combien d''onglets ouverts sur ton téléphone, là, maintenant ? Pas de triche.'),
  (26, 1, 'absurde', 'Quel jeu télé pourrions-nous gagner ensemble… et lequel nous ferait nous fâcher en direct ?'),
  (27, 1, 'enfance', 'Quelle réplique de film répétais-tu en boucle dans la cour de récré ?'),
  (28, 1, 'absurde', 'Un génie t''accorde un vœu, à condition qu''il tienne dans notre appartement. Lequel ?'),
  (29, 1, 'tu préfères', 'Tu préfères connaître la fin de tous les films, ou le contenu de tous tes cadeaux ?'),
  (30, 1, 'absurde', 'Si notre histoire était adaptée au cinéma, quel acteur jouerait mon rôle ? Sans méchanceté.'),
  (31, 2, 'souvenirs', 'Qu''as-tu pensé de moi, vraiment, au tout premier regard ?'),
  (32, 2, 'enfance', 'Où passais-tu tes étés à dix ans, et qu''est-ce qui sentait bon là-bas ?'),
  (33, 2, 'souvenirs', 'À quel moment précis t''es-tu dit « ah, ça devient sérieux » ?'),
  (34, 2, 'goûts', 'Quel livre, quel film ou quelle chanson a changé quelque chose en toi ?'),
  (35, 2, 'enfance', 'Qui était ton héros ou ton héroïne quand tu étais enfant, et pourquoi ?'),
  (36, 2, 'souvenirs', 'Raconte une victoire dont tu es fier ou fière, et que personne n''a vue.'),
  (37, 1, 'tu préfères', 'Tu préfères qu''on parte demain sans valise, ou dans six mois avec un planning à la minute ?'),
  (38, 2, 'rêves', 'Quelle vie parallèle t''arrive-t-il d''imaginer, dans le métro ou avant de t''endormir ?'),
  (39, 2, 'enfance', 'Quelle règle de ta famille trouvais-tu injuste, et l''appliquerais-tu aujourd''hui ?'),
  (40, 2, 'souvenirs', 'Quel message de moi as-tu gardé, ou relu plus d''une fois ?'),
  (41, 2, 'goûts', 'Quel lieu de Paris raconte le mieux qui tu es ? Emmène-moi en pensée.'),
  (42, 2, 'enfance', 'Quel souvenir d''école te fait encore rougir ?'),
  (43, 1, 'absurde', 'Quelle compétence absurde mettrais-tu en premier sur ton CV ?'),
  (44, 2, 'souvenirs', 'Quelle rencontre, avant moi, a changé ta trajectoire ?'),
  (45, 2, 'valeurs', 'Sur quoi as-tu complètement changé d''avis en dix ans ?'),
  (46, 2, 'rêves', 'Si tu avais un an et l''argent qu''il faut, quel projet lancerais-tu ?'),
  (47, 2, 'souvenirs', 'Quel voyage t''a appris quelque chose sur toi ?'),
  (48, 2, 'enfance', 'Comment se passaient les dîners de famille chez toi : qui parlait, qui se taisait ?'),
  (49, 1, 'tu préfères', 'Tu préfères lire dans mes pensées pendant une journée, ou que je lise dans les tiennes ?'),
  (50, 2, 'goûts', 'Quelle musique te ramène direct à une soirée précise de tes vingt ans ?'),
  (51, 2, 'souvenirs', 'Quelle a été la plus belle surprise de ta vie, avant moi ?'),
  (52, 2, 'valeurs', 'Qu''est-ce qui te met en colère plus que de raison, et sais-tu pourquoi ?'),
  (53, 2, 'enfance', 'Quel objet de ton enfance aimerais-tu retrouver dans un grenier ?'),
  (54, 2, 'rêves', 'Qu''est-ce que la personne que tu étais à quinze ans trouverait génial dans ta vie d''aujourd''hui ?'),
  (55, 2, 'souvenirs', 'Quel jour de notre histoire aimerais-tu revoir en film, coulisses comprises ?'),
  (56, 2, 'valeurs', 'Quelle personne admires-tu en silence, sans le lui avoir jamais dit ?'),
  (57, 2, 'goûts', 'Quel repas te console à coup sûr, et qui te le préparait ?'),
  (58, 2, 'rêves', 'Quel pays, quelle ville ou quelle époque t''attire sans que tu saches dire pourquoi ?'),
  (59, 2, 'enfance', 'Quel compliment reçu enfant t''accompagne encore aujourd''hui ?'),
  (60, 3, 'nous', 'Qu''est-ce que je fais qui te dit « je t''aime » mieux que les mots ?'),
  (61, 3, 'nous', 'Quand te sens-tu le plus proche de moi : en riant, en parlant, en silence, ou ailleurs ?'),
  (62, 3, 'nous', 'Quelle habitude avons-nous prise sans jamais la décider, et que tu adores ?'),
  (63, 1, 'absurde', 'Si on formait un duo de super-héros, quels seraient nos pouvoirs… et notre point faible commun ?'),
  (64, 3, 'nous', 'De quoi aimerais-tu qu''on parle plus souvent, tous les deux ?'),
  (65, 3, 'nous', 'Quel est ton moment préféré de nos semaines ordinaires ?'),
  (66, 3, 'rêves', 'Qu''aimerais-tu qu''on ait vécu ensemble d''ici cinq ans ?'),
  (67, 3, 'nous', 'Qu''est-ce que je comprends de toi sans que tu aies besoin de parler ?'),
  (68, 3, 'nous', 'Et qu''est-ce que je ne comprends toujours pas de toi ? Explique-moi.'),
  (69, 2, 'souvenirs', 'Quel petit moment de nous, sans importance pour personne d''autre, te revient souvent ?'),
  (70, 3, 'nous', 'Quand on n''est pas d''accord, qu''est-ce qui t''aide à revenir vers moi ?'),
  (71, 3, 'nous', 'Quelle qualité t''ai-je donné envie de cultiver ?'),
  (72, 3, 'rêves', 'Quelle aventure ferais-tu avec moi, et avec personne d''autre ?'),
  (73, 3, 'nous', 'Qu''est-ce qui te manque de nos débuts, et qu''on pourrait faire revenir ?'),
  (74, 1, 'tu préfères', 'Tu préfères qu''on vieillisse dans une grande ville bruyante, ou dans un village où tout le monde connaît notre vie ?'),
  (75, 3, 'nous', 'Quel est le plus beau compliment que je t''aie fait ? T''en souviens-tu mot pour mot ?'),
  (76, 3, 'valeurs', 'Prendre soin de l''autre, concrètement, pour toi, ça ressemble à quoi ?'),
  (77, 3, 'nous', 'Quelle tradition de ta famille aimerais-tu qu''on garde, et laquelle laisserais-tu volontiers derrière nous ?'),
  (78, 3, 'nous', 'Si tu écrivais la règle numéro un de notre couple, ce serait laquelle ?'),
  (79, 3, 'désir', 'Quel moment de tendresse imprévu t''a fait de l''effet, ces derniers temps ?'),
  (80, 3, 'nous', 'Dans quelles situations es-tu fier ou fière de nous ?'),
  (81, 2, 'goûts', 'Quelle chanson mettrais-tu sur la bande-son de notre année ?'),
  (82, 3, 'nous', 'Qu''aimerais-tu que je remarque plus souvent ?'),
  (83, 3, 'rêves', 'Quel rêve as-tu mis de côté, que je pourrais t''aider à reprendre ?'),
  (84, 3, 'désir', 'Qu''est-ce qui, chez moi, te séduit encore comme au premier jour ?'),
  (85, 3, 'nous', 'Comment préfères-tu qu''on se réconcilie après une dispute ?'),
  (86, 3, 'nous', 'Quelle est la chose la plus courageuse que tu aies faite pour nous ?'),
  (87, 1, 'absurde', 'On doit quitter Paris dans l''heure avec un seul sac pour deux : qu''est-ce que tu y mets ?'),
  (88, 3, 'valeurs', 'Tu préfères qu''on se dise tout, tout le temps, ou qu''on garde chacun un jardin secret ? Pourquoi ?'),
  (89, 3, 'désir', 'Quelle envie pour nous deux n''as-tu encore jamais formulée ?'),
  (90, 4, 'nous', 'Qu''est-ce qui est difficile à me dire, et que tu pourrais me confier aujourd''hui ?'),
  (91, 4, 'nous', 'De quoi as-tu le plus besoin de ma part en ce moment ?'),
  (92, 4, 'valeurs', 'Quelle blessure ancienne aimerais-tu que je comprenne mieux ?'),
  (93, 4, 'valeurs', 'Quel moment de ta vie a fait de toi la personne que tu es ?'),
  (94, 2, 'souvenirs', 'Raconte-moi la journée où tu as été le plus heureux ou la plus heureuse, avec ou sans moi.'),
  (95, 4, 'valeurs', 'Quelle peur gardes-tu pour toi, pour ne pas m''inquiéter ?'),
  (96, 4, 'nous', 'En quoi as-tu changé depuis que nous sommes ensemble, en mieux comme en moins bien ?'),
  (97, 4, 'nous', 'Qu''est-ce que tu n''as jamais osé me demander ?'),
  (98, 4, 'nous', 'T''es-tu déjà senti seul ou seule dans notre couple ? Qu''aurais-tu aimé que je fasse ?'),
  (99, 4, 'valeurs', 'S''il ne nous restait qu''une année, que changerais-tu dans notre vie ?'),
  (100, 4, 'nous', 'Quelle part de toi as-tu encore du mal à me montrer ?'),
  (101, 4, 'nous', 'Que voudrais-tu qu''on dise de nous dans trente ans ?'),
  (102, 4, 'valeurs', 'Quel pardon attends-tu encore, de quelqu''un ou de toi-même ?'),
  (103, 4, 'nous', 'Qu''aimes-tu en moi, que moi je n''aime pas ?'),
  (104, 4, 'nous', 'Quelle promesse aimerais-tu qu''on se fasse aujourd''hui ?'),
  (105, 4, 'valeurs', 'Qu''est-ce que l''amour t''a appris, que tu n''aurais appris nulle part ailleurs ?'),
  (106, 4, 'valeurs', 'L''amour, pour toi, en une seule phrase ?'),
  (107, 4, 'souvenirs', 'Quel est ton plus beau souvenir avec moi, et que ressens-tu en y repensant ?'),
  (108, 4, 'nous', 'Que me dirais-tu si tu savais que je vais t''écouter jusqu''au bout, sans rien répondre ?');

-- The answers, one per person and per day, final once given. Each reads the other's of a day once their own is given.
create table public.reponses_du_jour (
  duo_id uuid not null references public.duos(id) on delete cascade,
  day date not null,
  author uuid not null default auth.uid() references auth.users(id) on delete cascade,
  question_id integer not null references public.questions_du_jour(id),
  texte text not null check (length(trim(texte)) between 1 and 1000),
  answered_at timestamptz not null default now(),
  primary key (duo_id, day, author)
);
alter table public.reponses_du_jour enable row level security;

create function public.answered_on(d date) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.reponses_du_jour where duo_id = public.my_duo() and day = d and author = auth.uid())
$$;
revoke all on function public.answered_on(date) from public, anon;
grant execute on function public.answered_on(date) to authenticated;

create policy "read our answers" on public.reponses_du_jour
  for select using (duo_id = public.my_duo() and (author = auth.uid() or public.answered_on(day)));

-- The day's question of the account's duo: the next of the journey, after as many as the days one of them answered
-- (both see the same, and it waits for them); once all met, the journey starts again.
create function public.question_du_jour(d date default public.paris_today()) returns public.questions_du_jour
language sql stable security definer set search_path = public as $$
  select q.* from public.questions_du_jour q
  order by q.id
  offset mod(
    (select count(distinct day) from public.reponses_du_jour where duo_id = public.my_duo() and day < d)::int,
    (select count(*) from public.questions_du_jour)::int)
  limit 1
$$;
revoke all on function public.question_du_jour(date) from public, anon;
grant execute on function public.question_du_jour(date) to authenticated;

-- The day's question for the account's duo: the question, its own answer, and the other's once its own is given
-- (before, only whether it was given).
create function public.mon_jour(d date default public.paris_today()) returns json
language sql stable security definer set search_path = public as $$
  with q as (select * from public.question_du_jour(d)),
  mine as (select texte from public.reponses_du_jour where duo_id = public.my_duo() and day = d and author = auth.uid()),
  theirs as (select texte from public.reponses_du_jour where duo_id = public.my_duo() and day = d and author <> auth.uid())
  select json_build_object(
    'day', d,
    'question', (select json_build_object('id', id, 'texte', texte, 'theme', theme, 'profondeur', profondeur) from q),
    'mienne', (select texte from mine),
    'sienne_donnee', exists (select 1 from theirs),
    'sienne', case when exists (select 1 from mine) then (select texte from theirs) end
  )
$$;
revoke all on function public.mon_jour(date) from public, anon;
grant execute on function public.mon_jour(date) to authenticated;

-- The account answers today's question, once: its duo must be complete.
create function public.repondre_du_jour(texte text) returns void
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
  if length(trim(coalesce(texte, ''))) = 0 then
    raise exception 'Écrivez votre réponse avant de la sceller.';
  end if;
  if public.answered_on(today) then
    raise exception 'Votre réponse est déjà scellée.';
  end if;
  insert into public.reponses_du_jour (duo_id, day, author, question_id, texte)
  values (public.my_duo(), today, auth.uid(), (select id from public.question_du_jour(today)), left(trim(texte), 1000));
end $$;
revoke all on function public.repondre_du_jour(text) from public, anon;
grant execute on function public.repondre_du_jour(text) to authenticated;

-- What feeds the complicity gauge (app/src/lib/complicity.ts makes points of it): the evenings for two the account
-- lived, the pages of their Livre sealed by its duo (or by the account alone, without one), the days both answered.
-- The quizzes and défis come with phase 2.
create function public.complicite() returns json
language sql stable security definer set search_path = public as $$
  with two as (
    select user_id from public.duo_members where duo_id = public.my_duo()
    union select auth.uid()
  ), lived as (
    select s.id from public.soirees_choisies s
    where s.formule = 'duo' and s.day < public.paris_today()
      and (s.user_id = auth.uid() or exists (select 1 from public.soiree_invites i where i.soiree_id = s.id and i.user_id = auth.uid()))
  )
  select json_build_object(
    'duo', public.my_duo() is not null,
    'complet', public.duo_complete(),
    'soirees', (select count(*) from lived),
    'pages', (select count(*) from public.souvenirs p where p.soiree_id in (select id from lived) and p.author in (select user_id from two)),
    'reponses', (select count(*) from (
      select day from public.reponses_du_jour where duo_id = public.my_duo() group by day having count(*) = 2
    ) paired)
  )
$$;
revoke all on function public.complicite() from public, anon;
grant execute on function public.complicite() to authenticated;
