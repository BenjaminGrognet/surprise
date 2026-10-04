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
rem Le site (http://127.0.0.1:8001) est le build web de l'app : refait a chaque lancement, en arriere-plan.
start "surprise - site" /min cmd /c npm --prefix app run build:web

set TEL=
set /p TEL=Aussi sur le telephone (Expo Go, meme Wi-Fi) ? o/N :
if /i not "%TEL%"=="o" goto web

set IP=
for /f %%i in ('powershell -NoProfile -Command "(Get-NetIPConfiguration | Where-Object IPv4DefaultGateway | Select-Object -First 1).IPv4Address.IPAddress"') do set IP=%%i
if not defined IP (
  echo Adresse IP du PC introuvable : lancement pour le navigateur seulement.
  goto web
)
start "surprise - serveur" cmd /k uv run --env-file .env python -m surprise.quiz --host 0.0.0.0 --no-open
rem Expo ne remplace pas une variable deja definie par celle de app\.env : l'app vise le PC, pas localhost.
rem REACT_NATIVE_PACKAGER_HOSTNAME : le QR code porte l'IP du Wi-Fi, pas celle d'une carte virtuelle (Hyper-V, WSL).
start "surprise - app" /d app cmd /k "set EXPO_PUBLIC_API_URL=http://%IP%:8001&& set REACT_NATIVE_PACKAGER_HOSTNAME=%IP%&& npx expo start --web"
echo Le Wi-Fi doit etre un reseau "Prive" (Parametres ^> Reseau ^> Wi-Fi) : en "Public", le pare-feu bloque le telephone.
echo Scanner le QR code de la fenetre "surprise - app" (appareil photo sur iPhone, Expo Go sur Android).
echo Si Windows le demande, autoriser Python sur les reseaux prives.
goto fin

:web
start "surprise - serveur" cmd /k uv run --env-file .env python -m surprise.quiz --no-open
start "surprise - app" /d app cmd /k npm run web

:fin
echo Serveur (http://127.0.0.1:8001) et app lances dans deux fenetres : les fermer pour tout arreter.
timeout /t 10
