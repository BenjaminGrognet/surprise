@echo off
rem Double-cliquer pour collecter toutes les sources (200 fiches au plus chacune), puis enrichir.
rem Detail : docs\lancer-en-local.md
chcp 65001 >nul
cd /d "%~dp0"

if not exist .env (
  echo Il manque le fichier .env a la racine : voir docs\lancer-en-local.md, etape 0.
  pause
  exit /b 1
)

set SRC=
set /p SRC=Source (Entree = toutes, ex. fever) :
if defined SRC (
  uv run --env-file .env python -m surprise.collect --source %SRC% --limit 200
  uv run --env-file .env python -m surprise.enrich --source %SRC%
) else (
  uv run --env-file .env python -m surprise.collect --limit 200
  uv run --env-file .env python -m surprise.enrich
)
uv run --env-file .env python -m surprise.keywords
echo Collecte terminee.
pause
