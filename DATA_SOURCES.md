# Campera Offroad — Fonti dati (Piemonte + Liguria)

Sintesi della ricerca sulle fonti per strade bianche, sterrati, strade forestali
e militari, e itinerari offroad in Piemonte e Liguria. Aggiornato: giugno 2026.

## Sintesi operativa

- **Buona notizia licenze:** sia il Geoportale Piemonte sia quello Liguria pubblicano in **CC-BY 4.0** → uso anche **commerciale**, basta citare la fonte. OSM è **ODbL** (attribuzione + condivisione del database derivato).
- **OSM è la spina dorsale:** copre l'intera rete (necessaria per il routing), le tracce, `tracktype`/`4wd_only` e gli itinerari nominati (Via del Sale, ex-strade militari ci sono già).
- **I dati regionali servono per l'autorità e gli accessi:** strade forestali/silvo-pastorali ufficiali e reti escursionistiche validate, che OSM non garantisce.

## 1. OpenStreetMap (spina dorsale)

- **Cosa offre:** rete stradale completa (per routing asfalto+sterrato), `highway=track`, `surface`, `tracktype` (grade1-5), `4wd_only`, itinerari come relazioni. Verificato: la *Alta Via del Sale* esiste come relazione e come "Strada Ex-Militare Monesi – Col di Tenda".
- **Licenza:** ODbL — attribuzione "© OpenStreetMap contributors" + share-alike sul database derivato (l'uso per produrre mappe/percorsi è libero con attribuzione).
- **Limiti:** completezza dei tag variabile (nel pilota ~50% a bassa confidenza), nessun tag affidabile per "militare", accessi legali e chiusure stagionali assenti.

## 2. Regione Piemonte — Geoportale (CC-BY 4.0)

- **Licenza standard:** Creative Commons BY 4.0 (DGR 18-5072 del 2017) → riuso commerciale con attribuzione.
- **Dataset utili:**
  - **RPE — Rete del Patrimonio Escursionistico** (L.R. 12/2010): percorsi escursionistici validati per provincia. Visualizzatore IPLA `sentieri.ipla.org`, servizio WMS; download tracciati in GPX (alcuni con licenza specifica da verificare per dataset).
  - **Viabilità di interesse silvo-pastorale** (IPLA): rete di strade forestali — molte delle "strade bianche" e militari di montagna. Disponibile in Shapefile.
  - **SIFOR — Sistema Informativo Forestale Regionale** (L.R. 4/2009): supporto alla pianificazione forestale.
- **Da verificare:** termini esatti del singolo dataset RPE (alcuni download "con licenza specifica" più orientati alla PA).

## 3. Regione Liguria — Geoportale (CC-BY 4.0)

- **Licenza:** dati aperti regionali in CC-BY 4.0 (da confermare sul singolo metadato).
- **Dataset utili:**
  - **REL — Rete Escursionistica Ligure** (DGR 22/2025): rete sentieri/percorsi validata. Scaricabile in formati vettoriali (**Shapefile, KML, GML, MapInfo**) dal geoportale, categoria Trasporti delle carte tematiche.
  - **Sentiero Liguria** e carte dei percorsi escursionistici collegate.
- **Accesso:** geoportal.regione.liguria.it (catalogo) + sezione open data regionale.

## 4. Itinerari regolamentati — dato critico, NON su OSM

Molti percorsi-simbolo hanno **accesso regolamentato**: questa informazione va da gestori/ordinanze, non da OSM.

- **Alta Via del Sale (Limone – Monesi):** auto/quad **20 €**, moto **15 €**, a piedi/bici **gratis**; apertura stabilita da **ordinanza del Comune di Briga Alta**, ingressi a data fissa, orario 8:00–20:00 (ultimo ingresso 18:00); prenotazione consigliata su briga.info.
- **Implicazione prodotto:** Campera deve mostrare apertura stagionale, costo e regole. Va gestito come **strato "accessi"** curato manualmente per gli itinerari principali.

## Raccomandazione di integrazione

1. **OSM esteso a tutto Piemonte + Liguria** come base (routing + tracce + itinerari nominati). Veloce e gratuito → si parte da qui.
2. **Arricchimento regionale:** sovrapporre Viabilità silvo-pastorale (Piemonte) e REL (Liguria) per autorità, strade forestali/militari e percorsi validati. Ingestione Shapefile/WFS → mappatura sullo schema `offroad_segments`.
3. **Strato accessi curato** per gli itinerari regolamentati (Via del Sale e simili): apertura, costo, prenotazione.
4. **Attribuzioni** sempre visibili: "© OpenStreetMap contributors", "Regione Piemonte – CC BY 4.0", "Regione Liguria – CC BY 4.0".

## Fonti

- Rete Escursionistica Ligure (REL): https://geoportal.regione.liguria.it/ — scheda REL DGR 22/2025: https://geoportal.regione.liguria.it/component/k2/item/930-rel-d-g-r-22-2025.html — metadati RNDT: https://geodati.gov.it/geoportale/visualizzazione-metadati/scheda-metadati/?uuid=r_liguri:D.1630
- Download sentieri Liguria: https://sites.google.com/view/sentieriliguria/download
- RPE Piemonte: https://www.regione.piemonte.it/web/temi/ambiente-territorio/montagna/patrimonio-outdoor/visualizzare-dati-della-rete-patrimonio-escursionistico — visualizzatore IPLA: https://sentieri.ipla.org/ — metadato: https://www.geoportale.piemonte.it/geonetwork/srv/metadata/r_piemon:77e9d108-c291-4fcf-ba5b-12c1b3251558
- Viabilità silvo-pastorale (Geoportale Piemonte): https://www.geoportale.piemonte.it/geonetwork/srv/api/records/r_piemon:afb461fb-4147-4a90-a884-cf7ddb0cc1b2
- Licenza / copyright Geoportale Piemonte (CC-BY 4.0): https://www.geoportale.piemonte.it/cms/credits-e-copyright
- Alta Via del Sale — termini e prenotazione: https://briga.info/termini-condizioni/ — https://www.altaviadelsale.com/ita/limone-monesi
