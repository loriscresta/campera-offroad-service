# Manutenzione — Pulizia confini e Aggiornamento mensile

## 1. Pulizia ai confini regionali (rimuovere lo spillover)

L'import a tessere include qualche tratto fuori da Piemonte/Liguria (Francia,
Lombardia, Valle d'Aosta, mare). Lo script `scripts/clean_region_boundaries.py`
scarica i confini ufficiali delle due regioni e cancella i tratti esterni.

Esecuzione (prova senza cancellare):
```
DRY_RUN=1 DATABASE_URL=... python3 scripts/clean_region_boundaries.py
```
Esecuzione reale:
```
DATABASE_URL=... python3 scripts/clean_region_boundaries.py
```
In cloud: copia gia presente in `importer/clean_region_boundaries.py`, eseguibile
come job Railway (stesso DATABASE_URL interno).

## 2. Aggiornamento mensile automatico

L'import e idempotente (`ON CONFLICT DO NOTHING`): rilanciarlo recepisce le novita
OSM. Opzioni:

### Opzione A — Cron su Railway (consigliata)
Nel servizio importer (Railway) → Settings → Deploy → "Cron Schedule":
```
0 3 1 * *      # ogni 1 del mese alle 03:00
```
Railway riavvia il job a quell'ora, che ri-esegue l'import. Con `restartPolicyType
NEVER` il job parte, gira e si ferma.

> Per fare anche la pulizia confini dopo l'import, si puo impostare un secondo job
> (stessa immagine, CMD su `clean_region_boundaries.py`) con cron poco dopo, es.
> `30 4 1 * *`.

### Opzione B — Attivita programmata in Cowork
In alternativa al cron Railway, una scheduled task mensile puo lanciare il job o
verificare la copertura.

## Note
- Il limite API e 5.000 tratti per chiamata: a livello di mappa (riquadri piccoli)
  non incide; per export massivi si pagina per bbox.
- Dopo la pulizia, il conteggio totale cala (via lo spillover) ma la copertura
  Piemonte+Liguria resta completa.
