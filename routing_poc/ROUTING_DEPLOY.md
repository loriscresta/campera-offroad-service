# Deploy del routing pilota (Sassello) — guida

Strategia: **grafo pre-costruito caricato una volta su un volume Railway**, poi
letto dal volume all'avvio. Deploy leggero (il grafo NON e in git), servizio
puro-stdlib (niente shapely/networkx a runtime), stabile (dopo il primo upload
non serve rete).

Finche il grafo non e caricato, `/v1/route` risponde **501**: il servizio live e
Trail Planner restano invariati. Attivazione graduale e senza rischi.

## Passi (una volta sola)

1. **Volume sul servizio API**
   Railway → progetto `lavish-integrity` → servizio **api** → Settings → Volumes
   → aggiungi un volume montato su `/data`.

2. **Variabile d'ambiente**
   Servizio **api** → Variables → aggiungi:
   `ROUTING_GRAPH = /data/sassello_graph.json`

3. **Push del codice** (porta online `routing.py` e i nuovi endpoint)
   Doppio clic su `push_to_github.bat`. Railway rideploya in ~2 min.
   (Senza il grafo, `/v1/route` resta 501 — nessun impatto sul resto.)

4. **Carica il grafo sul volume** (dal tuo PC)
   ```
   python3 routing_poc/upload_graph.py https://<api>.up.railway.app <API_KEY>
   ```
   Invia `sassello_graph.json` (~7 MB → ~1.8 MB gzip) a
   `POST /v1/admin/load-graph`. Risposta attesa: `{"loaded": true, ...}`.

5. **Verifica**
   ```
   curl -H "X-API-Key: <KEY>" https://<api>.up.railway.app/v1/route/status
   ```
   Deve dare `"active": true` con l'area Sassello.

## Uso dell'endpoint

```
POST /v1/route          header: X-API-Key: <KEY>
{
  "start": [8.45, 44.40],
  "end":   [8.62, 44.50],
  "waypoints": [[8.50, 44.45]],
  "vehicle": "camper_4x4",     // van | camper_4x4
  "format":  "gpx"             // gpx | json
}
```
- `gpx` → file da mettere su Wikiloc/Garmin.
- `json` → riepilogo (distanza, % sterrato, dislivello, max pendenza) + geometria.

## Rigenerare / aggiornare il grafo
Offline: `routing_poc/build_routing_graph.py` (da `graph3.pkl` + quote) →
`sassello_graph.json` → ri-carica con `upload_graph.py`. Per altre aree si
ripete il flusso Step 1-3 e si carica un nuovo grafo regionale.
