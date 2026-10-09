# Mettre le site en ligne sur Oracle Cloud (gratuit)

Une machine Linux « Always Free » d'Oracle, toujours allumée, fait tourner le même serveur qu'en local
(`python -m surprise.quiz`, qui sert le site et l'API), avec les emails programmés (`--courriers`). Caddy, devant,
s'occupe du HTTPS. La base reste sur Supabase, les emails sur Brevo.

Compter une heure la première fois. Les commandes `bash` se tapent sur la machine (après `ssh`), les commandes
PowerShell sur le PC.

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
| Shape | Ampere **VM.Standard.A1.Flex**, 2 OCPU, 12 Go (gratuit jusqu'à 4 OCPU et 24 Go en tout) |
| Networking | réseau créé par défaut, **Assign a public IPv4 address** coché |
| SSH keys | « Paste public keys » : le contenu de `oracle.pub` |
| Boot volume | 50 Go (par défaut ; gratuit jusqu'à 200 Go) |

Une fois « Running », noter l'**adresse IP publique**. Pour qu'elle ne change jamais : Instance → Attached VNICs →
la VNIC → IPv4 Addresses → modifier → **Reserved public IP**.

## 4. Ouvrir le web (ports 80 et 443)

Deux pare-feu à ouvrir.

**Chez Oracle** : Instance → la Subnet → Security Lists → Default Security List → **Add Ingress Rules** :
source `0.0.0.0/0`, protocole TCP, port de destination `80`. Puis une deuxième règle identique pour `443`.

**Sur la machine** (l'image Ubuntu d'Oracle bloque tout sauf SSH) :

```powershell
ssh -i $HOME\.ssh\oracle ubuntu@IP_PUBLIQUE
```

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 5. Une adresse (nom de domaine)

Le HTTPS demande un nom. Gratuit : <https://www.duckdns.org>, connexion avec GitHub ou Google, créer par exemple
`secretdate` → `secretdate.duckdns.org`, et y mettre l'IP publique. Avec un vrai domaine, créer un enregistrement
`A` vers l'IP.

## 6. Les outils

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install git curl ca-certificates

# Python par uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Node 22 (pour construire le site Expo)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt -y install nodejs

# Caddy (HTTPS automatique)
sudo apt -y install debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt -y install caddy
```

## 7. Le code

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

## 8. Les secrets

Ils ne sont pas dans Git. Depuis le PC, dans PowerShell, à la racine du projet :

```powershell
scp -i $HOME\.ssh\oracle .env ubuntu@IP_PUBLIQUE:~/surprise/.env
scp -i $HOME\.ssh\oracle app\.env ubuntu@IP_PUBLIQUE:~/surprise/app/.env
```

Puis sur la machine, `nano ~/surprise/.env`, et changer :

```
APP_URL="https://secretdate.duckdns.org"
```

(`EXPO_PUBLIC_API_URL` ne compte pas pour le site : en ligne, il appelle l'API à sa propre adresse.)

Ailleurs, à ne pas oublier :

- **Brevo** : autoriser l'IP publique de la machine (comme pour le PC), sinon les emails sont refusés.
- **Supabase** : Authentication → URL Configuration : **Site URL** = `https://secretdate.duckdns.org`, et
  l'ajouter aux **Redirect URLs**, pour que les liens des emails de compte ramènent au site en ligne.

## 9. Construire le site

```bash
cd ~/surprise
uv sync
npm --prefix app install
npm --prefix app run build:web
```

## 10. Le serveur, relancé tout seul

```bash
sudo tee /etc/systemd/system/surprise.service > /dev/null <<'EOF'
[Unit]
Description=Secret Date (site, API et emails)
After=network-online.target
Wants=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/surprise
ExecStart=/home/ubuntu/.local/bin/uv run --env-file .env python -m surprise.quiz --host 127.0.0.1 --port 8001 --no-open --courriers
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now surprise
journalctl -u surprise -f   # les journaux ; Ctrl+C pour sortir
```

## 11. Le HTTPS

```bash
sudo tee /etc/caddy/Caddyfile > /dev/null <<'EOF'
secretdate.duckdns.org {
	encode gzip
	reverse_proxy 127.0.0.1:8001
}
EOF
sudo systemctl reload caddy
```

Caddy obtient et renouvelle seul le certificat. Le site est en ligne sur `https://secretdate.duckdns.org`.

## 12. Mettre à jour après un `git push`

Une fois pour toutes :

```bash
cat > ~/deployer.sh <<'EOF'
#!/bin/sh
set -e
cd ~/surprise
git pull --ff-only
uv sync
npm --prefix app install
npm --prefix app run build:web
sudo systemctl restart surprise
EOF
chmod +x ~/deployer.sh
```

Puis, à chaque mise à jour, depuis le PC :

```powershell
ssh -i $HOME\.ssh\oracle ubuntu@IP_PUBLIQUE ./deployer.sh
```

Le site n'est reconstruit que si l'app a changé (quelques secondes sinon).

## Et ensuite

- Les photos gardées avec les soirées (`data/images`) restent sur le disque de la machine : le sauvegarder de
  temps en temps (`scp -r`), ou une sauvegarde du volume dans la console Oracle (Block Storage → Backups, gratuites
  jusqu'à 5).
- Ubuntu installe seul ses mises à jour de sécurité. La connexion SSH n'accepte que la clé.
- L'app téléphone (Expo) : mettre `EXPO_PUBLIC_API_URL=https://secretdate.duckdns.org` dans `app/.env` pour ses
  builds.
