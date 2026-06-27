# Import completo Piemonte + Liguria — Piano

Obiettivo: caricare nel PostGIS live tutta la rete offroad (strade bianche,
sterrati, tracce, ex-militari) di Piemonte e Liguria, oltre alla zona pilota.

## Approccio

Per il **data layer** serve solo la rete OFFROAD (non l'intera rete stradale,
che servirà al routing in fase 2). Quindi NON usiamo l'import pesante
`osm2pgsql`, ma un'estrazione **a tessere via Overpass**: più leggera, sta sul
nostro stesso schema e si carica direttamente in PostGIS.

Script pronto: `scripts/import_region_to_pg.py` (e copia in `importer/` per il job
cloud). Divide il bbox in celle, interroga Overpass cella per cella, classifica
(Facile/Medio/Impegnativo/Solo 4x4) e fa UPSERT idempotente in `offroad_segments`.

## Stima volume (validata)

- Test reale su 2 tessere nel Cuneese (0.2°): **5.001 tratti** (~2.500/tessera in
  zona alpina densa).
- Regione bbox 6.60,43.75 → 10.15,46.50 con celle da 0.2°: ~**252 tessere**.
- Stima totale Piemonte+Liguria: **~150.000–250.000 tratti** offroad.
- Durata come job una tantum: ~**30–60 minuti** (query + pause + insert).

## Opzioni di esecuzione

### Opzione A — Job su Railway (consigliata: DB resta privato)
1. Porta su GitHub la cartella `importer/` (doppio clic su `push_to_github.bat`).
2. Su Railway → progetto **lavish-integrity** → Add → GitHub Repo → stesso repo,
   **Root Directory = `importer`**.
3. Variabili del nuovo servizio:
   - `DATABASE_URL = postgresql://campera:<password>@postgis.railway.internal:5432/campera_offroad`
   - `REGION_BBOX = 6.60,43.75,10.15,46.50`  (opzionale; default già questo)
   - `TILE_DEG = 0.2`, `SLEEP_SEC = 2`
4. Deploy: il job gira una volta, popola il DB e termina. Poi si può rimuovere.

### Opzione B — Esecuzione diretta verso il DB (TCP proxy)
1. Su Railway, servizio **postgis** → Settings → Networking → TCP Proxy (espone
   un host:porta pubblico temporaneo).
2. In locale o da ambiente con Python:
   ```
   pip install "psycopg[binary]" --break-system-packages
   export DATABASE_URL="postgresql://campera:<password>@<host-proxy>:<porta>/campera_offroad"
   python3 scripts/import_region_to_pg.py
   ```
3. A fine import, rimuovere il TCP Proxy (richiudere l'accesso pubblico).

## Note

- **Spillover bbox**: il riquadro include lembi di Francia/Lombardia/Valle
  d'Aosta/mare. Sono tratti offroad in più, innocui. Per limitare ESATTAMENTE ai
  confini regionali si può fare una pulizia successiva con i poligoni ISTAT.
- **Idempotente**: lo script usa `ON CONFLICT DO NOTHING`, quindi è ri-eseguibile
  e ripartibile senza duplicati.
- **Aggiornamenti**: rilanciare il job periodicamente (es. mensile) per recepire
  le novità OSM.
- **Routing (fase 2)**: per i percorsi A→B servirà comunque la rete completa
  (GraphHopper sull'estratto Geofabrik); questo import copre il data layer.
