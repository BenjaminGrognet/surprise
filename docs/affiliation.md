# Affiliation — les liens « Réserver » de Secret Date

Les boutons « Réserver » et « Valider la table » mènent aux sites de billetterie et de réservation. Avec des liens
affiliés, chaque réservation faite par ces liens rapporte une commission, sans rien changer pour le couple. C'est
le premier revenu à mettre en place : presque rien à coder, et aucune fonctionnalité retirée.

Les taux ci-dessous ont été relevés le 6 octobre 2026 sur les pages publiques des programmes et dans des annuaires
d'affiliation. Ils changent souvent : chaque contrat fait foi.

## Par où commencer : les sites vers lesquels l'app envoie

Dans la base locale (`data/surprise.db`, état du 27 septembre 2026), 14 872 activités sont gardées, dont 11 744
réservables en ligne. Leurs liens de réservation vont surtout vers :

| # | Site | Liens | Programme | Réseau | Commission relevée | Cookie | Priorité |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| 1 | shotgun.live | 2 018 | Pas de programme public ; « promoteurs » par événement, accordés par l'organisateur | Shotgun | À négocier | — | Partenariat |
| 2 | getyourguide.com | 1 686 | Partner Program | Direct (aussi via Travelpayouts) | 8 %, négociable au volume | 31 j | **1** |
| 3 | fnacspectacles.com | 1 561 | Fnac Spectacles FR | Awin (ouvert) | Non publiée | 30 j | **1** |
| 4 | wecandoo.fr | 1 441 | Programme d'affiliation | À confirmer auprès de Wecandoo | 8 % | 45 j | **1** |
| 5 | billetreduc.com | 1 197 | Aucun programme public trouvé | — | — | — | Contact direct |
| 6 | funbooker.com | 1 138 | Programme à commission variable (pas de SEA) | Réseaux tiers (Cuelinks) | Variable | ? | 2 |
| 7 | bookings.zenchef.com | 554 | Aucun (logiciel des restaurants) | — | — | — | Partenariats lieux |
| 8 | ticket.parisjetaime.com | 157 | Aucun programme public trouvé (Office du tourisme) | — | — | — | Contact direct |
| 9 | Fever (fever.pxf.io, feverup.com) | 157 | Fever Affiliate Program | Impact | Non affichée ; ≈ 6,4 % selon les annuaires | Court (1 j selon les annuaires) | 2 |
| 10 | eventbrite.fr / .com | 131 | Pas de programme public (fermé sur les réseaux) | — | — | — | — |
| 11 | billetweb.fr | 97 | Aucun | — | — | — | — |
| 12 | TheFork (lafourchette, thefork.fr) | 96 | TheFork | Awin (selon les pays ; France à vérifier) | ? | 20 j | 2 |
| 13 | dice.fm | 53 | Aucun programme public trouvé | — | — | — | — |
| 14 | tiqets.com | 52 | Tiqets | Awin (sélectif), FlexOffers | ≈ 6 % (4,8 % selon les pays) | 30 j | 2 |
| 15 | ticketmaster.fr | 45 | Ticketmaster France | Impact | 0,32 € par vente | 30 j | 3 |

Hors de cette liste, mais utiles à Secret Date :

| Site | Pour quoi | Réseau | Commission relevée | Cookie |
| --- | --- | --- | --- | --- |
| civitatis.com | Visites, activités (4 dans la base) | Direct (`?aid=` à ajouter au lien) | 8 à 10 % selon le volume, 1 € par participant aux visites gratuites | 30 j |
| Booking.com | Les hôtels du mode « découcher » | CJ ou Awin depuis juin 2025 (plus de programme direct) | ≈ 4 % des séjours effectués | Session seulement |
| Expedia, Hotels.com | Hôtels | Travel Creator Program (paiements par Partnerize) | Jusqu'à 4 % | ? |
| Viator | Activités (pas encore une source) | Direct, aussi via Travelpayouts | 8 % | 30 j |
| Travelpayouts | Un seul compte pour GetYourGuide, Tiqets, Viator, Klook… | Agrégateur | Celle de chaque marque | Celle de chaque marque |

À noter : les 110 liens `fever.pxf.io` sont déjà des liens de suivi Impact, venus tels quels du flux de Fever avec
l'identifiant d'un autre affilié. Une fois inscrit chez Fever, il faut les remplacer par les vôtres.

## Les démarches

### 1. Avant de candidater

- **Une structure pour encaisser** : micro-entreprise ou société (SIRET, RIB). Les commissions sont un revenu, à
  déclarer, avec la TVA selon le régime.
- **Un site public qui présente l'app** : presque tous les programmes le demandent (Civitatis refuse les partenaires
  présents seulement sur les réseaux sociaux ; Fever veut « un site, une plateforme ou une app »). Le site doit avoir
  des mentions légales et une politique de confidentialité qui parle des liens partenaires et de leurs cookies.
- **La transparence** : signaler dans l'app que certains liens sont des liens partenaires, par exemple une ligne
  sous « Réserver » ou dans le compte. Apple autorise ces liens, puisque la réservation est un service consommé hors
  de l'app (règle 3.1.3(e)).

### 2. Les inscriptions, dans l'ordre

1. **GetYourGuide**, en direct sur [partner.getyourguide.com](https://partner.getyourguide.com/) : le plus de liens
   avec un programme ouvert, 8 %. Il donne un identifiant partenaire à ajouter aux liens.
2. **Awin**, pour Fnac Spectacles, puis TheFork et Tiqets. L'inscription demande un dépôt de 1 € (ou 1 £, ou
   1 $), remboursé avec le premier paiement. Ensuite, candidater annonceur par annonceur depuis l'interface.
3. **Wecandoo** : 8 % et 45 jours. Demander le formulaire d'affiliation à Wecandoo (le réseau utilisé n'est pas
   public).
4. **Impact**, pour [Fever](https://business.feverup.com/en/partner-programs/affiliate-program/) (le lien
   d'inscription est sur cette page), puis Ticketmaster si le volume le justifie.
5. **Civitatis**, en direct sur [civitatis.com/en/affiliates](https://www.civitatis.com/en/affiliates/content-creators) :
   il suffit d'ajouter `?aid=<numéro>` aux liens.
6. **Les hôtels** (mode « découcher ») : Booking.com par CJ ou Awin, ou le
   [Travel Creator Program d'Expedia](https://partner.expediagroup.com/en-us/solutions/explore-our-affiliate-program).
7. **Les sites sans programme**, par e-mail aux partenariats, avec les chiffres de la base. Ce sont Shotgun
   (2 018 liens), BilletRéduc (1 197), la billetterie de Paris je t'aime (157) et Funbooker si son programme ne
   convient pas. Leur proposer un code de suivi ou une commission sur les ventes envoyées.

Pour aller plus vite au début, [Travelpayouts](https://www.travelpayouts.com/) ouvre GetYourGuide, Tiqets et Viator
avec un seul compte, contre une part de la commission.

### 3. Dans le code (fait le 8 octobre 2026)

`src/surprise/affiliation.py` transforme les liens « Réserver » au moment de servir la soirée (`parcours.soiree_json`)
et dans les emails (`surprise.courriers`), d'après des règles par domaine :
- GetYourGuide : `partner_id` (`GETYOURGUIDE_PARTNER_ID`) ;
- Civitatis : `aid` (`CIVITATIS_AID`) ;
- Awin : son lien profond `https://www.awin1.com/cread.php?awinmid=<annonceur>&awinaffid=<vous>&clickref=<page>&ued=<lien encodé>`
  (`AWIN_PUBLISHER_ID`, et `AWIN_MERCHANTS=fnacspectacles.com:1234,thefork.fr:5678` : l'identifiant de chaque annonceur) ;
- Impact (Fever) : lien profond généré dans son interface, pas encore branché.

Les identifiants sont dans `.env`, jamais dans le dépôt ; sans eux, les liens restent tels quels. Le sous-identifiant
est le nom de la page de la soirée (`cmp`, `clickref`), sans donnée personnelle. L'étape servie dit `partner: true`, et
Mon compte prévient que certains liens sont partenaires. Les tests (`tests/test_affiliation.py`) vérifient chaque règle :
le lien d'origine gardé, le paramètre ajouté une fois, les domaines inconnus tels quels.

### 4. Ensuite

- **Le suivi** : réservations, taux de conversion par source, soirées qui convertissent. Les plateformes à fort taux
  (GetYourGuide, Wecandoo) méritent alors un léger avantage dans la composition, à condition de ne jamais faire
  passer une activité moins bonne devant une meilleure.
- **Les paiements** : chaque réseau a son seuil et son rythme (mensuel le plus souvent ; Civitatis paie chaque mois
  par virement ou PayPal).

## Sources

- [GetYourGuide Partner Program](https://partner.getyourguide.com/)
- [Travelpayouts : GetYourGuide](https://travelpayouts.com/en/offers/getyourguide-affiliate-program)
- [Civitatis : affiliés créateurs de contenu](https://www.civitatis.com/en/affiliates/content-creators)
- [Fever Affiliate Program](https://business.feverup.com/en/partner-programs/affiliate-program/)
- [Awin : nouveau programme Tiqets](https://www.awin.com/us/news-and-events/program-news/new-affiliate-program-tiqets)
- [Awin : frais d'inscription](https://success.awin.com/articles/en_US/Knowledge/Why-do-I-have-to-pay-the-sign-up-fee)
- [Booking.com passe ses affiliés chez Awin et CJ](https://www.netinfluencer.com/booking-com-moves-all-affiliates-to-awin-what-to-know-about-termination-notices)
- [Expedia Group : programme d'affiliation](https://partner.expediagroup.com/en-us/solutions/explore-our-affiliate-program)
- [Wecandoo (annuaire affi.io)](https://affi.io/m/wecandoo)
- [TheFork (annuaire affi.io)](https://affi.io/m/thefork)
- [Fnac Spectacles (annuaire affsignal)](https://affsignal.com/merchant/Fnacspectacles)
- [Ticketmaster France (annuaire Affilitizer)](https://www.affilitizer.com/programs/ticketmaster.fr)
- [Funbooker (annuaire Cuelinks)](https://www.cuelinks.com/campaigns/funbooker-affiliate-program)
- [Shotgun : gestion des promoteurs](https://support-pro.shotgun.live/hc/en-us/articles/13970546627858--Promoters-Management)
- [Viator (annuaire Affilimate)](https://affilimate.com/programs/viator-affiliate-program/)
