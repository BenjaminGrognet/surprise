#!/bin/sh
# Une copie de la base Supabase (le plan gratuit n'en garde aucune) et des images des soirées gardées, chaque nuit
# dans ~/sauvegardes ; les 14 dernières restent. Lancée par sauvegarde.timer (docs/deployer.md).
# Reprendre une copie : pg_restore --clean --if-exists --no-owner -d "$SUPABASE_DB_URL" base-AAAA-MM-JJ.dump
set -eu
cd "$(dirname "$0")/.."
# SUPABASE_DB_URL, lue dans .env sans exécuter le fichier.
SUPABASE_DB_URL=$(sed -n 's/^SUPABASE_DB_URL=//p' .env | tr -d "\"'" | tail -n 1)
[ -n "$SUPABASE_DB_URL" ] || { echo "SUPABASE_DB_URL absente de .env" >&2; exit 1; }
DESTINATION="$HOME/sauvegardes"
JOUR=$(date +%F)
mkdir -p "$DESTINATION"
# public (comptes, soirées, livres) et pipeline (collecte, parcours) ; ni les schémas internes de Supabase.
pg_dump --format=custom --no-owner --no-privileges --schema=public --schema=pipeline \
  --file="$DESTINATION/base-$JOUR.dump" "$SUPABASE_DB_URL"
[ -d data/images ] && tar -czf "$DESTINATION/images-$JOUR.tar.gz" -C data images
ls -1t "$DESTINATION"/base-*.dump 2>/dev/null | tail -n +15 | xargs -r rm --
ls -1t "$DESTINATION"/images-*.tar.gz 2>/dev/null | tail -n +15 | xargs -r rm --
echo "Sauvegarde du $JOUR : $(du -sh "$DESTINATION" | cut -f1) en tout dans $DESTINATION"
