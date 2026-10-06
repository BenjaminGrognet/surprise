# Fiche store — Secret Date

Ce qu'il faut pour publier l'app sur l'App Store et Google Play : textes à coller, images (`captures/`), réponses
aux questionnaires, et ce qui bloque encore. Préparé le 6 octobre 2026.

## Ce qui bloque encore la publication

1. **Les images et les textes des activités** : l'app montre les photos des sites et garde le texte des médias
   (`lead_text`). Il faut régler les deux avant tout usage public (CLAUDE.md) : photos sous licence ou de la maison,
   textes réécrits. Les captures de `captures/` ne montrent que les images de l'app (bannières) ; il faut vérifier
   que leurs droits sont bien acquis.
2. **Identifiants de l'app** (`app/app.json`) : `fr.secretdate.app` est posé pour iOS et Android (le widget en a
   besoin), avec `fr.secretdate.app.widgets` et `group.fr.secretdate.app` pour le widget iPhone. À confirmer avant
   la première build : ils ne changent plus après la première publication. Le `slug` vaut encore `app`.
3. **Un serveur public** : l'API Python en HTTPS (`EXPO_PUBLIC_API_URL`). Le Supabase du projet a reçu le
   6 octobre ses deux migrations manquantes (`reveal_mode`, `gouts`). Il n'a pas d'historique de migrations :
   `supabase db push` voudrait tout rejouer. Marquer d'abord les migrations comme appliquées
   (`supabase migration repair --status applied …`).
4. **Trois pages web** :
   - une politique de confidentialité ;
   - une page d'assistance (contact) ;
   - pour Google Play, une page qui permet de demander la suppression du compte sans l'app.
5. **Les textes de permission en français** : localisation (« Je suis arrivé(e) ») et notifications. Les déclarer
   dans `app.json` (plugin `expo-location`, `locationWhenInUsePermission`) plutôt que les messages anglais par
   défaut. Ajouter aussi l'icône Android des notifications, monochrome.
6. **Des comptes de démonstration pour la vérification Apple** : un instigateur avec une soirée gardée à venir, et
   son passager.

## App Store Connect

| Champ | Limite | Texte |
| --- | --- | --- |
| Nom | 30 | Secret Date |
| Sous-titre | 30 | Soirées surprises en couple |
| Catégorie principale | | Style de vie |
| Catégorie secondaire | | Divertissement |
| Prix | | Gratuit |

**Texte promotionnel** (170 caractères, modifiable sans nouvelle version) :

> Une semaine de mystère avant chaque soirée : un indice chaque matin, un mot mystère par étape, et le jour J, les voiles se lèvent un à un.

**Mots-clés** (100 caractères, sans espaces ; le nom est déjà indexé) :

```
couple,soirée,surprise,paris,rendez-vous,amoureux,sortie,idée,romantique,anniversaire,cadeau,indice
```

**Description** (4 000 caractères) :

```
Secret Date compose des soirées surprises à deux, à Paris, et garde le secret jusqu'au bout.

L'un de vous devient l'instigateur. Une humeur, deux envies (rire, danser, créer de vos mains, frissonner…), un budget, un jour : Secret Date trame trois intrigues. Un dîner, un spectacle, un atelier, un bar caché, enchaînés à pied ou en métro, réglés à la minute. Une étape ne vous plaît pas ? Changez-la.

L'autre devient le passager. Rien qu'un nom de code, « Le Rideau rouge du Palais-Royal », un jour, une heure… et des indices. Toute la semaine, l'histoire se déroule en chapitres : la tenue à prévoir, le budget, un mot mystère pour chaque étape. Le jour J, chaque voile se lève un quart d'heure avant son heure.

POUR L'INSTIGATEUR
• Trois intrigues sur mesure, parmi des milliers de sorties parisiennes vraiment réservables
• Une feuille de route à la minute, trajets compris
• Les réservations à faire, cochées une à une, et un rappel tant qu'il en reste
• La boussole du jour J : l'étape en cours, la suivante, l'heure de partir
• Un plan B en un geste si une étape tombe à l'eau
• Les coulisses : ce que lit votre passager, et ce que son téléphone lui dira
• Un carton d'invitation à imprimer, avec son QR code, à glisser sous l'oreiller

POUR LE PASSAGER
• Une invitation, puis rien que des indices
• Un récit en notifications, du pli scellé une semaine avant au rideau qui se lève
• Des mots mystères qui deviennent des noms, étape après étape

POUR TOUS LES DEUX
• Un widget sur l'écran d'accueil : le compte à rebours et le dernier indice
• Une carte postale de la soirée à partager en story, sans rien dévoiler

APRÈS LA SOIRÉE
• Le Livre des Secrets : chacun scelle sa page, une photo et un mot, puis découvre celle de l'autre
• Un pouce sur chaque étape : les soirées suivantes suivent vos goûts
• Et c'est à votre tour de surprendre

Sans publicité. Disponible à Paris.
```

**URL** : assistance, marketing (facultative), politique de confidentialité (obligatoire), à héberger (voir plus haut).

**Classification par âge** : répondre au questionnaire honnêtement. Les bars et clubs reviennent souvent (références
à l'alcool), et l'option « Pimenter la soirée » touche à des thèmes suggestifs. La note calculée sera
vraisemblablement haute (16+ ou 18+), ce qui va avec un public de couples adultes.

**Confidentialité de l'app** (« étiquette nutritionnelle ») : aucune donnée n'est utilisée pour le suivi publicitaire.

| Donnée | Collectée | Liée à l'identité | Usage |
| --- | --- | --- | --- |
| Adresse e-mail | oui | oui | Fonctionnalités de l'app (compte) |
| Identifiant utilisateur | oui | oui | Fonctionnalités de l'app |
| Photos | oui | oui | Fonctionnalités (Livre des Secrets) |
| Autre contenu (notes, réponses au quiz, votes) | oui | oui | Fonctionnalités, personnalisation |
| Localisation | non | | Lue sur le téléphone seulement (« Je suis arrivé(e) »), jamais envoyée |

La suppression du compte se fait dans l'app (Mon compte → Supprimer mon compte…), comme Apple l'exige.

**Notes pour la vérification** (à adapter) :

```
Secret Date se joue à deux comptes. Compte instigateur : <email> / <mot de passe> : il a une soirée gardée à venir (onglet boussole), ses réservations et la semaine de son passager (« Les Coulisses »). Compte passager : <email> / <mot de passe> : il ne voit que les indices de cette soirée (onglet clé). Les notifications sont locales, programmées sur l'appareil. Les liens « Réserver » ouvrent les sites des lieux dans le navigateur.
```

## Google Play Console

| Champ | Limite | Texte |
| --- | --- | --- |
| Nom | 30 | Secret Date : soirées à deux |
| Description courte | 80 | Des soirées surprises à Paris : l'un compose, l'autre n'a que des indices. |
| Description complète | 4 000 | La même que l'App Store |
| Catégorie | | Style de vie |

- **Images** :
  - `captures/google-play/` : 8 captures en 1080 x 1920 (9:16), le maximum de Google Play ;
  - `feature-graphic-1024x500.png` (obligatoire) ;
  - `icone-512.png`.
- **Classification du contenu** (questionnaire IARC) : mêmes réponses qu'Apple ; une note PEGI 16 ou 18 est probable.
- **Sécurité des données** : mêmes données que dans le tableau Apple. Elles sont chiffrées en transit (HTTPS,
  Supabase), et l'utilisateur peut demander leur suppression dans l'app et par la page web de suppression.
- **Compte développeur personnel récent** : Google demande un test fermé avec au moins 12 testeurs pendant 14 jours
  avant la production.

## Les captures

`captures/app-store/` (1320 x 2868, l'écran de 6,9 pouces que demande Apple : les 10) et `captures/google-play/`
(1080 x 1920 : les 8 sans la 02 ni la 08), dans cet ordre :

| # | Écran | Légende |
| --- | --- | --- |
| 01 | Accueil de l'instigateur, compte à rebours | Une soirée surprise à Paris |
| 02 | Le filtre des envies | Une humeur, deux envies |
| 03 | Les trois intrigues composées | Trois intrigues au choix |
| 04 | La feuille de route (L'Aventure) | Une feuille de route à la minute |
| 05 | Accueil du passager, l'étape voilée | Votre complice ne sait rien |
| 06 | Les indices du passager, en chapitres | Un indice chaque matin |
| 07 | La semaine du passager vue des coulisses | Une semaine en chapitres |
| 08 | Les coulisses : réservations, ce que voit le passager | Vous tirez les ficelles |
| 09 | La carte postale de la soirée | Une carte pour vos stories |
| 10 | Le carton d'invitation à imprimer, avec son QR code | Un carton à glisser sous l'oreiller |

`captures/exemple-carte-postale.png` montre la carte postale telle qu'elle est partagée (1080 x 1920).

L'icône de l'App Store est celle de l'app, `app/assets/images/logo-secretdate.png` : 1024 x 1024, sans transparence, comme Apple le veut.

Pour les refaire avec le site des tests (Supabase local lancé, `npm run build:e2e` fait) :

```bash
uv run python tests/e2e_server.py --port 8011
```

```bash
cd app && node scripts/store-captures.js
```

Le script crée deux comptes de test, compose une soirée pour le lendemain, la garde, invite le passager et
photographie chaque écran comme un téléphone de 440 x 956 points. Il bloque les photos des sites : seules les
images de l'app apparaissent.
