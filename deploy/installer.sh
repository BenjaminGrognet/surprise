#!/bin/bash
# Tout installer sur une machine Ubuntu neuve (Oracle Cloud « Always Free » : docs/deployer.md, étape 6), une fois le
# code cloné et les deux .env copiés. Se relance sans risque (ce qui est déjà là est gardé ou remis à jour).
#   bash ~/surprise/deploy/installer.sh secretdate.duckdns.org
set -euo pipefail

DOMAINE=${1:?"Usage : bash deploy/installer.sh mon-domaine.duckdns.org"}
DOSSIER=$(cd "$(dirname "$0")/.." && pwd)
UTILISATEUR=$(id -un)
cd "$DOSSIER"
[ -f .env ] || { echo "Il manque $DOSSIER/.env : le copier d'abord depuis le PC (docs/deployer.md, étape 5)." >&2; exit 1; }
[ -f app/.env ] || { echo "Il manque $DOSSIER/app/.env : le copier d'abord depuis le PC." >&2; exit 1; }

echo "== Paquets du système"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get -y upgrade
sudo DEBIAN_FRONTEND=noninteractive apt-get -y install git curl ca-certificates gnupg debian-keyring debian-archive-keyring \
  apt-transport-https iptables-persistent postgresql-common

echo "== Node 22 (le build web de l'app)"
if ! command -v node >/dev/null || [ "$(node -v | cut -d. -f1)" != "v22" ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get -y install nodejs
fi

echo "== Caddy (HTTPS automatique)"
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update
  sudo apt-get -y install caddy
fi

echo "== pg_dump 17 (les sauvegardes ; Supabase est en Postgres 17)"
if ! command -v pg_dump >/dev/null || ! pg_dump --version | grep -q " 17\."; then
  sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
  sudo apt-get -y install postgresql-client-17
fi

echo "== uv (Python)"
if [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
UV="$HOME/.local/bin/uv"

echo "== Pare-feu de la machine : ports 80 et 443"
for PORT in 80 443; do
  sudo iptables -C INPUT -m state --state NEW -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null \
    || sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport "$PORT" -j ACCEPT
done
sudo netfilter-persistent save

echo "== Le code : dépendances et build du site"
"$UV" sync
npm --prefix app ci
npm --prefix app run build:web

echo "== Les services : le site, la collecte de la nuit, la sauvegarde"
for UNITE in surprise.service collecte.service collecte.timer sauvegarde.service sauvegarde.timer; do
  sed -e "s|__UTILISATEUR__|$UTILISATEUR|g" -e "s|__DOSSIER__|$DOSSIER|g" "deploy/$UNITE" | sudo tee "/etc/systemd/system/$UNITE" >/dev/null
done
sed "s|__DOMAINE__|$DOMAINE|g" deploy/Caddyfile | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now surprise.service collecte.timer sauvegarde.timer
sudo systemctl restart surprise.service
sudo systemctl reload caddy

echo
echo "Fini. Le site : https://$DOMAINE (le certificat arrive en une minute)."
echo "Journal du serveur : journalctl -u surprise -f ; prochaines tâches : systemctl list-timers 'collecte*' 'sauvegarde*'"
