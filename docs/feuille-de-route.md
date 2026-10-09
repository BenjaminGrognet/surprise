# Feuille de route — faire revenir, faire connaître, gagner un peu

Idées pour Secret Date et Secret Squad, classées par objectif, avec ce qui existe déjà et l'effort estimé
(S : une journée, M : quelques jours, L : une à deux semaines). Rédigé le 8 octobre 2026.

## Fait le 8 octobre 2026

| Quoi | Pour | Où |
| --- | --- | --- |
| Emails des moments clés (soirée gardée et ses réservations, pli scellé, veille, Livre des Secrets, « À votre tour », prochaine intrigue), et les mêmes en push sur le web | Faire revenir : le web n'avait aucune notification | `surprise.courriers`, README § Emails |
| Invitation par email depuis la soirée (passager, bande, complices) | Faire connaître : chaque soirée amène un compte | carte « Votre passager » / « Votre bande » |
| Liens partenaires sur les « Réserver » (GetYourGuide, Civitatis, Awin), dans l'app et les emails | Gagner : il ne reste qu'à s'inscrire aux programmes | `surprise.affiliation`, docs/affiliation.md |
| Composition deux fois plus rapide, base chargée trois fois plus vite, deux fois moins de données écrites par soirée | Tenir la charge, répondre vite | `parcours`, `patterns`, `originality` |

À activer : `SMTP_URL`, `MAIL_FROM`, `MAIL_SECRET`, `APP_URL` dans `.env`, le serveur lancé avec `--courriers` ; les
identifiants d'affiliation dans `.env`. Les deux migrations sont passées sur le Supabase du projet le 8 octobre 2026.

## 1. Ergonomie : moins de friction à l'entrée

Aujourd'hui, tout visiteur bute sur la page de connexion, et au téléphone (375 × 812) le formulaire commence aux trois
quarts de l'écran, sous le texte de présentation.

- **Essayer avant le compte** (M) : composer et voir ses trois intrigues sans compte ; le compte n'est demandé que pour
  garder la soirée. C'est le moment où l'envie est la plus forte. L'API compose déjà sans compte ; c'est le garde de
  `_layout.tsx` qui l'empêche.
- **Connexion sans mot de passe** (S) : un lien ou un code par email (Supabase Auth OTP), surtout pour le passager qui
  arrive par une invitation : un geste au lieu d'un compte à créer. Puis Apple et Google.
- **La page d'entrée au téléphone** (S) : le formulaire et « Créer un compte » d'abord, le texte ensuite ou replié.
- **Un quiz en deux temps** (M) : 4 questions pour la première soirée (envie, audace, budget, ce qu'on ne veut
  jamais), les 8 autres proposées après, une par écran, quand l'appli a déjà fait ses preuves.
- **Un seul écran le lendemain** (S) : sceller sa page et voter les étapes au même endroit (deux demandes aujourd'hui).

## 2. Faire revenir

- **Les dates qui comptent** (M) : l'anniversaire de rencontre, ceux de chacun, gardés dans le compte ; trois semaines
  avant, un email et une notification « Votre anniversaire approche : trois intrigues vous attendent », la soirée déjà
  composée. Une table `dates_cles` et un moment de plus dans `surprise.courriers`. Le levier le plus fort pour une app
  qu'on n'ouvre que quelques fois par an.
- **Le rendez-vous du jeudi** (S) : un email facultatif « Ce week-end à Paris » avec trois activités insolites
  nouvellement collectées (le score d'originalité les trie déjà), un bouton « Composer autour ».
- **Les saisons** (S chacune) : Saint-Valentin, Fête de la musique, Nuit Blanche, Halloween, Noël : une envie et une
  trame de saison, un email aux comptes qui n'ont pas de soirée à venir.
- **La carte de vos soirées** (M) : Paris qui s'allume quartier par quartier, au fil des soirées faites (la jauge de
  complicité existe ; la prolonger en carte et en petits trophées : « 5 quartiers », « 3 premières fois »).
- **Le plan B prévenu** (S) : une étape annulée ou complète, un email et un push à l'instigateur avec la remplaçante en
  un geste (le plan B existe ; personne n'en est averti).

## 3. Faire connaître

Le passager est la boucle d'acquisition naturelle : chaque soirée amène un compte, une soirée de bande jusqu'à neuf.

- **« À votre tour », prêt à l'emploi** (S) : le lien de l'email J+4 ouvre une première intrigue déjà composée pour le
  passager (ses goûts ressemblent à ceux du couple), à garder en un geste.
- **La carte postale qui amène quelqu'un** (S) : l'adresse de l'app et un QR code discrets sur la carte partagée en
  story (aujourd'hui, seul le nom secret y figure).
- **La fin d'une soirée de bande** (S) : chaque invité d'un EVJF reçoit le lendemain « Organisez la vôtre », avec le
  livre de la soirée pour preuve. Dix personnes, dix futurs instigateurs.
- **Parrainage** (M) : « Offrez une soirée à des amis » ; quand l'invité garde sa première soirée, les deux comptes
  débloquent une option payante (voir plus bas).
- **Des pages publiques** (M) : « Les soirées les plus insolites du Marais », « Un EVJF à Pigalle »… tirées de la base
  (originalité, quartier, envie), pour le référencement ; dans l'app web (`app/`), comme le reste.

## 4. Gagner un peu

1. **L'affiliation** (fait dans le code) : s'inscrire aux programmes (docs/affiliation.md), mettre les identifiants
   dans `.env`. Premier revenu, sans rien retirer.
2. **Offrir une Secret Date** (M) : une carte cadeau (Noël, anniversaires, fête des amoureux) : l'enveloppe, le jour, le
   budget ; le destinataire compose avec. Le produit est déjà un cadeau : c'est la forme la plus naturelle de le vendre.
3. **Secret Date+** (L) : gratuit, une soirée par mois et ses trois intrigues ; payant (à l'unité ou au mois) : intrigues
   redessinées sans limite, la nuit à l'hôtel, les bandes au-delà de quatre, plus de vérifications de créneaux en direct.
   Paiement sur le web (Stripe) pour éviter la commission des stores sur un service consommé hors de l'app.
4. **La conciergerie** (M) : « On réserve pour vous » contre quelques euros : les réservations faites, cochées, le
   reçu en coulisses.
5. **Les lieux partenaires** (M) : un « coup de cœur » clairement signalé, ou une commission négociée en direct (bars
   Privateaser, restaurants Zenchef), jamais au détriment d'une meilleure activité.
6. **Les équipes** (L) : Secret Squad pour les entreprises (« sortie d'équipe ») : devis, facture, plusieurs bandes.

## 5. Pour tenir la charge

- **Un serveur public** (M) : l'API en HTTPS, `--courriers` qui tourne, la collecte de nuit (la fiche store le demande
  aussi).
- **Les candidats d'une soirée** (M) : encore 1,3 Mo écrits dans Supabase à chaque composition (94 % de bars sans
  réservation) : ne garder que leurs clés et leurs horaires vérifiés, le reste se recalcule depuis la base chargée.
- **Les compositions d'un même vendredi** (S) : les candidats d'une soirée (jour, nombre, horaires) gardés quelques
  minutes en mémoire et partagés entre les compositions : la plupart des demandes visent le vendredi et le samedi qui
  viennent.
- **Mesurer** (S) : erreurs (Sentry) et usage (PostHog, hébergé en Europe) : part des comptes qui gardent une soirée,
  délai entre garde et invitation, part des passagers qui composent à leur tour (le coefficient viral), soirées par
  couple et par trimestre, clics « Réserver » et commissions.
