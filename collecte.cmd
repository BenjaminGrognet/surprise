@echo off
rem Double-cliquer pour collecter toutes les sources (limite par source demandee), puis enrichir.
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
set LIMIT=
set /p LIMIT=Limite par source (Entree = 200) :
if not defined LIMIT set LIMIT=200

if defined SRC (
  uv run --env-file .env python -m surprise.collect --source %SRC% --limit %LIMIT%
  uv run --env-file .env python -m surprise.enrich --source %SRC%
) else (
  uv run --env-file .env python -m surprise.collect --limit %LIMIT%
  uv run --env-file .env python -m surprise.enrich
)
uv run --env-file .env python -m surprise.keywords
echo Collecte terminee.
pause
