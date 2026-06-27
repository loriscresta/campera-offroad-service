#!/usr/bin/env python3
"""Carica un GeoJSON di tratti offroad in PostGIS (tabella offroad_segments).

Pensato per il PRIMO deploy: popola il database senza osm2pgsql, usando i
GeoJSON gia prodotti (es. data/pilot_appennino_ligure.geojson). L'import completo
Geofabrik/osm2pgsql resta in import/import_osm.sh per la fase di scala.

Connessione: usa DATABASE_URL se presente (Railway), altrimenti POSTGRES_*.
Uso:
    python3 scripts/load_geojson_to_pg.py data/pilot_appennino_ligure.geojson
"""
import os, sys, json
import psycopg

def dsn():
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    return (
        f"host={os.environ.get('POSTGRES_HOST','localhost')} "
        f"port={os.environ.get('POSTGRES_PORT','5432')} "
        f"dbname={os.environ.get('POSTGRES_DB','campera_offroad')} "
        f"user={os.environ.get('POSTGRES_USER','campera')} "
        f"password={os.environ.get('POSTGRES_PASSWORD','campera')}"
    )

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS offroad_segments (
    id TEXT PRIMARY KEY, name TEXT, difficulty TEXT NOT NULL, surface TEXT,
    tracktype TEXT, smoothness TEXT, requires_4wd BOOLEAN NOT NULL DEFAULT FALSE,
    suitable_for TEXT[] NOT NULL DEFAULT '{}', vehicle_max_width_m NUMERIC,
    vehicle_max_weight_t NUMERIC, vehicle_max_height_m NUMERIC, length_m NUMERIC,
    confidence TEXT NOT NULL DEFAULT 'media', warning TEXT,
    geom GEOMETRY(LineString, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_offroad_segments_geom ON offroad_segments USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_offroad_segments_diff ON offroad_segments (difficulty);
"""

INSERT = """
INSERT INTO offroad_segments
  (id, name, difficulty, surface, tracktype, requires_4wd, suitable_for,
   length_m, confidence, warning, geom)
VALUES
  (%(id)s, %(name)s, %(difficulty)s, %(surface)s, %(tracktype)s, %(requires_4wd)s,
   %(suitable_for)s, %(length_m)s, %(confidence)s, %(warning)s,
   ST_SetSRID(ST_GeomFromGeoJSON(%(geom)s), 4326))
ON CONFLICT (id) DO UPDATE SET
   name=EXCLUDED.name, difficulty=EXCLUDED.difficulty, surface=EXCLUDED.surface,
   tracktype=EXCLUDED.tracktype, requires_4wd=EXCLUDED.requires_4wd,
   suitable_for=EXCLUDED.suitable_for, length_m=EXCLUDED.length_m,
   confidence=EXCLUDED.confidence, warning=EXCLUDED.warning, geom=EXCLUDED.geom;
"""

def main(path):
    fc = json.load(open(path, encoding="utf-8"))
    feats = fc["features"]
    with psycopg.connect(dsn()) as conn:
        conn.execute(SCHEMA)
        with conn.cursor() as cur:
            n = 0
            for f in feats:
                p = f["properties"]
                cur.execute(INSERT, {
                    "id": p["id"], "name": p.get("name"), "difficulty": p["difficulty"],
                    "surface": p.get("surface"), "tracktype": p.get("tracktype"),
                    "requires_4wd": p.get("requires_4wd", False),
                    "suitable_for": p.get("suitable_for", []),
                    "length_m": p.get("length_m"), "confidence": p.get("confidence", "media"),
                    "warning": p.get("warning"),
                    "geom": json.dumps(f["geometry"]),
                })
                n += 1
        conn.commit()
    print(f"Caricati/aggiornati {n} tratti da {path}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/pilot_appennino_ligure.geojson")
