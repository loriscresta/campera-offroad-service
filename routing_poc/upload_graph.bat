@echo off
chcp 65001 >nul
setlocal
set "BASE=https://campera-offroad-service-production.up.railway.app"
set "GRAPH=%~dp0sassello_graph.json"
set "LOG=%~dp0upload_result.txt"

echo ============================================================
echo  Campera - upload grafo routing sul microservizio
echo ============================================================
echo.
if not exist "%GRAPH%" (
  echo ERRORE: non trovo sassello_graph.json in questa cartella.
  echo Atteso in: %GRAPH%
  pause
  exit /b 1
)

set "APIKEY="
set /p "APIKEY=Incolla qui la API key del servizio (resta sul tuo PC) e premi Invio: "
if "%APIKEY%"=="" (
  echo Nessuna chiave inserita. Annullato.
  pause
  exit /b 1
)

echo Upload in corso (file ~7 MB)... attendere.
echo === UPLOAD === > "%LOG%"
curl -sS --ssl-no-revoke -X POST "%BASE%/v1/admin/load-graph" -H "X-API-Key: %APIKEY%" --data-binary "@%GRAPH%" -w "\nHTTP_UPLOAD=%%{http_code}\n" >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo === STATUS === >> "%LOG%"
curl -sS --ssl-no-revoke "%BASE%/v1/route/status" -H "X-API-Key: %APIKEY%" -w "\nHTTP_STATUS=%%{http_code}\n" >> "%LOG%" 2>&1

echo.
echo ------------------------------------------------------------
type "%LOG%"
echo ------------------------------------------------------------
echo  Risultato salvato in: upload_result.txt
echo  (non contiene la chiave). Dimmi in chat che hai finito,
echo  oppure incolla queste righe.
echo ============================================================
set "APIKEY="
pause
