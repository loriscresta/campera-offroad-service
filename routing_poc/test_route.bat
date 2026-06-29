@echo off
chcp 65001 >nul
setlocal
set "BASE=https://campera-offroad-service-production.up.railway.app"
set "DIR=%~dp0"
set "LOG=%DIR%route_test_result.txt"

echo ============================================================
echo  Campera - test percorso live (camper + jeep)
echo ============================================================
echo.
set "APIKEY="
set /p "APIKEY=Incolla la API key del servizio e premi Invio: "
if "%APIKEY%"=="" ( echo Annullato. & pause & exit /b 1 )

rem --- corpi richiesta (stessi A/B del POC) ---
> "%DIR%_camper.json" echo {"start":[8.294519,44.357628],"end":[8.684182,44.612588],"vehicle":"van","format":"json"}
> "%DIR%_jeep.json"   echo {"start":[8.294519,44.357628],"end":[8.684182,44.612588],"vehicle":"camper_4x4","format":"json"}
> "%DIR%_camper_gpx.json" echo {"start":[8.294519,44.357628],"end":[8.684182,44.612588],"vehicle":"van","format":"gpx"}
> "%DIR%_jeep_gpx.json"   echo {"start":[8.294519,44.357628],"end":[8.684182,44.612588],"vehicle":"camper_4x4","format":"gpx"}

echo Richiesta percorsi in corso...
echo === CAMPER (json) === > "%LOG%"
curl -sS --ssl-no-revoke -X POST "%BASE%/v1/route" -H "X-API-Key: %APIKEY%" -H "Content-Type: application/json" --data "@%DIR%_camper.json" -w "\nHTTP=%%{http_code}\n" >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo === JEEP (json) === >> "%LOG%"
curl -sS --ssl-no-revoke -X POST "%BASE%/v1/route" -H "X-API-Key: %APIKEY%" -H "Content-Type: application/json" --data "@%DIR%_jeep.json" -w "\nHTTP=%%{http_code}\n" >> "%LOG%" 2>&1

curl -sS --ssl-no-revoke -X POST "%BASE%/v1/route" -H "X-API-Key: %APIKEY%" -H "Content-Type: application/json" --data "@%DIR%_camper_gpx.json" -o "%DIR%campera_camper_live.gpx"
curl -sS --ssl-no-revoke -X POST "%BASE%/v1/route" -H "X-API-Key: %APIKEY%" -H "Content-Type: application/json" --data "@%DIR%_jeep_gpx.json" -o "%DIR%campera_jeep_live.gpx"

del "%DIR%_camper.json" "%DIR%_jeep.json" "%DIR%_camper_gpx.json" "%DIR%_jeep_gpx.json" >nul 2>&1
echo.
echo ------------------------------------------------------------
type "%LOG%"
echo ------------------------------------------------------------
echo  GPX salvati: campera_camper_live.gpx / campera_jeep_live.gpx
echo  Scrivi "fatto" in chat: leggo io il risultato.
echo ============================================================
set "APIKEY="
pause
