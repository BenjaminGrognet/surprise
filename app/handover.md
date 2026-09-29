# Handover — relooking beige & or

## Fait

- Palette (`src/constants/theme.ts`) : fond beige `#faf8f5`, cartes crème `#f3ece0`, accent or `#caa15a`, encre `#2e241c`. `Night` (reveal du profil) inchangé, déjà cohérent avec l'or.
- Composants partagés recolorés : `option-button.tsx` (cartes sans bordure, radius 20, ombre or + badge coche sur sélection), `buttons.tsx` (ombre or sur le CTA), `day-field.tsx` (champ sans bordure).
- `soiree.tsx`, `profil.tsx` (quiz) et `index.tsx` (accueil) : badge "Soirée à deux" + barre de progression.
- `compte.tsx`, `profil.tsx`, `historique.tsx` : champs/cartes sans bordure, couleurs alignées.
- Vérifié en web (accueil, quiz, soirée, compte) : palette, sélection, CTA, progression OK.

## Pas fait / à trancher

- **Badge + barre de progression** ajoutés sur `soiree.tsx`, `profil.tsx` et `index.tsx`. Sur l'accueil, la barre est statique (1/3, pas de logique d'étape réelle) — à relier à un vrai état si un jour l'onboarding devient un vrai wizard à 3 étapes.
- **CTA en dégradé** : les maquettes proposaient un dégradé or (`#caa15a → #e4c07a`). Le code garde un aplat (pas de `expo-linear-gradient` installé). Ajouter la dépendance si le dégradé est jugé nécessaire.
- **Compte / historique non testés en conditions réelles** : Supabase n'est pas configuré dans cet environnement, donc les onglets connexion/inscription et les cartes d'historique n'ont pas pu être vérifiés à l'écran (seul le message de repli "comptes non configurés" a été vu).
- **Non testé sur natif** (iOS/Android, Expo Go) : uniquement vérifié sur le build web (`npx expo start` → web). Le radius/ombre RN (`shadowColor`/`elevation`) est à vérifier sur device.
- **Couleur d'erreur** (`#ff5c72`, plusieurs fichiers) laissée telle quelle — rouge/corail générique pour les messages d'erreur, pas retouchée pour rester lisible comme signal d'alerte. À revoir si le corail détonne trop avec la nouvelle palette.
- **Lint pré-existant** non lié à ce chantier : `src/hooks/use-color-scheme.web.ts:11` (`react-hooks/set-state-in-effect`) — présent avant le relooking, pas corrigé.
- **Dark mode** : `Colors.dark === Colors.light` (ponytail existant, non traité ici) — pas de variante sombre dédiée pour la nouvelle palette.
