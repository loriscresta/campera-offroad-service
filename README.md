# Campera Offroad Service

Microservizio **indipendente** che rileva strade bianche e percorsi offroad da
OpenStreetMap, li classifica per difficoltà e idoneità mezzo (van / camper 4x4)
e li serve via API REST.

- Front-end di appoggio: **Campera Trail Planner** (Base44) — consuma questo
  servizio senza toccare la Campera di produzione.
- Zona pilota: **Appennino ligure-piemontese** (entroterra genovese, Valle
  Scrivia, Val Borbera, Ovadese/Novese), estendibile a tutto il Nord-Ovest e poi
  all'Italia.

## Architettura

```
Campera Trail Planner (Base44)
        │  HTTPS + X-API-Key
        ▼
 FastAPI  ──►  PostGIS (rete offroad classificata)  ◄── import OSM (Geofabrik)
        └──►  [fase 2] GraphHopper (routing van / 4x4)
```

## Componenti

| Cartella | Contenuto |
|---|---|
| `app/` | API FastAPI: `/segments`, `/segment/{id}`, `/route` (stub fase 2) |
| `db/` | Schema PostGIS + regole di classificazione difficoltà |
| `import/` | Download estratto Geofabrik + clip bbox + import `osm2pgsql` |
| `scripts/` | `seed_overpass.py`: estrazione rapida via Overpass (validazione/seed) |
| `data/` | Output GeoJSON (es. `pilot_appennino_ligure.geojson`) |

## Avvio rapido (sulla tua macchina o VPS)

Richiede Docker.

```bash
cp .env.example .env          # imposta API_KEY e BBOX
docker compose up -d db       # avvia PostGIS
./import/import_osm.sh        # scarica, clippa e importa la zona (una volta)
docker compose up -d api      # avvia l'API su :8000
```

Verifica:

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/v1/segments?bbox=8.80,44.55,9.15,44.72&vehicle=van&max_difficulty=medio"
```

## Validazione senza Docker (subito)

Lo script Overpass non richiede database e produce un GeoJSON reale della zona
pilota:

```bash
python3 scripts/seed_overpass.py
# -> data/pilot_appennino_ligure.geojson
```

## Modello di difficoltà

| Livello | Regola (sintesi) | Mezzi |
|---|---|---|
| `facile` | fondo compatto, `tracktype=grade1` | van, camper_4x4 |
| `medio` | `tracktype=grade2` o `surface=gravel/fine_gravel` | van, camper_4x4 |
| `impegnativo` | `tracktype=grade3` o `surface=dirt/ground/earth` | van, camper_4x4 |
| `solo_4x4` | `4wd_only=yes` o `tracktype=grade4/5` o `smoothness` molto bassa | camper_4x4 |

Ogni tratto ha anche `confidence` (alta/media/bassa) in base ai tag OSM presenti.
Su `confidence=bassa` viene mostrato un avviso "verifica condizioni locali".

## Stato

- [x] Data layer: schema, classificazione, API `/segments` e `/segment/{id}`
- [x] Seed/validazione via Overpass (zona pilota)
- [ ] Routing van/4x4 (fase 2 — GraphHopper)
- [ ] Integrazione Campera Trail Planner (entità + backend function)
