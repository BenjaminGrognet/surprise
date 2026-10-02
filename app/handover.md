# Handover — SecretDate, « Midnight Emerald »

## Fait

- Nom : **SecretDate** (`app.json` : nom, schéma `secretdate`, interface sombre, fonds de splash/icône `#040F0A`).
- Charte « midnight emerald luxury » (branche `midnight`, `src/constants/theme.ts`) : nuit presque noire `#040F0A`,
  surfaces `#081A13` cernées d'un filet doré (`line`, or à 14 %), émeraude `#3DB787` pour ce qui vit (icônes, bouton
  principal, choix, jauges, point de statut), or champagne `#DBC18C` réservé aux chiffres et aux badges (compte à
  rebours, heures, prix, rôle), ivoire `#E9E5D8` pour le texte, sauge `#8F9E91` pour les petites capitales espacées.
  Sombre uniquement (light == dark). Polices : Cormorant Garamond (titres, noms, indices en italique) et Manrope (texte).
  Formes : tuiles arrondies à 22, cartes à 26, boutons en pilule (`Radius`).
- Cadre commun (`components/screen.tsx`) : plus de barre en haut (l'ancien `brand-header.tsx`, sa cloche et le salut de
  l'accueil sont retirés), et **barre d'onglets flottante** (`tab-bar.tsx`) : accueil, mes soirées (un
  grimoire), joyau émeraude au centre (nouvelle intrigue ; indices de la soirée pour le passager), boussole de
  l'instigateur vers la prochaine soirée (grisée sans soirée à venir), compte. Le profil du couple vit dans le compte
  (`persona-card.tsx`, partagée avec la fin du quiz ; « Modifier » rouvre le quiz prérempli, `/profil?modifier=1`).
  La barre s'appuie sur le Stack existant (`dismissTo('/')` pour l'accueil, `navigate` pour le reste) ; cachée sans
  compte et sur l'invitation. Jusqu'à 6 h, la soirée de la veille reste « la prochaine » (`eveningDay`), pour la nuit.
- **Haut de page commun** : chaque page s'ouvre directement sur sa carte (`PageCard` / `CardHead`, `intrigue-card.tsx` :
  émeraude taillée, emblème et « Secret Date » en or, badge doré court, titre en italique, texte justifié). Flèche
  retour dans la carte (`back`) sur révélation, livre et quiz ; ouverte par un lien direct, elle ramène à l'accueil.
  Badges : rôle (accueil, compte), « 3 secrets », « Votre profil » / « Sans profil », « 3 intrigues », prix « ≈ 104 € »,
  « Passager », « À sceller » / « Scellé », « 1 / 10 », « Invitation » ; tous tiennent sur une ligne à 360-375 px.
  Seule la page de connexion garde sa bannière.
- **Accueil, « Le Tableau des Complots »** (`index.tsx`) : salutation (portrait du persona, « Bonsoir », prénoms du
  profil), la prochaine soirée en carte de membre (`intrigue-card.tsx` : émeraude taillée en SVG, `emerald-facets.tsx`,
  monogramme, badge du rôle, titre secret en italique, compte à rebours en or), une ligne de statut (passager connecté,
  à inviter, prochain indice), la prochaine étape en photo (voilée pour le passager), la jauge de complicité
  (`lib/complicity.ts`).
- Typographie : `ThemedText` met une espace insécable avant ? ! : ; » et après «, pour qu'un signe ne parte pas seul à la ligne.
- **Préparation, « Le Filtre de vos Envies »** (`soiree.tsx`) : curseur d'humeur (`mood-slider.tsx`) de « Tamisé & Intime »
  à « Aventureux & Insolite », dont chaque cran est une envie du serveur (cocooning, romantique, nous, curieux,
  surprise) ; les autres envies sont les « options secrètes » (cases à cocher). Le serveur reçoit les mêmes `envies` qu'avant.
- **Jour J, « La Révélation »** (`revelation.tsx`, nouvelle route) : chaque téléphone choisit son rôle pour la soirée
  (gardé sur l'appareil, `lib/local-store.ts`). L'organisateur voit la feuille de route complète, les réservations à faire
  et les indices montrés à l'autre ; la personne surprise ne voit que des indices (`lib/clues.ts`, règles sans appel à Claude)
  qui se débloquent de 24 h à 2 h avant, et un programme flouté dont chaque étape se dévoile 15 min avant son heure.
- **La boussole du jour J** (`compass-guide.tsx`, dans la feuille de route de l'instigateur) : du matin du jour J à la
  fin de la dernière étape (après minuit compris), l'étape en cours, la suivante avec son trajet et l'heure de départ,
  et « Itinéraire » vers Google Maps depuis la position du téléphone (à pied ou en métro comme prévu ; au premier
  rendez-vous, Maps choisit).
- Garder une intrigue mène à la Révélation ; dans l'historique, une soirée à venir reste scellée (titre caché).
- Vérifié sur le web en 375 px : accueil, filtre (curseur glissé), composition, révélation (les deux rôles), quiz.

## Pas fait / à trancher

- **Avec un compte, pas vu à l'écran** : Supabase n'est pas configuré ici (`app/.env` absent), donc la jauge de complicité,
  le compte à rebours de l'accueil et la pastille « Complices connectés » n'ont pas été vus avec de vraies données.
- **Non testé sur natif** (iOS/Android) : le flou des photos (`blurRadius`) et le glisser du curseur sont à vérifier sur un appareil.
- **Rôle par appareil** : un même compte pour le couple, donc rien n'empêche la personne surprise de choisir « J'organise ».
  Un vrai secret demanderait deux comptes liés.
- **Pas de chauffeur** : l'indice « votre chauffeur arrive à 19h30 » de la maquette devient « le rideau se lève à 19h15 ».
- **Refonte « midnight », natif** : la barre d'onglets flottante, les ombres (`boxShadow`) et la carte en SVG n'ont été
  vues que sur le web (375 px et bureau). La carte de soirée, la ligne de statut et l'étape en photo ont été vérifiées
  avec une soirée fictive (le compte de test n'en avait pas).
- **Boussole** : vue sur le web avec une soirée composée et l'horloge du navigateur avancée (avant, pendant, après
  minuit, la veille) ; pas encore un vrai jour J, ni sur téléphone. La boussole active de la barre n'a pas été vue :
  le compte de test n'a aucune soirée gardée.
