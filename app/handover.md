# Handover — SecretDate, « Midnight Emerald »

## Fait

- Nom : **SecretDate** (`app.json` : nom, schéma `secretdate`, interface sombre, fonds de splash/icône `#0A1F1D`).
- Charte (`src/constants/theme.ts`) : fond émeraude `#0A1F1D`, or champagne `#D4AF37` (boutons, filets, jauges),
  crème `#FFFDD0`, texte blanc cassé `#F4F1E8`. Sombre uniquement (light == dark). Polices : Playfair Display
  (titres, indices en italique) et Inter (texte), à la place de Fredoka / Space Grotesk.
- Cadre commun (`components/screen.tsx`) avec l'en-tête `brand-header.tsx` (logo + pastille « Complices connectés »).
  Les bannières photo génériques et le badge « Soirée à deux » sont retirés.
- **Accueil, « Le Tableau des Complots »** (`index.tsx`) : une carte scellée (`intrigue-card.tsx`) avec le compte à rebours
  jusqu'à la prochaine soirée gardée et l'indice du jour ; bouton « Lancer une nouvelle intrigue » ; jauge de complicité
  (`lib/complicity.ts` : un point par soirée vécue, niveaux nommés).
- **Préparation, « Le Filtre de vos Envies »** (`soiree.tsx`) : curseur d'humeur (`mood-slider.tsx`) de « Tamisé & Intime »
  à « Aventureux & Insolite », dont chaque cran est une envie du serveur (cocooning, romantique, nous, curieux,
  surprise) ; les autres envies sont les « options secrètes » (cases à cocher). Le serveur reçoit les mêmes `envies` qu'avant.
- **Jour J, « La Révélation »** (`revelation.tsx`, nouvelle route) : chaque téléphone choisit son rôle pour la soirée
  (gardé sur l'appareil, `lib/local-store.ts`). L'organisateur voit la feuille de route complète, les réservations à faire
  et les indices montrés à l'autre ; la personne surprise ne voit que des indices (`lib/clues.ts`, règles sans appel à Claude)
  qui se débloquent de 24 h à 2 h avant, et un programme flouté dont chaque étape se dévoile 15 min avant son heure.
- Garder une intrigue mène à la Révélation ; dans l'historique, une soirée à venir reste scellée (titre caché).
- Vérifié sur le web en 375 px : accueil, filtre (curseur glissé), composition, révélation (les deux rôles), quiz.

## Pas fait / à trancher

- **Avec un compte, pas vu à l'écran** : Supabase n'est pas configuré ici (`app/.env` absent), donc la jauge de complicité,
  le compte à rebours de l'accueil et la pastille « Complices connectés » n'ont pas été vus avec de vraies données.
- **Non testé sur natif** (iOS/Android) : le flou des photos (`blurRadius`) et le glisser du curseur sont à vérifier sur un appareil.
- **Rôle par appareil** : un même compte pour le couple, donc rien n'empêche la personne surprise de choisir « J'organise ».
  Un vrai secret demanderait deux comptes liés.
- **Pas de chauffeur** : l'indice « votre chauffeur arrive à 19h30 » de la maquette devient « le rideau se lève à 19h15 ».
