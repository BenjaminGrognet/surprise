# Mettre Secret Date en ligne : le site, l'app, gratuitement

Le site (qui est l'app Expo construite pour le web), l'API, les emails, la collecte de la nuit et les sauvegardes
tournent sur une machine Linux **Oracle Cloud « Always Free »**, toujours allumée. La base, les comptes et les photos
du Livre restent sur **Supabase** (plan gratuit). L'app téléphone se construit dans le cloud d'Expo (**EAS**).

Compter une heure la première fois pour le site, une de plus pour l'app Android. Les commandes `bash` se tapent sur la
machine (après `ssh`), les commandes PowerShell sur le PC.

## Ce que ça coûte

| Morceau | Où | Prix |
|---|---|---|
| Base, comptes, photos du Livre | Supabase, plan gratuit (gardé tel quel) | 0 € |
| Site, API, emails, collecte de nuit, sauvegardes | Oracle Cloud Always Free (machine Ampere A1) | 0 € (carte bancaire demandée pour vérifier l'identité) |
| HTTPS | Caddy, certificat Let's Encrypt renouvelé seul | 0 € |
| Adresse du site | DuckDNS (`secretdate.duckdns.org`) | 0 € (un vrai domaine en `.fr` : environ 7 à 12 €/an, facultatif) |
| Emails | AgentMail ou Brevo (déjà branchés, README § Emails) | 0 € (plans gratuits) |
| Notifications push | Firebase Cloud Messaging (plan Spark) | 0 € |
| App Android à partager (APK) | EAS Build, plan gratuit | 0 € |
| App Android sur le Play Store | Compte développeur Google Play | 25 $ une fois |
| App iPhone (App Store ou TestFlight) | Apple Developer Program | 99 $/an, sans alternative gratuite |
| Surveillance (site tombé ?) | UptimeRobot ou Better Stack, plans gratuits | 0 € |

Sans payer Apple, les iPhone utilisent le site (Safari › Partager › « Sur l'écran d'accueil »), qui est la même app.

## 1. Le compte Oracle

1. Sur <https://www.oracle.com/cloud/free/>, « Start for free ».
2. **Région d'origine** : France Central (Paris) ou France South (Marseille). Elle ne pourra plus changer, et les
   machines gratuites ne se créent que dans cette région.
3. Une carte bancaire est demandée pour vérifier l'identité (une empreinte de 1 € environ, rendue). Rien n'est
   facturé tant que le compte reste en « Free Tier ».

Deux choses à savoir :

- Une machine gratuite peu utilisée (moins de 20 % de processeur, de réseau et de mémoire sur 7 jours) peut être
  arrêtée par Oracle. Passer le compte en « Pay As You Go » (Billing → Upgrade) l'évite et rend la création de machine
  plus facile quand la région est saturée ; les ressources « Always Free » restent gratuites. Dans ce cas, créer une
  alerte de budget à 1 € (Billing → Budgets) pour être prévenu au moindre centime.
- Si la création échoue avec « Out of capacity », réessayer plus tard ou avec moins de processeurs.

## 2. Une clé SSH, sur le PC

Dans PowerShell :

```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\oracle
```

Ça crée `oracle` (privée, ne jamais la donner) et `oracle.pub` (publique, à coller chez Oracle).

## 3. La machine

Console Oracle → Compute → Instances → **Create instance** :

| Réglage | Valeur |
|---|---|
| Name | `surprise` |
| Image | Canonical **Ubuntu 24.04** |
| Shape | Ampere **VM.Standard.A1.Flex**, **4 OCPU, 24 Go** (tout le quota gratuit ; 2 OCPU et 12 Go si la région est saturée) |
| Networking | réseau créé par défaut, **Assign a public IPv4 address** coché |
| SSH keys | « Paste public keys » : le contenu de `oracle.pub` |
| Boot volume | 50 Go (par défaut ; gratuit jusqu'à 200 Go) |

Une fois « Running », noter l'**adresse IP publique**. Pour qu'elle ne change jamais : Instance → Attached VNICs →
la VNIC → IPv4 Addresses → modifier → **Reserved public IP**.

**Ouvrir le web chez Oracle** : Instance → la Subnet → Security Lists → Default Security List → **Add Ingress Rules** :
source `0.0.0.0/0`, protocole TCP, port de destination `80`. Puis une deuxième règle identique pour `443`. (Le pare-feu
de la machine elle-même est ouvert par le script d'installation, étape 6.)

## 4. Une adresse (nom de domaine)

Le HTTPS demande un nom. Gratuit : <https://www.duckdns.org>, connexion avec GitHub ou Google, créer par exemple
`secretdate` → `secretdate.duckdns.org`, et y mettre l'IP publique. Avec un vrai domaine, créer un enregistrement
`A` vers l'IP.

## 5. Le code et les secrets

```powershell
ssh -i $HOME\.ssh\oracle ubuntu@IP_PUBLIQUE
```

Le dépôt GitHub est privé : la machine reçoit une clé de lecture seule.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/github -N ""
cat ~/.ssh/github.pub
```

Sur GitHub : dépôt `surprise` → Settings → Deploy keys → **Add deploy key**, coller la clé, sans cocher « Allow
write access ». Puis :

```bash
printf 'Host github.com\n  IdentityFile ~/.ssh/github\n' >> ~/.ssh/config
git clone git@github.com:BenjaminGrognet/surprise.git ~/surprise
```

Les secrets ne sont pas dans Git. Depuis le PC, dans PowerShell, à la racine du projet :

```powershell
scp -i $HOME\.ssh\oracle .env ubuntu@IP_PUBLIQUE:~/surprise/.env
scp -i $HOME\.ssh\oracle app\.env ubuntu@IP_PUBLIQUE:~/surprise/app/.env
```

Puis sur la machine, `nano ~/surprise/.env`, et changer :

```
APP_URL="https://secretdate.duckdns.org"
```

Ce dont le serveur a besoin : `SUPABASE_DB_URL` (le *session pooler*, IPv4), `SMTP_URL`, `MAIL_FROM`, `MAIL_SECRET`,
`APP_URL`, `FIREBASE_SERVICE_ACCOUNT` (et son fichier JSON, à copier aussi par `scp` vers le chemin indiqué), les
identifiants d'affiliation. Aucun code n'utilise `SUPABASE_SERVICE_ROLE_KEY` ni `SUPABASE_SECRET_KEY` : mieux vaut les
retirer du `.env` de la machine, et de `app/.env` partout (seules les lignes `EXPO_PUBLIC_…` y servent ; elles sont
publiques par nature, comme la clé anon). `EXPO_PUBLIC_API_URL` ne compte pas pour le site : en ligne, il appelle l'API
à sa propre adresse.

## 6. Tout installer, en une commande

```bash
bash ~/surprise/deploy/installer.sh secretdate.duckdns.org
```

Le script (`deploy/installer.sh`, relançable sans risque) :

- installe les outils : uv (Python), Node 22 (le build du site), Caddy (HTTPS), `pg_dump` 17 (les sauvegardes) ;
- ouvre les ports 80 et 443 du pare-feu de la machine (l'image Ubuntu d'Oracle bloque tout sauf SSH) ;
- installe les dépendances et construit le site (`npm run build:web`) ;
- pose les services systemd de `deploy/`, à son nom d'utilisateur et à son dossier :
  - `surprise.service` : le site, l'API et les emails des soirées (`python -m surprise.quiz --courriers`), relancé
    seul s'il s'arrête et au démarrage ;
  - `collecte.timer` : chaque nuit vers 4 h, la collecte de toutes les sources à `--limit 50` (jamais sans limite ;
    les pages encore fraîches ne sont pas relues), puis l'enrichissement (sans appel extérieur), les mots-clés, et les
    idées des sites de questions de couple (relues après 30 jours), à retoucher et publier sur `/admin/contenus` ;
  - `sauvegarde.timer` : chaque nuit vers 3 h, une copie de la base et des images (plus bas) ;
- écrit `/etc/caddy/Caddyfile` pour le domaine : Caddy obtient et renouvelle seul le certificat ;
- met la modération derrière un mot de passe : `/admin`, `/admin/contenus` et leur API (approuver une activité, publier
  un contenu du couple dans l'app) demandent l'utilisateur `moderation` et le mot de passe `MODERATION_PASSWORD` du
  `.env` du serveur. Sans lui, le script en tire un au hasard, l'écrit dans ce `.env` et l'affiche à la fin. Pour en
  choisir un autre : changer la ligne dans `~/surprise/.env`, puis relancer le script.

Le site est en ligne sur `https://secretdate.duckdns.org` une minute plus tard.

```bash
journalctl -u surprise -f                          # le journal du serveur ; Ctrl+C pour sortir
systemctl list-timers 'collecte*' 'sauvegarde*'    # les prochaines tâches de la nuit
sudo systemctl start collecte                      # une collecte tout de suite ; journal : journalctl -u collecte
```

## 7. Les réglages chez les services

- **Supabase** : Authentication → URL Configuration : **Site URL** = `https://secretdate.duckdns.org` ; dans
  **Redirect URLs**, l'ajouter, ainsi que `secretdate://**` pour l'app téléphone : les liens des emails de compte
  ramènent au site ou à l'app.
- **Brevo** (si c'est le relais) : autoriser l'IP publique de la machine, sinon les emails sont refusés. **AgentMail** :
  rien à faire. Oracle laisse sortir les ports 465 et 587 (c'est le 25 qu'il bloque).
- **Firebase** : rien à changer pour les pushes du site (il faut seulement le HTTPS, que Caddy donne).

Vérifier, sur la machine :

```bash
cd ~/surprise
~/.local/bin/uv run --env-file .env python -m surprise.courriers --dry-run    # ce qui partirait, sans rien envoyer
~/.local/bin/uv run --env-file .env python -m surprise.push vous@exemple.fr --dry-run
```

## 8. Mettre à jour après un `git push`

Depuis le PC :

```powershell
ssh -i $HOME\.ssh\oracle ubuntu@IP_PUBLIQUE sh surprise/deploy/deployer.sh
```

`deploy/deployer.sh` récupère le code, les dépendances, refait le site (quelques secondes si l'app n'a pas changé) et
relance le serveur. Un changement des fichiers de `deploy/` se repose en relançant `installer.sh`.

## 9. Les sauvegardes

Le plan gratuit de Supabase n'en garde **aucune**. `deploy/sauvegarde.sh` copie chaque nuit dans `~/sauvegardes` :

- la base (`pg_dump` des schémas `public` et `pipeline` : comptes, soirées, livres, collecte), `base-AAAA-MM-JJ.dump` ;
- les images des soirées gardées (`data/images`), `images-AAAA-MM-JJ.tar.gz` ;
- les 14 dernières restent.

Les photos du Livre sont dans Supabase Storage (bucket `souvenirs`), hors de cette copie : de temps en temps, les
télécharger depuis le tableau de bord de Supabase (Storage) si elles comptent.

Une copie hors de la machine, de temps en temps, depuis le PC :

```powershell
scp -i $HOME\.ssh\oracle -r ubuntu@IP_PUBLIQUE:sauvegardes .\sauvegardes
```

Ou une sauvegarde du disque entier dans la console Oracle (Block Storage → Boot Volumes → Backups, gratuites jusqu'à 5).
Reprendre la base depuis une copie (efface puis remet les tables de la copie) :

```bash
pg_restore --clean --if-exists --no-owner -d "$SUPABASE_DB_URL" ~/sauvegardes/base-2026-10-15.dump
```

## 10. Surveiller

Sur UptimeRobot ou Better Stack (gratuit), une sonde HTTP toutes les 5 minutes sur
`https://secretdate.duckdns.org/api/soiree` : un email si le site ne répond plus. Le serveur se relance seul
(systemd) ; s'il tombe quand même, `journalctl -u surprise -n 200` dit pourquoi.

## 11. Les limites du plan gratuit de Supabase

Vérifiées le 15 octobre 2026 sur <https://supabase.com/pricing> :

| Limite | Ce qui la remplit |
|---|---|
| 500 Mo de base | surtout `pipeline` : pages brutes de la collecte, candidats des soirées |
| 1 Go de fichiers | les photos du Livre |
| 5 Go de trafic par mois (+ 5 Go en cache) | les lectures de l'app (comptes, soirées) et du serveur |
| 50 000 utilisateurs actifs par mois | les comptes |
| Projet mis en pause après une semaine sans activité | le serveur lit la base toutes les dix minutes (emails) et y écrit chaque nuit (collecte) ; Supabase prévient par email avant une pause |
| Aucune sauvegarde | la copie de la nuit (étape 9) |

La taille de la base, dans l'éditeur SQL de Supabase : `select pg_size_pretty(pg_database_size('postgres'));`.
Pour la réduire : `python -m surprise.purge` (les activités passées, voir le README), qui compte d'abord et n'efface
qu'avec `--apply`.

## 12. L'app sur les téléphones

L'app se construit dans le cloud d'Expo, sans Android Studio ni Mac. Plan gratuit d'EAS, vérifié le 15 octobre 2026
sur <https://expo.dev/pricing> : jusqu'à 15 builds Android et 15 builds iOS, file d'attente lente (parfois plus d'une
heure aux heures chargées), envoi aux stores compris.

### Une fois

1. Un compte sur <https://expo.dev>.
2. Depuis `app/` :

   ```powershell
   npx eas-cli@latest login
   npx eas-cli@latest init
   ```

   `init` crée le projet chez Expo et donne son identifiant (`extra.eas.projectId`) : le mettre dans `app.json` s'il
   le demande (la config est dynamique, `app.config.js`).
3. Sur expo.dev, le projet → **Environment variables**, pour les environnements `preview` et `production` :
   - en texte visible (elles finissent dans l'app, publiques par nature) : `EXPO_PUBLIC_SUPABASE_URL`,
     `EXPO_PUBLIC_SUPABASE_ANON_KEY`, `EXPO_PUBLIC_FIREBASE_API_KEY`, `EXPO_PUBLIC_FIREBASE_PROJECT_ID`,
     `EXPO_PUBLIC_FIREBASE_SENDER_ID`, `EXPO_PUBLIC_FIREBASE_APP_ID` (les valeurs de `app/.env`) ;
   - en **fichier secret** : `GOOGLE_SERVICES_JSON`, le `google-services.json` de Firebase (les pushes Android ;
     `app.config.js` le prend de là).
4. L'adresse de l'API est dans `app/eas.json` (`EXPO_PUBLIC_API_URL`) : la changer si le domaine n'est pas
   `secretdate.duckdns.org`.
5. Les identifiants `fr.secretdate.app` (`app.json`) ne changent plus une fois l'app publiée : les confirmer avant.

### Android, gratuit : un APK à partager

```powershell
npx eas-cli@latest build --platform android --profile preview
```

À la fin, un lien et un QR code : on l'ouvre sur le téléphone, on autorise l'installation depuis cette source, c'est
installé. Le même lien se partage au passager ou à la bande. Rien à payer.

### Android sur le Play Store (25 $ une fois)

1. Un compte développeur sur <https://play.google.com/console> (25 $, vérification d'identité).
2. Le build pour le store (un `.aab`, version incrémentée seule) :

   ```powershell
   npx eas-cli@latest build --platform android --profile production
   npx eas-cli@latest submit --platform android --profile production
   ```

3. La fiche du store est prête dans `docs/store/` (textes, captures). Un compte personnel récent doit d'abord passer
   par un test fermé (une douzaine de testeurs pendant deux semaines, règle de Google) avant la production : les
   inviter avec le même lien.

### iPhone (99 $/an)

Il n'existe pas de façon gratuite de distribuer une app iPhone à d'autres que soi : TestFlight comme l'App Store
demandent l'Apple Developer Program (99 $/an). Une fois inscrit :

```powershell
npx eas-cli@latest build --platform ios --profile production
npx eas-cli@latest submit --platform ios --profile production
```

EAS crée les certificats, le groupe d'apps du widget (`group.fr.secretdate.app`) et envoie le build sur TestFlight.
D'ici là, les iPhone passent par le site, ajouté à l'écran d'accueil.

### Les mises à jour de l'app

Un changement de l'app demande un nouveau build (et, sur les stores, une nouvelle version). Pour pousser les
changements de JavaScript sans rebuild, EAS Update (gratuit jusqu'à 1 000 utilisateurs actifs par mois) demande
d'ajouter `expo-updates` à l'app : à faire le jour où les builds deviennent trop fréquents.

## 13. Les images : sur le serveur, ou dans Supabase Storage ?

Les images des soirées gardées sont copiées sur la machine (`data/images`) et servies par le serveur ; les autres
restent celles des sites. Les mettre dans Supabase Storage a été étudié le 15 octobre 2026, et écarté pour l'instant :

- **Ce que ça apporterait** : un serveur sans fichiers à garder (une machine perdue ou déménagée ne perd rien) et des
  images servies par le CDN de Supabase.
- **Pourquoi pas maintenant** :
  - le trafic de Supabase gratuit (5 Go par mois) est partagé avec toute l'app, alors que la machine Oracle en offre
    10 To ; ses 1 Go de fichiers sont mieux gardés pour les photos du Livre ;
  - ces images ne servent que jusqu'au jour de la soirée ; perdues, l'app reprend celle du site, ou à défaut sa
    propre image du genre de l'étape, jamais un blanc ;
  - la copie de la nuit (étape 9) les garde de toute façon.
- **Fait à la place** : chaque nouvelle copie est réduite à 1 200 px au plus en JPEG, sans différence visible sur un
  téléphone : les grandes photos pèsent 3 à 7 fois moins (1,2 Mo → 300 Ko), les 17 copies présentes le 15 octobre
  2026 seraient passées de 5,5 à 2,4 Mo. Le navigateur garde chaque copie un mois.

Supabase Storage redeviendrait intéressant si le site passait sur un hébergement sans disque (Vercel, Cloud Run…) :
seule `images.local_copy` serait à changer.
