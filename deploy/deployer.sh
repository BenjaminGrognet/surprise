#!/bin/sh
# Mettre le site à jour après un `git push`, depuis le PC (docs/deployer.md, étape 10) :
#   ssh -i $HOME\.ssh\oracle ubuntu@IP_PUBLIQUE sh surprise/deploy/deployer.sh
# Le site n'est reconstruit que si l'app a changé (quelques secondes sinon).
set -eu
cd "$(dirname "$0")/.."
git pull --ff-only
"$HOME/.local/bin/uv" sync
npm --prefix app install --no-audit --no-fund
npm --prefix app run build:web
sudo systemctl restart surprise
echo "À jour : $(git log -1 --format='%h %s' | cut -c1-100)"
