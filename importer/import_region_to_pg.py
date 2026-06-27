#!/usr/bin/env python3
"""Import completo offroad di una regione in PostGIS, a tessere via Overpass.

Divide il bounding box in celle, per ogni cella interroga Overpass (tracce,
tracktype, 4wd, sterrati su strade minori), classifica e fa UPSERT nella tabella
offroad_segments. Pensato per girare come job (Railway) o in locale.

Connessione DB: DATABASE_URL (Railway) oppure POSTGRES_*.
Variabili opzionali:
  REGION_BBOX="min_lon,min_lat,max_lon,max_lat"  (default: Piemonte+Liguria)
  TILE_DEG="0.2"        dimensione cella in gradi
  SLEEP_SEC="2"         pausa tra le tessere (gentilezza verso Overpass)
  DRY_RUN="1"           non scrive su DB: stampa solo i conteggi (per stimare)
"""
import os, sys, json, math, time, urllib.request, urllib.parse

REGION_BBOX = os.environ.get("REGION_BBOX", "6.60,43.75,10.15,46.50")
TILE = float(os.environ.get("TILE_DEG", "0.2"))
SLEEP = float(os.environ.get("SLEEP_SEC", "2"))
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
UA = "CamperaOffroad/0.1 (loris.cresta@gmail.com)"
OVERPASS = "https://overpass-api.de/api/interpreter"

min_lon, min_lat, max_lon, max_lat = (float(x) for x in REGION_BBOX.split(","))


def tiles():
    lat = min_lat
    while lat < max_lat:
        lon = min_lon
        while lon < max_lon:
            yield (lat, lon, min(lat + TILE, max_lat), min(lon + TILE, max_lon))
            lon += TILE
        lat += TILE


def overpass(s, w, n, e, retries=3):
    q = f"""[out:json][timeout:90];
(
  way["highway"="track"]({s},{w},{n},{e});
  way["highway"~"^(unclassified|service|path|bridleway)$"]["surface"~"^(unpaved|gravel|fine_gravel|compacted|dirt|ground|earth)$"]({s},{w},{n},{e});
  way["tracktype"]({s},{w},{n},{e});
  way["4wd_only"="yes"]({s},{w},{n},{e});
);
out geom tags;"""
    data = urllib.parse.urlencode({"data": q}).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": UA})
            return json.loads(urllib.request.urlopen(req, timeout=120).read())
        except Exception as ex:
            if attempt == retries - 1:
                print("  ! errore tessera:", ex)
                return {"elements": []}
            time.sleep(5 * (attempt + 1))


def haversine_len(geom):
    R = 6371000.0
    tot = 0.0
    for a, b in zip(geom, geom[1:]):
        la1, lo1, la2, lo2 = map(math.radians, [a["lat"], a["lon"], b["lat"], b["lon"]])
        h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
        tot += 2*R*math.asin(math.sqrt(h))
    return tot


def classify(t):
    tr, sf, sm = t.get("tracktype"), t.get("surface"), t.get("smoothness")
    fourwd = t.get("4wd_only") == "yes"
    if fourwd or tr in ("grade4", "grade5") or sm in ("very_bad", "horrible", "very_horrible", "impassable"):
        diff = "solo_4x4"
    elif tr == "grade3" or sf in ("dirt", "ground", "earth"):
        diff = "impegnativo"
    elif tr == "grade2" or sf in ("gravel", "fine_gravel"):
        diff = "medio"
    else:
        diff = "facile"
    suitable = ["camper_4x4"] if (fourwd or tr in ("grade4", "grade5")) else ["van", "camper_4x4"]
    conf = "alta" if (tr and sf) else ("media" if (tr or sf) else "bassa")
    return diff, suitable, conf, fourwd


def main():
    conn = cur = None
    if not DRY_RUN:
        import psycopg
        dsn = os.environ.get("DATABASE_URL") or (
            f"host={os.environ.get('POSTGRES_HOST','localhost')} port={os.environ.get('POSTGRES_PORT','5432')} "
            f"dbname={os.environ.get('POSTGRES_DB','campera_offroad')} user={os.environ.get('POSTGRES_USER','campera')} "
            f"password={os.environ.get('POSTGRES_PASSWORD','campera')}")
        conn = psycopg.connect(dsn)
        conn.execute("""CREATE EXTENSION IF NOT EXISTS postgis;
        CREATE TABLE IF NOT EXISTS offroad_segments (
          id TEXT PRIMARY KEY, name TEXT, difficulty TEXT NOT NULL, surface TEXT, tracktype TEXT,
          smoothness TEXT, requires_4wd BOOLEAN NOT NULL DEFAULT FALSE, suitable_for TEXT[] NOT NULL DEFAULT '{}',
          vehicle_max_width_m NUMERIC, vehicle_max_weight_t NUMERIC, vehicle_max_height_m NUMERIC,
          length_m NUMERIC, confidence TEXT NOT NULL DEFAULT 'media', warning TEXT,
          geom GEOMETRY(LineString,4326) NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_offroad_segments_geom ON offroad_segments USING GIST (geom);
        CREATE INDEX IF NOT EXISTS idx_offroad_segments_diff ON offroad_segments (difficulty);""")
        conn.commit()

    INSERT = """INSERT INTO offroad_segments
      (id,name,difficulty,surface,tracktype,requires_4wd,suitable_for,length_m,confidence,warning,geom)
      VALUES (%(id)s,%(name)s,%(difficulty)s,%(surface)s,%(tracktype)s,%(requires_4wd)s,%(suitable_for)s,
              %(length_m)s,%(confidence)s,%(warning)s,ST_SetSRID(ST_GeomFromGeoJSON(%(geom)s),4326))
      ON CONFLICT (id) DO NOTHING;"""

    all_tiles = list(tiles())
    seen, total = set(), 0
    print(f"Regione {REGION_BBOX} | {len(all_tiles)} tessere da {TILE} gradi | DRY_RUN={DRY_RUN}")
    for i, (s, w, n, e) in enumerate(all_tiles, 1):
        js = overpass(s, w, n, e)
        els = [x for x in js.get("elements", []) if x.get("type") == "way" and x.get("geometry")]
        batch = 0
        for el in els:
            oid = f"way/{el['id']}"
            if oid in seen:
                continue
            seen.add(oid)
            coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
            if len(coords) < 2:
                continue
            t = el.get("tags", {})
            diff, suitable, conf, fourwd = classify(t)
            total += 1
            batch += 1
            if not DRY_RUN:
                cur = conn.cursor()
                cur.execute(INSERT, {
                    "id": oid, "name": t.get("name"), "difficulty": diff, "surface": t.get("surface"),
                    "tracktype": t.get("tracktype"), "requires_4wd": fourwd, "suitable_for": suitable,
                    "length_m": round(haversine_len(el["geometry"]), 1), "confidence": conf,
                    "warning": "Dati parziali: verifica le condizioni locali" if conf == "bassa" else None,
                    "geom": json.dumps({"type": "LineString", "coordinates": coords}),
                })
        if not DRY_RUN:
            conn.commit()
        print(f"[{i}/{len(all_tiles)}] tessera ({s:.2f},{w:.2f}) -> +{batch} nuovi (totale {total})")
        time.sleep(SLEEP)

    if not DRY_RUN:
        conn.close()
    print(f"FINE. Tratti unici importati: {total}")


if __name__ == "__main__":
    main()
