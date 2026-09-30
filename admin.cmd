@echo off
rem Double-cliquer pour ouvrir la moderation (http://127.0.0.1:8000/admin). Fermer la fenetre pour l'arreter.
chcp 65001 >nul
cd /d "%~dp0"

if not exist .env (
  echo Il manque le fichier .env a la racine : voir docs\lancer-en-local.md, etape 0.
  pause
  exit /b 1
)
uv run --env-file .env python -m surprise.admin
pause
