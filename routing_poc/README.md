# routing_poc — Proof of Concept routing percorsi (NON in produzione)

Cartella isolata: **non** referenziata da Railway (i servizi buildano da `app/` e
`importer/`), quindi non tocca l'infrastruttura live anche se finisce su GitHub.

## Step 1 — topologia rete offroad area Sassello (SV), 30x30 km
- `sassello_step1.py` — pull Overpass (stessa query dell'importer) → noding
  geometrico → grafo → connettività → test Dijkstra A→B → GPX/mappa.
- `sassello_map.html` — mappa: verde = componente connessa più grande,
  grigio = frammenti scollegati, rosso = test percorso A→B.
- `sassello_test_route.gpx` — percorso di test (offroad puro, 20.9 km).
- `sassello_summary.json` — numeri della run.

### Esito Step 1
Rete offroad da sola = molto frammentata (1617 componenti, la più grande 9.5%).
Atteso: i tratti sono "isole" collegate dalle strade asfaltate, non ancora nel
grafo. Lo Step 2 aggiunge le strade OSM e rimisura la connettività.

## Step 3 — pendenza + profili veicolo (camper vs jeep 4x4)
- `build_graph3.py` — grafo unificato (offroad + strade a tessere) -> `graph3.pkl`.
- quote per nodo via opentopodata eudem25m (25 m).
- `route_profiles3.py` / `build_step3_outputs.py` — pendenza per arco, due cost
  model (camper evita ripido/solo_4x4; jeep cerca tecnico, evita asfalto),
  stesso A->B -> due percorsi diversi.
- `sassello_map_step3.html` — mappa confronto + tabella + profilo altimetrico.
- `sassello_camper.gpx`, `sassello_jeep.gpx` — i due percorsi.

### Esito Step 3 (A->B identici)
- camper: 74 km, 10% sterrato, dislivello +1706 m, max 22%.
- jeep 4x4: 81 km, 87% sterrato (11.7 km solo_4x4), dislivello +3233 m.
- divergenza percorsi ~96%: stessa partenza/arrivo, due itinerari opposti.
Nota: pendenza da quota nodi a 25 m; in produzione Tinitaly 10 m + per-vertice.

## Step 4 — endpoint /v1/route (pilota, NON deployato)
- `app/routing.py` — motore Dijkstra in PURO stdlib (nessuna nuova dipendenza).
  Carica `routing_poc/sassello_graph.json` (gitignored, locale).
- `app/main.py` — lo stub `/v1/route` ora e implementato: input
  {start,end,waypoints,vehicle,format}, output GPX o GeoJSON + riepilogo.
- Sicurezza deploy: il grafo NON e nel repo (gitignore). Finche non viene
  spedito a Railway, l'endpoint risponde 501 e il servizio live resta invariato.

### Test (locale, TestClient) — tutti OK
- senza X-API-Key -> 401
- vehicle=van  -> camper: 74.2 km, 10% sterrato
- vehicle=camper_4x4 -> jeep: 81.3 km, 87% sterrato, GPX 6531 punti
- con waypoint intermedio -> 75.4 km

### Esempio chiamata
POST /v1/route   header: X-API-Key: <key>
{"start":[8.45,44.40],"end":[8.62,44.50],"waypoints":[],"vehicle":"camper_4x4","format":"gpx"}
