# Complicité, dates et routine : la conception

Les fonctionnalités retenues le 15 octobre 2026 : rapprocher le couple (A1 à A5), les dates et les occasions (B7 à B10),
sortir de la routine (C11, C14, C16). Ce document dit ce que voit le couple, où c'est rangé en base, et d'où vient le
contenu. Il est construit par phases (en fin de document), chacune avec ses tests aux trois couches.

## Le duo

Les questions, quiz, défis et la jauge appartiennent à deux personnes, pas à une soirée. Depuis la migration
`…_passager_per_evening`, il n'y a plus de table `couples` : les invités sont rangés soirée par soirée. Il faut donc
un lien entre deux comptes, **le duo**.

- `public.duos (id, code, created_at)` et `public.duo_members (user_id primary key, duo_id, email, joined_at)`. La clé
  primaire sur `user_id` garantit **un seul duo par compte** ; les fonctions qui l'écrivent en limitent le nombre à deux.
- **Formé tout seul** : quand un passager rejoint une soirée à deux (`soiree_invites`, formule `duo`) et qu'aucun des
  deux n'a encore de duo, ils en forment un. Si l'instigateur a un duo qui attend son second membre, le passager le
  rejoint.
- **Ou par un code**, depuis « Mon couple » : l'un ouvre le duo et envoie son code, l'autre l'entre (`join_duo`).
- **Quitter le duo** (`leave_duo`) le dissout : ses réponses, ses défis et son programme partent avec lui. Les soirées et
  le Livre restent, ils appartiennent aux soirées.
- Une soirée Secret Squad ne forme jamais de duo.

## L'écran « Mon couple »

Une page `/couple`, ouverte par la jauge de l'accueil et par « Mon compte ». De haut en bas :

1. **La jauge vivante** (A4), son palier, ce qu'il débloque, et le palier suivant.
2. **La question du jour** (A1).
3. **Le défi de la semaine** (A3).
4. **Le quiz de la semaine** (A2).
5. **Le programme « 4 semaines pour se retrouver »** (C11), une fois commencé.
6. **Les dates qui comptent** (B7).
7. **Le duo** : avec qui, le code pour inviter, quitter.

Sans duo, la page explique le principe et propose le code d'invitation ; la jauge compte alors les seules soirées et
pages du Livre du compte.

## A1. La question du jour

- Une question par jour, la même pour les deux, tirée de `public.questions_du_jour` (texte, thème, palier 1 à 4) :
  **un parcours, du plus léger au plus intime**. Palier 1 « Pour rire » (scénarios absurdes, « tu préfères… », pièges du
  quotidien), 2 « Se raconter » (souvenirs, enfance), 3 « Nous deux », 4 « À cœur ouvert ». Le duo les rencontre dans
  l'ordre (`question_du_jour(day)` : la suivante après autant de jours où l'un des deux a répondu) ; la question attend
  tant que personne n'y répond. Une question légère revient de temps en temps, pour respirer.
- **Scellée** comme le Livre : chacun répond (`public.reponses_du_jour`, une réponse par personne et par jour,
  définitive) et ne lit celle de l'autre qu'après avoir donné la sienne. Avant, il voit seulement « Sam a répondu ».
- Une paire de réponses fait monter la jauge. Les sept derniers jours restent lisibles, sous la question.

## A2. Le quiz « Vous connaissez-vous vraiment ? »

- Une série de 8 questions par semaine (`public.quiz_questions` : série, rang, question, 4 choix). Huit séries, dans
  l'ordre du parcours du duo (la suivante après chaque semaine jouée) : Petites manies, Et si… (scénarios absurdes), Goûts
  et dégoûts, Notre mémoire, L'enfant que j'étais, Par gros temps (stress et disputes), Le langage du cœur, Nos rêves.
- Pour chaque question, chacun donne **sa** réponse et **devine** celle de l'autre (`public.quiz_reponses`). Une question
  se dévoile quand les deux y ont répondu : qui a deviné juste.
- Le score de la semaine : les bonnes devinettes des deux, sur 16, et son verdict une fois la série finie (Télépathes, Âmes
  complices, Complices en rodage, Deux mystères ambulants). Une série finie à deux fait monter la jauge, chaque bonne
  devinette en plus.

## A3. Les défis de la semaine

- Un défi par semaine (semaine ISO), tiré de `public.defis` : un petit geste hors de l'app, un rituel, une sortie, un
  jeu. Dans l'ordre du parcours, des petits gestes aux plus audacieux, à partir de la semaine où le duo s'est formé.
  Les défis-sorties renvoient vers les activités de la base par une étiquette (« un cours à deux » → `atelier`).
- Chacun coche « fait » (`public.defis_faits`) ; le défi est **validé quand les deux l'ont coché**.
- Badges selon le nombre de défis validés : Premier pas (1), Un mois de complicité (4), Saison complice (12), Année
  complice (52).

## A4. La jauge vivante

`public.complicite()` compte, pour le compte connecté et son duo : les soirées à deux vécues, les pages du Livre scellées
de ces soirées, les paires de réponses du jour, les séries de quiz finies, les bonnes devinettes, les défis validés.
`app/src/lib/complicity.ts` en fait des points :

| Ce qui compte | Points |
|---|---|
| Une soirée à deux vécue | 10 |
| Une page du Livre scellée | 3 |
| Une paire de réponses du jour | 1 |
| Une série de quiz finie à deux | 3, et 1 par bonne devinette |
| Un défi validé par les deux | 4 |

Paliers et ce qu'ils débloquent :

| Palier | Points | Débloque |
|---|---|---|
| Premiers regards | 0 | |
| Étincelles | 15 | une **option secrète** de plus dans le formulaire de soirée |
| Étoiles filantes | 40 | **l'intrigue spéciale** : une soirée tout en audace, au titre à part |
| Constellation | 80 | **le thème « Minuit »** pour l'app |
| Âmes complices | 150 | |

## A5. Les cartes du soir

- Sur la feuille de route du jour J, chaque étape dévoilée porte **une carte** : une question de conversation ou un
  petit défi, selon le genre d'étape (`repas`, `verre`, `sortie`). Pour Secret Squad, des **gages** entre potes.
- `public.cartes_du_soir` (formule, genre, rôle de l'étape, texte). La carte est tirée de l'id de la soirée et du rang de
  l'étape : les deux voient la même. « Une autre carte » en tire la suivante.

## B7. Les dates qui comptent

- Dans « Mon couple », le duo note ses dates (`public.dates_cles` : intitulé, genre, jour et mois) : la rencontre, les
  anniversaires de chacun. La Saint-Valentin compte d'office pour un duo.
- **Trois semaines avant**, le serveur (`surprise.rappels`) compose trois intrigues pour ce jour, avec le profil du
  couple, et envoie un email et une notification : « Le 14 février approche : trois intrigues vous attendent. » Le lien
  ouvre ces trois intrigues dans le formulaire. L'anniversaire d'un des deux ne va qu'à l'autre.
- Chaque rappel n'est envoyé qu'une fois : `pipeline.rappels (user_id, cle, recipient)` (les courriers des soirées,
  `pipeline.courriers`, sont liés à une soirée ; ceux-ci non).

## B8. Les conseils de saison

- `public.saisons` : Fête de la musique (21 juin), Nuit Blanche (date de l'année, saisie chaque année), Halloween
  (31 octobre), Noël (du 1er au 24 décembre), Saint-Valentin. Pour chacune : une envie, un texte, un déroulé.
- Sur l'accueil, dans les trois semaines qui précèdent : une carte « En ce moment » qui ouvre le formulaire réglé sur la
  saison (envies et jour).
- Dix jours avant, un email aux comptes **sans soirée prévue** ce jour-là.

## B9. « Il y a un an… »

- Sur l'accueil, le jour anniversaire d'une soirée vécue (à trois jours près), sa photo du Livre revient, avec
  « On remet ça ? » qui ouvre le formulaire sur ses envies.
- Le jour même, un email (`pipeline.rappels`, clé `un-an:<soirée>`).

## B10. La météo, 48 h avant

- Pour une étape en plein air (étiquette `plein_air`, ou sur l'eau), le serveur lit la prévision d'Open-Meteo à l'heure
  de l'étape, 48 h avant la soirée. Pluie probable (60 % ou plus) : un email et une notification à l'instigateur,
  « Pluie annoncée à 21 h : un plan B couvert ? », qui ouvrent la soirée sur le bouton « Plan B » existant.
- Rien n'est changé sans l'instigateur : ses réservations sont les siennes.
- Open-Meteo est gratuit sans clé pour un usage **non commercial**. Si l'app devient payante, il faudra son offre
  commerciale ou une autre source.

## C11. Le programme « 4 semaines pour se retrouver »

- `public.programme` : quatre semaines, de plus en plus audacieuses. Chaque semaine : une soirée (envies et audace
  pour le formulaire), une question à se poser, un défi.
- Le duo le commence depuis « Mon couple » (`public.programmes_duo`, date de début). Chaque semaine s'ouvre à son tour ;
  sa soirée se compose d'un geste, son défi se valide comme ceux de la semaine.

## C14. Le mode « Ce soir »

- Sur l'accueil, « Ce soir, maintenant » : la position du téléphone (avec l'accord du couple), une soirée qui commence
  dans une demi-heure, pour trois heures, la première étape à 3 km au plus.
- Côté serveur, la composition reçoit un point de départ (`origin`, `radius`) et ne garde, pour la première étape, que
  les activités assez proches ; les suivantes suivent la règle des trajets existante.
- Sans position (refusée, ou indisponible) : le formulaire habituel, réglé sur ce soir.

## C16. Le bilan du lendemain

- Sur l'écran du Livre, une fois la soirée passée : trois questions. Le moment préféré (une étape), à refaire (des
  étapes), à éviter (des étapes).
- « À refaire » et « à éviter » deviennent des votes de goûts (`public.gouts`, +1 et −1) : la composition s'en sert déjà.
  Le moment préféré est rangé dans `public.bilans` et rappelé sous le Livre de la soirée, celui de l'autre une fois le sien donné.

## D'où vient le contenu

Tout le contenu (questions, quiz, défis, cartes, saisons, programme) est **écrit pour l'app, en français**, et rangé en
base par les migrations. Il n'est recopié d'aucun livre ni d'aucun jeu ; il s'inspire de travaux publiés :

- **Arthur Aron et al., 1997**, « The Experimental Generation of Interpersonal Closeness » : des questions qui vont du
  léger au plus intime rapprochent deux personnes. D'où les paliers de la question du jour, rencontrés dans l'ordre.
- **John Gottman**, les « love maps » (connaître le monde intérieur de l'autre) et les rituels de connexion : d'où le quiz
  (deviner ce que l'autre répond) et les défis-rituels.
- **La théorie de l'expansion de soi** (Aron et Aron) : les activités nouvelles faites à deux ravivent le couple. D'où
  l'audace croissante du programme et les défis-sorties vers les activités de la base.

- **Les formats des quiz et jeux de questions pour couples** (Ozer, Quiz Couple, les tests de Psychologies et de Elle,
  les questions pièges de Bridebook, les listes fun et profondes de Tostadora ou Mariages.net) : leurs univers
  (communication, aventure, absurde, étincelle), leurs niveaux, les questions pièges sur la mémoire partagée et le
  quotidien, le « tu préfères ». Aucune de leurs questions n'est reprise : on n'en garde que les formats, et le ton,
  drôle d'abord, profond ensuite.
- Les cartes du soir suivent le même chemin : celles d'un duo s'approfondissent avec ses soirées vécues (profondeur 2 dès
  la deuxième, 3 dès la quatrième).

Les activités elles-mêmes restent celles de la collecte (les sources de CLAUDE.md).

## Les phases

1. **Le duo, la question du jour, la jauge** : migration (duo, questions, réponses, `complicite()`), écran « Mon
   couple », jauge à points sur l'accueil.
2. **Quiz, défis, cartes du soir** et les déblocages des paliers.
3. **Les dates** : dates qui comptent, saisons, « Il y a un an », météo (`surprise.rappels`, Open-Meteo).
4. **La routine** : programme 4 semaines, mode « Ce soir », bilan du lendemain.

Chaque phase passe `uv run pytest`, `npm test` et `npm run e2e` avant d'être commitée.
