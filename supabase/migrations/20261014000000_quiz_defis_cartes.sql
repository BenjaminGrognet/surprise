-- Quiz, défis et cartes du soir (docs/complicite.md, phase 2). Each week, a quiz of eight questions: each one answers
-- for themselves and guesses the other's answer, both read once both answered. Each week, a défi for two, done when
-- both ticked it. On the day, a card for each step: a question or a little défi for two, a gage for a band. All of it
-- written for the app, and the gauge fed by it.

-- The quiz: eight series in the order of the journey (from the daily traps to the dreams), a duo's weeks one after
-- the other; eight questions each with four answers.
create table public.quiz_series (
  id smallint primary key,
  titre text not null,
  accroche text not null
);
create table public.quiz_questions (
  id integer primary key,
  serie smallint not null references public.quiz_series(id),
  rang smallint not null check (rang between 1 and 8),
  question text not null,
  choix text[] not null check (array_length(choix, 1) = 4),
  unique (serie, rang)
);
alter table public.quiz_series enable row level security;
alter table public.quiz_questions enable row level security;
create policy "the quiz is for every account" on public.quiz_series for select to authenticated using (true);
create policy "the quiz questions are for every account" on public.quiz_questions for select to authenticated using (true);

insert into public.quiz_series (id, titre, accroche) values
  (1, 'Petites manies', 'Les pièges du quotidien : vous croyez tout savoir de l''autre ?'),
  (2, 'Et si…', 'Des scénarios absurdes, des réponses révélatrices'),
  (3, 'Goûts et dégoûts', 'Ce qui nous régale… et ce que l''on ne mangera jamais'),
  (4, 'Notre mémoire', 'Ce que nous avons vécu : qui en garde le meilleur souvenir ?'),
  (5, 'L''enfant que j''étais', 'Cours de récré, goûters et bêtises : l''autre vous connaît-il d''avant ?'),
  (6, 'Par gros temps', 'Stress, disputes, réconciliations : comment chacun traverse les orages'),
  (7, 'Le langage du cœur', 'Ce qui fait du bien, à l''un et à l''autre'),
  (8, 'Nos rêves', 'Ce dont nous rêvons, à voix haute ou en secret');

insert into public.quiz_questions (id, serie, rang, question, choix) values
  (1, 1, 1, 'Ma position pour m''endormir', array['En étoile de mer', 'En chien de fusil', 'Sur le dos, comme un pharaon', 'Ça change toutes les nuits']),
  (2, 1, 2, 'Ce que je fais en premier en rentrant', array['Les chaussures valsent', 'Direction le frigo', 'Le canapé m''aspire', 'Je raconte ma journée sans respirer']),
  (3, 1, 3, 'Mon rapport au réveil', array['Debout à la première sonnerie', 'Trois rappels, minimum', 'Réveillé avant tout le monde', 'Quel réveil ?']),
  (4, 1, 4, 'Devant un film, le soir', array['Je commente tout', 'Je regarde mon téléphone en même temps', 'Je m''endors avant la fin', 'Je devine la fin, et je le dis']),
  (5, 1, 5, 'L''état de mon sac', array['Chaque chose a sa poche', 'Je retrouve tout… en vidant tout', 'Un ticket de 2019 y vit encore', 'Pas de sac : des poches']),
  (6, 1, 6, 'Au supermarché sans liste', array['Tout, sauf l''essentiel', 'Exactement ce qu''il faut', 'Le rayon biscuits gagne', 'Jamais sans liste']),
  (7, 1, 7, 'Face à une araignée', array['Je l''évacue délicatement', 'Je crie, puis j''appelle à l''aide', 'Je fais comme si je ne l''avais pas vue', 'Je lui donne un prénom']),
  (8, 1, 8, 'Mon message quand je suis en retard', array['« J''arrive ! » (pas encore parti)', 'Un vocal d''excuses de deux minutes', 'Un emoji qui court', 'Rien : j''arrive en courant']),
  (9, 2, 1, 'Une invasion de zombies à Paris : mon rôle', array['Celui qui a un plan', 'Celui qui a stocké des pâtes', 'Mordu le premier, par curiosité', 'Celui qui négocie avec eux']),
  (10, 2, 2, 'Je gagne un an gratuit de', array['Restaurants', 'Billets de train', 'Massages', 'Livres et places de cinéma']),
  (11, 2, 3, 'On me propose une nuit seul au Louvre', array['Oui, avec une lampe torche', 'Seulement avec toi', 'Jamais de la vie', 'Seulement si je peux toucher la Joconde']),
  (12, 2, 4, 'Invisible pour une journée', array['J''espionne mes collègues', 'Je vole un croissant (et je le paie après)', 'Je fais des blagues à mes amis', 'Je m''ennuie un peu, en fait']),
  (13, 2, 5, 'Un seul plat pour toute la vie', array['Les pâtes', 'La pizza', 'Un plat de mon enfance', 'Les sushis']),
  (14, 2, 6, 'Sur une île déserte, j''emporte', array['Un couteau suisse', 'Un livre', 'Une enceinte', 'Toi, ça compte ?']),
  (15, 2, 7, 'Si j''étais célèbre, ce serait pour', array['Un livre', 'Une chanson', 'Une recette', 'Un scandale bien mérité']),
  (16, 2, 8, 'Si je pouvais parler à une espèce animale', array['Les chats, enfin', 'Les oiseaux, pour les potins', 'Les dauphins', 'Les pigeons de Paris, pour comprendre']),
  (17, 3, 1, 'Le plat que je refuse poliment', array['Les abats', 'Les fruits de mer', 'La coriandre', 'Le fromage qui sent fort']),
  (18, 3, 2, 'Ma boisson d''un soir réussi', array['Une coupe de champagne', 'Un cocktail inventif', 'Un verre de rouge', 'Une bière bien fraîche']),
  (19, 3, 3, 'Le dessert, au restaurant', array['Toujours : c''est le but du repas', 'Seulement à partager', 'Jamais : je pique dans le tien', 'Café gourmand, le compromis']),
  (20, 3, 4, 'Ma musique pour cuisiner', array['Variété française à fond', 'Jazz ou soul', 'Un podcast', 'Le silence : je me concentre']),
  (21, 3, 5, 'Le genre de film que je ne supporte pas', array['L''horreur', 'Les comédies romantiques', 'Les super-héros', 'Les films d''auteur très lents']),
  (22, 3, 6, 'Mon petit-déjeuner du dimanche', array['Viennoiseries chaudes', 'Brunch salé, œufs à gogo', 'Rien : la grasse matinée d''abord', 'Pancakes maison']),
  (23, 3, 7, 'L''odeur que je préfère', array['Le pain chaud', 'L''herbe coupée', 'La pluie sur le bitume', 'Le café du matin']),
  (24, 3, 8, 'En vacances, premier achat', array['Les produits du marché', 'Des chips', 'Le vin de la région', 'La crème solaire, soyons sérieux']),
  (25, 4, 1, 'Ce qui m''a fait craquer au tout début', array['Le regard', 'L''humour', 'La voix', 'Une phrase précise']),
  (26, 4, 2, 'Notre premier rendez-vous, avec le recul', array['Parfait', 'Un peu gênant, mais mignon', 'Raté, et pourtant', 'Je ne savais pas que c''en était un']),
  (27, 4, 3, 'Qui a fait le premier pas ?', array['Moi, évidemment', 'Toi, évidemment', 'Personne : c''est arrivé tout seul', 'Nos amis s''en sont chargés']),
  (28, 4, 4, 'Le souvenir de nos débuts qui revient le plus', array['Un fou rire', 'Un baiser', 'Une conversation jusqu''à l''aube', 'Un message inattendu']),
  (29, 4, 5, 'Notre voyage le plus marquant', array['Le plus lointain', 'Le plus improvisé', 'Celui où tout est allé de travers', 'Le prochain, forcément']),
  (30, 4, 6, 'Notre dispute la plus absurde portait sur', array['Un itinéraire', 'La vaisselle ou le rangement', 'Un film ou une série', 'Personne ne s''en souvient']),
  (31, 4, 7, 'La chanson qui me fait penser à nous', array['Une chanson de nos débuts', 'Un tube de soirée', 'Une chanson qu''on chante faux ensemble', 'Il nous en faut une !']),
  (32, 4, 8, 'Notre plus belle soirée à deux, jusqu''ici', array['Un dîner', 'Un concert ou un spectacle', 'Une balade de nuit', 'Une soirée à la maison']),
  (33, 5, 1, 'À l''école, j''étais plutôt', array['Au premier rang, toujours', 'Le clown de la classe', 'Dans la lune, près de la fenêtre', 'Discrètement rebelle']),
  (34, 5, 2, 'Mon dessin animé culte', array['Un classique Disney', 'Un animé japonais', 'Celui du mercredi matin', 'Je regardais ceux des grands']),
  (35, 5, 3, 'Enfant, je voulais devenir', array['Un métier héroïque', 'Un artiste', 'Le patron de quelque chose', 'Un animal, à un moment']),
  (36, 5, 4, 'Ma plus grande peur d''enfant', array['Le noir', 'Le monstre sous le lit', 'Me perdre', 'Les piqûres']),
  (37, 5, 5, 'Le goûter de mon enfance', array['Pain et barre de chocolat', 'Un gâteau industriel culte', 'Des fruits, sous la contrainte', 'La tartine de confiture de mamie']),
  (38, 5, 6, 'Ma bêtise la plus mémorable', array['Une coupe de cheveux maison', 'Une fugue de vingt minutes', 'Un objet cassé, puis caché', 'Un mensonge énorme']),
  (39, 5, 7, 'Les vacances en famille', array['Camping et glacière', 'Chez les grands-parents', 'Toujours la même maison', 'Des road trips à rallonge']),
  (40, 5, 8, 'Mon doudou', array['Je l''ai encore', 'Perdu, je le pleure encore', 'Je n''en avais pas', 'Je préfère ne pas en parler']),
  (41, 6, 1, 'Sous le stress', array['Je parle beaucoup', 'Je me ferme', 'Je range tout frénétiquement', 'Je vais marcher ou courir']),
  (42, 6, 2, 'Après une dispute, j''ai besoin', array['D''en reparler tout de suite', 'D''un moment seul d''abord', 'D''un câlin, sans un mot', 'D''une blague pour détendre']),
  (43, 6, 3, 'Après une mauvaise journée, ce qui m''apaise', array['Qu''on m''écoute raconter', 'Qu''on me change les idées', 'Un bon repas', 'Le calme absolu']),
  (44, 6, 4, 'Face à une grosse décision', array['Une liste pour et contre', 'Mon instinct', 'L''avis de tout le monde', 'Je repousse jusqu''au dernier moment']),
  (45, 6, 5, 'Ma façon de dire pardon', array['Je le dis franchement', 'Par une attention', 'Je fais comme si de rien n''était', 'Avec humour']),
  (46, 6, 6, 'Quand je suis malade', array['Je veux qu''on s''occupe de moi', 'Je veux qu''on me laisse tranquille', 'Je fais comme si de rien n''était', 'J''annonce qu''il me reste trois heures à vivre']),
  (47, 6, 7, 'Ce qui me fait sortir de mes gonds', array['Qu''on ne m''écoute pas', 'Les retards', 'L''injustice', 'Qu''on me dise de me calmer']),
  (48, 6, 8, 'Dans une dispute, mon défaut', array['Je hausse le ton', 'Je boude', 'Je ressors de vieilles histoires', 'Je veux le dernier mot']),
  (49, 7, 1, 'Ce qui me touche le plus', array['Un compliment sincère', 'Un service rendu sans demander', 'Du temps rien qu''à nous', 'Un geste tendre']),
  (50, 7, 2, 'Le cadeau qui me touche', array['Un objet choisi avec soin', 'Une expérience à vivre ensemble', 'Un mot écrit à la main', 'Une surprise sans occasion']),
  (51, 7, 3, 'La preuve d''amour qui compte le plus pour moi', array['Qu''on me dise les choses', 'Qu''on me prenne dans les bras', 'Qu''on pense aux détails', 'Qu''on rie ensemble']),
  (52, 7, 4, 'Le geste du quotidien que je préfère', array['Le café apporté', 'Le baiser en partant', 'Le message de midi', 'La main dans la rue']),
  (53, 7, 5, 'La déclaration idéale', array['Écrite, pour la relire', 'Murmurée au bon moment', 'Criée sur les toits', 'Montrée, jamais dite']),
  (54, 7, 6, 'Mon moment de tendresse préféré', array['Le matin, avant de se lever', 'Le soir, sur le canapé', 'Dans la rue, par surprise', 'Les retrouvailles après une absence']),
  (55, 7, 7, 'Une soirée réussie, c''est d''abord', array['Bien manger', 'Rire', 'Découvrir quelque chose', 'Se retrouver']),
  (56, 7, 8, 'Ce que je préfère chez l''autre', array['Son humour', 'Sa douceur', 'Son énergie', 'Sa curiosité']),
  (57, 8, 1, 'Le voyage rêvé', array['Un road trip sans itinéraire', 'Une île au bout du monde', 'Une grande ville inconnue', 'Un refuge en montagne']),
  (58, 8, 2, 'Si l''on changeait de vie demain', array['Ouvrir un lieu à nous', 'Vivre à l''étranger', 'S''installer à la campagne', 'Faire le tour du monde']),
  (59, 8, 3, 'La maison de nos rêves', array['Un appartement haussmannien', 'Une maison face à la mer', 'Un loft en ville', 'Une ferme rénovée']),
  (60, 8, 4, 'Le talent que j''aimerais acquérir', array['Jouer d''un instrument', 'Parler une autre langue', 'Cuisiner comme un chef', 'Danser vraiment bien']),
  (61, 8, 5, 'Une année sabbatique serait faite pour', array['Voyager', 'Apprendre', 'Se reposer enfin', 'Créer quelque chose']),
  (62, 8, 6, 'Dans dix ans, je nous vois', array['Au même endroit, en mieux', 'Dans une autre ville', 'Dans un autre pays', 'Allez savoir, et c''est très bien']),
  (63, 8, 7, 'Le projet fou que je n''ose pas dire', array['Changer de métier', 'Écrire un livre', 'Partir un an', 'Monter une affaire']),
  (64, 8, 8, 'Pour nos vieux jours, je rêve', array['D''une maison pleine de monde', 'D''un tour du monde en camping-car', 'D''un village au soleil', 'De rester à Paris, évidemment']);

-- The answers: for oneself (moi) and the guess of the other's (devine), 0 to 3, final once given.
create table public.quiz_reponses (
  duo_id uuid not null references public.duos(id) on delete cascade,
  semaine date not null, -- the week's Monday
  question_id integer not null references public.quiz_questions(id),
  author uuid not null default auth.uid() references auth.users(id) on delete cascade,
  moi smallint not null check (moi between 0 and 3),
  devine smallint not null check (devine between 0 and 3),
  answered_at timestamptz not null default now(),
  primary key (duo_id, semaine, question_id, author)
);
alter table public.quiz_reponses enable row level security;
-- Read through mon_quiz only, which shows the other's answers to a question once both answered it.
create policy "read my quiz answers" on public.quiz_reponses for select using (duo_id = public.my_duo() and author = auth.uid());

-- The week's series for the account's duo: the next of the journey, after as many as the weeks it played before;
-- once all played, the journey starts again.
create function public.quiz_de_la_semaine(d date default public.paris_today()) returns smallint
language sql stable security definer set search_path = public as $$
  select (mod(
    (select count(distinct semaine) from public.quiz_reponses where duo_id = public.my_duo() and semaine < date_trunc('week', d)::date)::int,
    (select count(*) from public.quiz_series)::int) + 1)::smallint
$$;
revoke all on function public.quiz_de_la_semaine(date) from public, anon;
grant execute on function public.quiz_de_la_semaine(date) to authenticated;

-- The month's quiz for the account's duo: its series, each question with the account's answer and guess, and the
-- other's once both answered it (before: only whether they did); the score, each one's right guesses.
create function public.mon_quiz(d date default public.paris_today()) returns json
language sql stable security definer set search_path = public as $$
  with week as (select date_trunc('week', d)::date as m, public.quiz_de_la_semaine(d) as s),
  answers as (
    select q.id, q.rang, q.question, q.choix,
      mine.moi, mine.devine, theirs.moi as sien_moi, theirs.devine as sien_devine
    from public.quiz_questions q
    cross join week
    left join public.quiz_reponses mine
      on mine.question_id = q.id and mine.duo_id = public.my_duo() and mine.semaine = week.m and mine.author = auth.uid()
    left join public.quiz_reponses theirs
      on theirs.question_id = q.id and theirs.duo_id = public.my_duo() and theirs.semaine = week.m and theirs.author <> auth.uid()
    where q.serie = week.s
  )
  select json_build_object(
    'semaine', (select m from week),
    'serie', (select json_build_object('id', id, 'titre', titre, 'accroche', accroche) from public.quiz_series where id = (select s from week)),
    'questions', (select json_agg(json_build_object(
      'id', id, 'rang', rang, 'question', question, 'choix', choix, 'moi', moi, 'devine', devine,
      'sienne_donnee', sien_moi is not null,
      'sien_moi', case when moi is not null then sien_moi end,
      'sien_devine', case when moi is not null then sien_devine end
    ) order by rang) from answers),
    'score', json_build_object(
      'moi', (select count(*) from answers where moi is not null and sien_moi is not null and devine = sien_moi),
      'sien', (select count(*) from answers where moi is not null and sien_moi is not null and sien_devine = moi)
    )
  )
$$;
revoke all on function public.mon_quiz(date) from public, anon;
grant execute on function public.mon_quiz(date) to authenticated;

create function public.repondre_quiz(question_id integer, pour_moi smallint, pour_l_autre smallint) returns void
language plpgsql security definer set search_path = public as $$
declare
  today date := public.paris_today();
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  if not public.duo_complete() then
    raise exception 'Formez d''abord votre duo : le quiz se joue à deux.';
  end if;
  if not exists (select 1 from public.quiz_questions q where q.id = repondre_quiz.question_id and q.serie = public.quiz_de_la_semaine(today)) then
    raise exception 'Cette question n''est pas celle de la semaine.';
  end if;
  if pour_moi is null or pour_l_autre is null or pour_moi not between 0 and 3 or pour_l_autre not between 0 and 3 then
    raise exception 'Choisissez une réponse pour vous, et une pour l''autre.';
  end if;
  insert into public.quiz_reponses (duo_id, semaine, question_id, author, moi, devine)
  values (public.my_duo(), date_trunc('week', today)::date, repondre_quiz.question_id, auth.uid(), pour_moi, pour_l_autre)
  on conflict do nothing;
  if not found then
    raise exception 'Votre réponse à cette question est déjà donnée.';
  end if;
end $$;
revoke all on function public.repondre_quiz(integer, smallint, smallint) from public, anon;
grant execute on function public.repondre_quiz(integer, smallint, smallint) to authenticated;

-- The défis: a gesture, a ritual, an outing (with the wish that opens the evening form on it), a game.
create table public.defis (
  id integer primary key,
  genre text not null check (genre in ('geste', 'rituel', 'sortie', 'jeu')),
  titre text not null,
  texte text not null,
  envie text -- a wish of the evening form (surprise.quiz.ENVIES), for an outing
);
alter table public.defis enable row level security;
create policy "the défis are for every account" on public.defis for select to authenticated using (true);

insert into public.defis (id, genre, titre, texte, envie) values
  (1, 'geste', 'Le mot caché', 'Glissez un petit mot dans une poche, un sac ou un livre de l''autre. Plus il est trouvé tard, mieux c''est.', null),
  (2, 'jeu', 'Le surnom de la semaine', 'Trouvez-vous chacun un surnom absurde, et tenez-le toute la semaine, même devant les autres.', null),
  (3, 'geste', 'La chanson sans un mot', 'Envoyez une chanson qui vous fait penser à l''autre, sans la moindre explication.', null),
  (4, 'rituel', 'Dix minutes sans écran', 'Chaque soir de la semaine, dix minutes rien qu''à deux, les téléphones exilés dans une autre pièce.', null),
  (5, 'jeu', 'Le portrait chinois', 'Si j''étais une ville, un plat, une chanson : répondez pour l''autre, puis comparez avec ses vraies réponses.', null),
  (6, 'geste', 'Le compliment précis', 'Un compliment sur un geste précis de la semaine de l''autre. « Tu es super » ne compte pas.', null),
  (7, 'sortie', 'Un quartier inconnu', 'Explorez un quartier de Paris où vous n''avez jamais mis les pieds, sans carte si possible.', 'air'),
  (8, 'jeu', 'Deux vérités, un mensonge', 'Chacun raconte trois anecdotes de sa vie, dont une inventée. L''autre doit démasquer l''intruse.', null),
  (9, 'geste', 'Le petit-déjeuner servi', 'Préparez le petit-déjeuner de l''autre, prêt avant son réveil.', null),
  (10, 'rituel', 'Le palmarès du dimanche', 'Dimanche soir, remettez-vous les prix de la semaine : fou rire d''or, gaffe d''argent, moment tendre de bronze.', null),
  (11, 'sortie', 'Une cuisine jamais goûtée', 'Un restaurant d''une cuisine que ni l''un ni l''autre n''a jamais goûtée.', 'gourmand'),
  (12, 'jeu', 'Le dîner à l''aveugle', 'L''un cuisine, l''autre goûte les yeux bandés et devine chaque ingrédient.', null),
  (13, 'geste', 'La corvée envolée', 'Faites, sans le dire, une tâche que l''autre déteste. Puis attendez que ce soit remarqué.', null),
  (14, 'jeu', 'Le samedi du oui', 'Un samedi, dites oui à toutes les propositions raisonnables de l''autre.', null),
  (15, 'rituel', 'Le plat de l''enfance', 'Cuisinez ensemble le plat préféré de l''enfance de l''un de vous, recette de famille si possible.', null),
  (16, 'sortie', 'Jouer en équipe', 'Une activité où il faut gagner ensemble : escape game, quiz, jeu de piste.', 'jouer'),
  (17, 'jeu', 'Le musée de nous', 'Choisissez chacun trois objets de la maison qui racontent votre histoire, et faites la visite guidée à l''autre.', null),
  (18, 'geste', 'La vieille photo', 'Retrouvez une photo de vous deux d''il y a longtemps, et envoyez-la avec un mot.', null),
  (19, 'rituel', 'La playlist commune', 'Composez à deux une playlist de dix chansons qui racontent votre histoire, dans l''ordre.', null),
  (20, 'sortie', 'Rire ensemble', 'Une soirée d''humour, pour rire à deux du même spectacle.', 'rire'),
  (21, 'jeu', 'Les rôles inversés', 'Le temps d''une soirée, chacun organise ce que l''autre aime faire.', null),
  (22, 'geste', 'Les trois mercis', 'Dites merci pour trois choses que l''autre fait sans que personne ne le remarque.', null),
  (23, 'sortie', 'Une expo en nocturne', 'Visitez une exposition à la nuit tombée.', 'curieux'),
  (24, 'jeu', 'L''interview', 'Interviewez l''autre comme une star pendant dix minutes, questions de journaliste à l''appui. Puis inversez.', null),
  (25, 'rituel', 'Le café de l''aube', 'Un matin, levez-vous dix minutes plus tôt pour un café rien qu''à deux.', null),
  (26, 'sortie', 'Danser, même mal', 'Dansez dans une guinguette, un bal ou un club, le temps d''une chanson au moins.', 'fete'),
  (27, 'jeu', 'Le top cinq', 'Dressez chacun le top cinq de vos moments à deux, puis comparez vos listes.', null),
  (28, 'sortie', 'Une musique jamais écoutée', 'Allez écouter en concert une musique que vous n''écoutez jamais.', 'musique'),
  (29, 'geste', 'La vraie lettre', 'Écrivez une lettre sur papier, et laissez-la là où l''autre la trouvera.', null),
  (30, 'sortie', 'Le premier rendez-vous, rejoué', 'Retournez sur les lieux de votre premier rendez-vous, ou réinventez-le de zéro.', 'romantique'),
  (31, 'jeu', 'Le jeu oublié', 'Ressortez un jeu de société du fond d''un placard, et jouez-y pour de vrai.', null),
  (32, 'rituel', 'La soirée souvenirs', 'Ressortez vos photos d''il y a cinq ans, et racontez-vous ce moment-là.', null),
  (33, 'geste', 'Le câlin de vingt secondes', 'Un câlin de vingt secondes chaque jour de la semaine. Comptez à voix basse.', null),
  (34, 'sortie', 'Le frisson', 'Une activité qui fait un peu peur à l''un de vous deux, l''autre en soutien.', 'frissons'),
  (35, 'jeu', 'Le grand tri', 'Videz ensemble un tiroir ou une étagère, et racontez-vous les trouvailles.', null),
  (36, 'rituel', 'Le carnet de projets', 'Notez ensemble trois choses à faire avant la fin de l''année, et fixez la date de la première.', null),
  (37, 'sortie', 'Un cours à deux', 'Réservez un atelier où apprendre quelque chose ensemble, de vos mains.', 'creer'),
  (38, 'jeu', 'La question interdite', 'Posez-vous chacun la question que vous n''avez jamais osé poser. Un seul joker chacun.', null),
  (39, 'sortie', 'Le soleil se lève', 'Levez-vous pour voir le soleil se lever sur Paris, depuis un point haut.', 'air'),
  (40, 'jeu', 'La lettre au futur', 'Écrivez-vous une lettre à ouvrir dans un an, jour pour jour.', null);

-- The week's défi for the account's duo: the next of the journey each week since the duo was formed (from its
-- Monday); once all met, the journey starts again.
create function public.defi_de_la_semaine(d date default public.paris_today()) returns public.defis
language sql stable security definer set search_path = public as $$
  with formed as (
    select coalesce((select (created_at at time zone 'Europe/Paris')::date from public.duos where id = public.my_duo()), d) as day
  )
  select * from public.defis order by id
  offset mod(greatest(0,
    ((d - (extract(isodow from d)::int - 1)) - ((select day from formed) - (extract(isodow from (select day from formed))::int - 1))) / 7
  ), (select count(*) from public.defis)::int)
  limit 1
$$;
revoke all on function public.defi_de_la_semaine(date) from public, anon;
grant execute on function public.defi_de_la_semaine(date) to authenticated;

-- Each one ticks the week's défi once done; it is done for the duo once both ticked it.
create table public.defis_faits (
  duo_id uuid not null references public.duos(id) on delete cascade,
  semaine date not null, -- the week's Monday
  defi_id integer not null references public.defis(id),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  done_at timestamptz not null default now(),
  primary key (duo_id, semaine, user_id)
);
alter table public.defis_faits enable row level security;
create policy "read our défis" on public.defis_faits for select using (duo_id = public.my_duo());

create function public.mon_defi(d date default public.paris_today()) returns json
language sql stable security definer set search_path = public as $$
  with week as (select (d - (extract(isodow from d)::int - 1))::date as monday),
  done as (select user_id from public.defis_faits, week where duo_id = public.my_duo() and semaine = week.monday)
  select json_build_object(
    'semaine', (select monday from week),
    'defi', (select json_build_object('id', id, 'genre', genre, 'titre', titre, 'texte', texte, 'envie', envie) from public.defi_de_la_semaine(d)),
    'fait_par_moi', exists (select 1 from done where user_id = auth.uid()),
    'fait_par_l_autre', exists (select 1 from done where user_id <> auth.uid()),
    'valides', (select count(*) from (
      select semaine from public.defis_faits where duo_id = public.my_duo() group by semaine having count(*) = 2
    ) both_done)
  )
$$;
revoke all on function public.mon_defi(date) from public, anon;
grant execute on function public.mon_defi(date) to authenticated;

create function public.defi_fait() returns void
language plpgsql security definer set search_path = public as $$
declare
  today date := public.paris_today();
begin
  if auth.uid() is null then
    raise exception 'Connectez-vous d''abord.';
  end if;
  if not public.duo_complete() then
    raise exception 'Formez d''abord votre duo : les défis se relèvent à deux.';
  end if;
  insert into public.defis_faits (duo_id, semaine, defi_id, user_id)
  values (public.my_duo(), (today - (extract(isodow from today)::int - 1))::date, (select id from public.defi_de_la_semaine(today)), auth.uid())
  on conflict do nothing;
end $$;
revoke all on function public.defi_fait() from public, anon;
grant execute on function public.defi_fait() to authenticated;

-- The cards of the evening: on each step revealed, a question or a little défi for two, a gage for a band. `role`:
-- the step's (repas, verre, sortie), or null for any step.
create table public.cartes_du_soir (
  id integer primary key,
  formule text not null check (formule in ('duo', 'squad')),
  genre text not null check (genre in ('conversation', 'defi', 'gage')),
  role text check (role in ('repas', 'verre', 'sortie')),
  profondeur smallint not null default 1 check (profondeur between 1 and 3), -- a duo's, deeper as it lives evenings
  texte text not null
);
alter table public.cartes_du_soir enable row level security;
-- Read on the evening's page, even by a guest who has no duo: every account.
create policy "the cards are for every account" on public.cartes_du_soir for select to authenticated using (true);

insert into public.cartes_du_soir (id, formule, genre, role, profondeur, texte) values
  (1, 'duo', 'conversation', null, 1, 'Si cette soirée était le début d''un film, quel en serait le titre ?'),
  (2, 'duo', 'conversation', 'repas', 1, 'Quel plat de la carte commanderais-tu pour moi, et pourquoi ?'),
  (3, 'duo', 'defi', 'repas', 1, 'Inventez à voix basse l''histoire du couple de la table voisine : premier rendez-vous, ou dixième anniversaire ?'),
  (4, 'duo', 'conversation', 'verre', 1, 'On trinque à quoi, ce soir ? Interdit de dire « à nous ».'),
  (5, 'duo', 'defi', 'verre', 1, 'Trinquez en vous regardant dans les yeux. Le premier qui rit choisit le prochain verre.'),
  (6, 'duo', 'defi', null, 1, 'Faites-vous un compliment dans une langue étrangère. Inventée, ça marche aussi.'),
  (7, 'duo', 'defi', 'sortie', 1, 'Une photo de vous deux façon vieille carte postale, pose comprise.'),
  (8, 'duo', 'defi', 'verre', 1, 'Pendant cinq minutes, ne parlez plus que par questions. Le premier qui répond normalement a perdu.'),
  (9, 'duo', 'defi', 'repas', 1, 'Choisissez le plat de l''autre, sans le consulter.'),
  (10, 'duo', 'conversation', 'sortie', 1, 'Notez cette étape sur dix, avec un argument de critique gastronomique, même si l''on n''y mange pas.'),
  (11, 'duo', 'conversation', null, 1, 'Quel détail de cette soirée raconteras-tu à tes amis demain ?'),
  (12, 'duo', 'defi', 'sortie', 1, 'Main dans la main jusqu''à l''étape suivante. Le premier qui lâche porte le manteau de l''autre.'),
  (13, 'duo', 'defi', 'repas', 1, 'Commandez quelque chose que vous n''avez jamais goûté.'),
  (14, 'duo', 'conversation', 'verre', 1, 'Quel serait notre mot de code pour fuir une soirée ennuyeuse ?'),
  (15, 'duo', 'conversation', null, 2, 'Quel moment de ta journée aurais-tu aimé partager avec moi ?'),
  (16, 'duo', 'conversation', 'repas', 2, 'Raconte-moi un souvenir d''enfance lié à un repas.'),
  (17, 'duo', 'conversation', 'verre', 2, 'Quelle est la plus belle chose qu''on ait faite ensemble cette année ?'),
  (18, 'duo', 'conversation', 'sortie', 2, 'Quelle sortie n''as-tu encore jamais osé me proposer ?'),
  (19, 'duo', 'conversation', null, 2, 'Quel voyage referais-tu demain, avec moi ?'),
  (20, 'duo', 'conversation', null, 2, 'Quelle chanson mettrais-tu sur ce moment précis ?'),
  (21, 'duo', 'defi', 'repas', 2, 'Faites un vœu en secret pour l''autre, et révélez-le au dessert.'),
  (22, 'duo', 'defi', 'sortie', 2, 'Volez un baiser au moment le plus inattendu de cette étape.'),
  (23, 'duo', 'conversation', 'verre', 2, 'Qu''est-ce qui te plaît chez moi, que je ne soupçonne pas ?'),
  (24, 'duo', 'defi', null, 2, 'Racontez votre rencontre comme à un inconnu : chacun sa version, et l''autre corrige.'),
  (25, 'duo', 'conversation', null, 3, 'Que voudrais-tu qu''on retienne de ce soir, dans dix ans ?'),
  (26, 'duo', 'conversation', 'verre', 3, 'Qu''est-ce que tu n''as jamais osé me dire, en bien ?'),
  (27, 'duo', 'conversation', 'repas', 3, 'Quel est le meilleur conseil qu''on t''ait donné, et l''as-tu suivi ?'),
  (28, 'duo', 'defi', 'sortie', 3, 'Avant l''étape suivante, dites-vous une chose que vous admirez chez l''autre, sans détourner le regard.'),
  (29, 'duo', 'conversation', null, 3, 'Qu''est-ce qui te fait te sentir chez toi, avec moi ?'),
  (30, 'duo', 'defi', 'verre', 3, 'Écrivez chacun un mot sur une serviette, pliez-la, et échangez-les à la fin de la soirée.'),
  (31, 'squad', 'gage', 'repas', 1, 'La dernière personne arrivée à table porte un toast improvisé.'),
  (32, 'squad', 'gage', 'verre', 1, 'Chacun raconte son pire premier rendez-vous ; la bande vote pour le plus gênant.'),
  (33, 'squad', 'gage', 'sortie', 1, 'Photo de groupe en pyramide humaine, ou ce qui s''en approche.'),
  (34, 'squad', 'gage', null, 1, 'Le premier qui sort son téléphone avant la fin de l''étape offre les cafés.'),
  (35, 'squad', 'gage', 'verre', 1, 'Imitez quelqu''un de la bande ; les autres devinent qui.'),
  (36, 'squad', 'gage', 'sortie', 1, 'La personne fêtée choisit la chanson du prochain trajet : tout le monde chante.'),
  (37, 'squad', 'gage', null, 1, 'Chacun fait un compliment à la personne à sa droite. Un vrai.'),
  (38, 'squad', 'gage', 'repas', 1, 'Racontez en trente secondes comment vous avez rencontré la personne fêtée.'),
  (39, 'squad', 'gage', 'sortie', 1, 'Trouvez un inconnu qui accepte de prendre la bande en photo, pose imposée par lui.'),
  (40, 'squad', 'gage', 'verre', 1, 'Interdit de dire « oui » ou « non » jusqu''à la fin de l''étape ; chaque faute, un gage choisi par la bande.'),
  (41, 'squad', 'gage', 'repas', 1, 'La plus jeune personne de la bande choisit le dessert de tout le monde.'),
  (42, 'squad', 'gage', 'verre', 1, 'Chacun révèle une chose que personne ici ne sait encore.'),
  (43, 'squad', 'gage', 'repas', 1, 'Accent étranger obligatoire pour passer commande.'),
  (44, 'squad', 'gage', 'sortie', 1, 'La bande invente un cri de ralliement, et le pousse à chaque étape.'),
  (45, 'squad', 'gage', null, 1, 'Mimez un film : les autres ont une minute pour deviner.'),
  (46, 'squad', 'gage', null, 1, 'Chacun partage un souvenir avec la personne fêtée, en une phrase.'),
  (47, 'squad', 'gage', 'verre', 1, 'Qui rit pendant le prochain toast chante un refrain choisi par la bande.'),
  (48, 'squad', 'gage', 'sortie', 1, 'Échangez un accessoire avec votre voisin le temps de l''étape.'),
  (49, 'squad', 'gage', 'repas', 1, 'Commande au doigt pointé : interdit de prononcer le nom du plat.'),
  (50, 'squad', 'gage', null, 1, '« Je n''ai jamais… » : trois tours, version avouable.'),
  (51, 'squad', 'gage', 'verre', 1, 'Toast collectif : chacun ajoute un mot, la phrase doit avoir un sens à la fin.'),
  (52, 'squad', 'gage', 'sortie', 1, 'Jusqu''à la prochaine étape, en file indienne, comme une équipe de cambrioleurs.'),
  (53, 'squad', 'gage', null, 1, 'Désignez le paparazzi de l''étape : à lui la photo la plus improbable de la soirée.');

-- The gauge, now with the quiz and the défis: each month's series both finished, the right guesses of both on the
-- questions both answered, the défis both ticked.
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
    ) both_done)
  )
$$;
