@echo off
rem Double-cliquer pour lancer le serveur et l'app Expo. Detail : docs\lancer-en-local.md
chcp 65001 >nul
cd /d "%~dp0"

if not exist .env (
  echo Il manque le fichier .env a la racine : voir docs\lancer-en-local.md, etape 0.
  pause
  exit /b 1
)
if not exist app\node_modules (
  echo Installation des dependances de l'app...
  call npm install --prefix app
)
set TEL=
set /p TEL=Aussi sur le telephone (Expo Go, meme Wi-Fi) ? o/N :
if /i not "%TEL%"=="o" goto web

set IP=
for /f %%i in ('powershell -NoProfile -Command "(Get-NetIPConfiguration | Where-Object IPv4DefaultGateway | Select-Object -First 1).IPv4Address.IPAddress"') do set IP=%%i
if not defined IP (
  echo Adresse IP du PC introuvable : lancement pour le navigateur seulement.
  goto web
)
rem Le site (http://127.0.0.1:8001) est le build web de l'app : refait d'abord s'il a change (quelques secondes), puis servi.
start "surprise - serveur" cmd /k "npm --prefix app run build:web && uv run --env-file .env python -m surprise.quiz --host 0.0.0.0 --no-open"
rem Expo ne remplace pas une variable deja definie par celle de app\.env : l'app vise le PC, pas localhost.
rem REACT_NATIVE_PACKAGER_HOSTNAME : le QR code porte l'IP du Wi-Fi, pas celle d'une carte virtuelle (Hyper-V, WSL).
start "surprise - app" /d app cmd /k "set EXPO_PUBLIC_API_URL=http://%IP%:8001&& set REACT_NATIVE_PACKAGER_HOSTNAME=%IP%&& npx expo start --web"
echo Le Wi-Fi doit etre un reseau "Prive" (Parametres ^> Reseau ^> Wi-Fi) : en "Public", le pare-feu bloque le telephone.
echo Scanner le QR code de la fenetre "surprise - app" (appareil photo sur iPhone, Expo Go sur Android).
echo Si Windows le demande, autoriser Python sur les reseaux prives.
goto fin

:web
rem Le site seul : son build (refait seulement s'il a change), puis le serveur, qui l'ouvre dans le navigateur une fois pret.
rem Pas de serveur Expo (8081) : il recompilait toute l'app a la premiere page, en meme temps que le build.
start "surprise - serveur" cmd /k "npm --prefix app run build:web && uv run --env-file .env python -m surprise.quiz"
echo Le site s'ouvre dans le navigateur des qu'il est pret (http://127.0.0.1:8001) : fermer la fenetre "surprise - serveur" pour l'arreter.
timeout /t 10
exit /b 0

:fin
echo Serveur (http://127.0.0.1:8001) et app lances dans deux fenetres : les fermer pour tout arreter.
timeout /t 10
