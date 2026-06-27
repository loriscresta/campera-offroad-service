@echo off
REM Carica il microservizio su GitHub. Fai doppio clic su questo file.
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
  echo.
  echo [!] Git non e' installato su questo PC.
  echo     Scaricalo da https://git-scm.com/download/win  oppure usa GitHub Desktop.
  echo.
  pause
  exit /b 1
)

git init
git add .
git commit -m "Campera Offroad Service"
git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/loriscresta/campera-offroad-service.git
git push -u origin main

echo.
echo ============================================================
echo  Se vedi "Writing objects" e nessun errore: FATTO.
echo  Se compare una finestra di login GitHub, accedi e riprova.
echo  Se vedi errori, copiali e mandameli in chat.
echo ============================================================
pause
