# Deploy su Railway — Campera Offroad Service

Obiettivo: portare online l'API (FastAPI + PostGIS) con un URL pubblico HTTPS che
Campera Trail Planner potrà chiamare. Primo deploy con i **dati pilota** (veloce);
l'import completo Piemonte+Liguria è la fase di scala (in fondo).

## 0. Prerequisito — codice su GitHub

Railway fa il deploy da un repo GitHub. Dalla cartella `campera-offroad-service/`:

```bash
git init
git add .
git commit -m "Campera Offroad Service"
git branch -M main
git remote add origin https://github.com/<tuo-utente>/campera-offroad-service.git
git push -u origin main
```

(Crea prima il repo vuoto su github.com, poi incolla l'URL sopra.)

## 1. Progetto Railway + database PostGIS

1. Railway → **New Project** → **Deploy from GitHub repo** → seleziona `campera-offroad-service`.
2. Nel servizio creato: **Settings → Root Directory** = `app` (così builda `app/Dockerfile`).
3. **New** (nel progetto) → **Docker Image** → immagine `postgis/postgis:16-3.4`. Chiamalo **db**.
   - **Variables** del servizio db:
     - `POSTGRES_USER=campera`
     - `POSTGRES_PASSWORD=` (genera una password forte)
     - `POSTGRES_DB=campera_offroad`
   - **Settings → Volumes**: aggiungi un volume montato su `/var/lib/postgresql/data`.

> Nota: il PostgreSQL "managed" di Railway non ha PostGIS — per questo usiamo
> l'immagine `postgis/postgis` come servizio con volume.

## 2. Variabili del servizio API

Nel servizio **api** → Variables:

- `API_KEY` = (genera una chiave; servirà a Trail Planner nell'header `X-API-Key`)
- `DATABASE_URL` = `postgresql://campera:<PASSWORD>@db.railway.internal:5432/campera_offroad`

(`db.railway.internal` è l'hostname privato del servizio db dentro Railway.)

## 3. Schema + dati pilota (seed)

Dal tuo PC, usando l'URL **pubblico** del db (Railway → servizio db → **Connect** →
"Public Network" / TCP proxy):

```bash
pip install "psycopg[binary]" --break-system-packages
export DATABASE_URL="postgresql://campera:<PASSWORD>@<host-pubblico>:<porta>/campera_offroad"
python3 scripts/load_geojson_to_pg.py data/pilot_appennino_ligure.geojson
```

Lo script crea l'estensione PostGIS, la tabella e carica i tratti. (Ripetibile.)

## 4. Dominio pubblico + test

1. Servizio **api** → **Settings → Networking → Generate Domain** → ottieni
   `https://<qualcosa>.up.railway.app`.
2. Test:

```bash
curl -H "X-API-Key: <API_KEY>" \
 "https://<qualcosa>.up.railway.app/v1/segments?bbox=8.80,44.55,9.15,44.72&vehicle=van"
curl "https://<qualcosa>.up.railway.app/health"
```

## 5. Collega Campera Trail Planner

In Trail Planner (Base44) crea una **backend function** che chiama l'API mettendo
la chiave nell'header `X-API-Key` (la chiave resta lato server, non nel browser).
La function gira `GET /v1/segments?bbox=...` e restituisce il GeoJSON alla mappa.

## 6. Fase di scala — import completo Piemonte + Liguria

L'import `osm2pgsql` dell'intero Nord-Ovest è pesante (GB + RAM): conviene
eseguirlo una volta verso il DB (host pubblico) da una macchina con risorse, poi
Railway serve i dati. Vedi `import/import_osm.sh` e `.env.example` (BBOX già
impostato su Piemonte+Liguria; per il ritaglio esatto usa un poligono dei confini
regionali con `osmium extract -p`).

## Costi indicativi

API + db + volume su Railway: ordine di pochi €/mese in base a uso e RAM del db.
