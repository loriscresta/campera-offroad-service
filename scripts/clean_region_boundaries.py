#!/usr/bin/env python3
"""Pulizia ai confini regionali: rimuove i tratti fuori da Piemonte e Liguria.

L'import a tessere (bbox) include un po' di spillover (Francia, Lombardia, Valle
d'Aosta, mare). Questo script scarica i confini ufficiali delle due regioni e
cancella da offroad_segments i tratti che NON ricadono dentro quei confini.

Connessione DB: DATABASE_URL (Railway) oppure POSTGRES_*.
Variabili opzionali:
  REGIONS_GEOJSON_URL  (default: openpolis limits_IT_regions.geojson)
  KEEP_REGIONS         (default: "Piemonte,Liguria")
  DRY_RUN=1            stampa quanti tratti verrebbero rimossi, senza cancellare
"""
import os, json, urllib.request
import psycopg

URL = os.environ.get(
    "REGIONS_GEOJSON_URL",
    "https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/limits_IT_regions.geojson",
)
KEEP = [s.strip().lower() for s in os.environ.get("KEEP_REGIONS", "Piemonte,Liguria").split(",")]
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"


def dsn():
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    return (
        f"host={os.environ.get('POSTGRES_HOST','localhost')} port={os.environ.get('POSTGRES_PORT','5432')} "
        f"dbname={os.environ.get('POSTGRES_DB','campera_offroad')} user={os.environ.get('POSTGRES_USER','campera')} "
        f"password={os.environ.get('POSTGRES_PASSWORD','campera')}"
    )


def main():
    print("Scarico i confini regionali:", URL)
    req = urllib.request.Request(URL, headers={"User-Agent": "CamperaOffroad/0.1"})
    fc = json.loads(urllib.request.urlopen(req, timeout=60).read())

    # Estrai le geometrie delle regioni da tenere (campo nome variabile a seconda della fonte)
    geoms = []
    for f in fc["features"]:
        p = f.get("properties", {})
        name = (p.get("reg_name") or p.get("name") or p.get("NOME_REG") or "").strip().lower()
        if name in KEEP:
            geoms.append(json.dumps(f["geometry"]))
    if not geoms:
        raise SystemExit(f"Nessuna regione trovata tra {KEEP}. Controlla REGIONS_GEOJSON_URL e i nomi.")
    print(f"Regioni trovate da tenere: {len(geoms)}")

    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        # Costruisci un'unica geometria unione delle regioni da tenere, in una tabella temporanea
        cur.execute("CREATE TEMP TABLE keep_region (geom geometry(MultiPolygon,4326));")
        for g in geoms:
            cur.execute(
                "INSERT INTO keep_region (geom) VALUES (ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s),4326)));",
                (g,),
            )
        cur.execute("SELECT ST_Union(geom) FROM keep_region;")
        # Conta e cancella i tratti che NON intersecano le regioni da tenere
        cur.execute("SELECT count(*) FROM offroad_segments;")
        before = cur.fetchone()[0]
        cur.execute("""
            SELECT count(*) FROM offroad_segments s
            WHERE NOT EXISTS (
              SELECT 1 FROM keep_region k WHERE ST_Intersects(s.geom, k.geom)
            );
        """)
        to_remove = cur.fetchone()[0]
        print(f"Tratti totali: {before} | fuori dai confini: {to_remove}")
        if DRY_RUN:
            print("DRY_RUN: nessuna cancellazione.")
            return
        cur.execute("""
            DELETE FROM offroad_segments s
            WHERE NOT EXISTS (
              SELECT 1 FROM keep_region k WHERE ST_Intersects(s.geom, k.geom)
            );
        """)
        conn.commit()
        print(f"Rimossi {to_remove} tratti fuori da Piemonte/Liguria. Restano {before - to_remove}.")


if __name__ == "__main__":
    main()
