"""Campera Offroad Service — API REST (data layer).

Endpoint:
  GET  /v1/segments         tratti offroad in un bbox (GeoJSON FeatureCollection)
  GET  /v1/segment/{id}     dettaglio di un tratto (JSON o GPX)
  POST /v1/route            stub fase 2 (routing van / 4x4)
Auth: header X-API-Key.
"""
import os
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Depends, Header, HTTPException, Query, Response, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import routing

API_KEY = os.environ.get("API_KEY", "dev")

# Railway/managed host: usa DATABASE_URL se presente; altrimenti POSTGRES_*.
if os.environ.get("DATABASE_URL"):
    DSN = os.environ["DATABASE_URL"]
else:
    DSN = (
        f"host={os.environ.get('POSTGRES_HOST','localhost')} "
        f"port={os.environ.get('POSTGRES_PORT','5432')} "
        f"dbname={os.environ.get('POSTGRES_DB','campera_offroad')} "
        f"user={os.environ.get('POSTGRES_USER','campera')} "
        f"password={os.environ.get('POSTGRES_PASSWORD','campera')}"
    )

DIFFICULTY_ORDER = ["facile", "medio", "impegnativo", "solo_4x4"]

app = FastAPI(title="Campera Offroad Service", version="0.1.0")

# Permette le chiamate dal browser (Campera Trail Planner e altri front-end).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_SCHEMA_SQL = """
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

_INSERT_SQL = """
INSERT INTO offroad_segments
  (id, name, difficulty, surface, tracktype, requires_4wd, suitable_for,
   length_m, confidence, warning, geom)
VALUES
  (%(id)s, %(name)s, %(difficulty)s, %(surface)s, %(tracktype)s, %(requires_4wd)s,
   %(suitable_for)s, %(length_m)s, %(confidence)s, %(warning)s,
   ST_SetSRID(ST_GeomFromGeoJSON(%(geom)s), 4326))
ON CONFLICT (id) DO NOTHING;
"""


@app.on_event("startup")
def _startup_seed():
    """Crea lo schema e, se il DB e vuoto, carica i dati pilota inclusi (seed_pilot.geojson)."""
    import json
    try:
        with db() as conn:
            conn.execute(_SCHEMA_SQL)
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) AS c FROM offroad_segments")
                count = cur.fetchone()["c"]
            if count == 0:
                path = os.path.join(os.path.dirname(__file__), "seed_pilot.geojson")
                if os.path.exists(path):
                    fc = json.load(open(path, encoding="utf-8"))
                    with conn.cursor() as cur:
                        for f in fc["features"]:
                            p = f["properties"]
                            cur.execute(_INSERT_SQL, {
                                "id": p["id"], "name": p.get("name"),
                                "difficulty": p["difficulty"], "surface": p.get("surface"),
                                "tracktype": p.get("tracktype"),
                                "requires_4wd": p.get("requires_4wd", False),
                                "suitable_for": p.get("suitable_for", []),
                                "length_m": p.get("length_m"),
                                "confidence": p.get("confidence", "media"),
                                "warning": p.get("warning"),
                                "geom": json.dumps(f["geometry"]),
                            })
                    print(f"[seed] caricati {len(fc['features'])} tratti pilota")
            conn.commit()
    except Exception as e:  # non bloccare l'avvio per errori di seed
        print("[seed] errore:", e)


def auth(x_api_key: str = Header(default="")) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key mancante o non valida")


def db():
    return psycopg.connect(DSN, row_factory=dict_row)


def _feature(row: dict) -> dict:
    import json
    from decimal import Decimal
    geom = row.pop("geometry")
    props = {k: (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()}
    return {
        "type": "Feature",
        "geometry": json.loads(geom) if geom else None,
        "properties": props,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/segments", dependencies=[Depends(auth)])
def segments(
    bbox: str = Query(..., description="min_lon,min_lat,max_lon,max_lat"),
    vehicle: Optional[str] = Query(None, pattern="^(van|camper_4x4)$"),
    max_difficulty: Optional[str] = Query(None),
    limit: int = Query(1000, le=5000),
):
    try:
        min_lon, min_lat, max_lon, max_lat = (float(x) for x in bbox.split(","))
    except ValueError:
        raise HTTPException(400, "bbox non valido: usa min_lon,min_lat,max_lon,max_lat")

    where = ["geom && ST_MakeEnvelope(%s,%s,%s,%s,4326)"]
    params: list = [min_lon, min_lat, max_lon, max_lat]
    if vehicle:
        where.append("%s = ANY(suitable_for)")
        params.append(vehicle)
    if max_difficulty:
        if max_difficulty not in DIFFICULTY_ORDER:
            raise HTTPException(400, "max_difficulty non valido")
        allowed = DIFFICULTY_ORDER[: DIFFICULTY_ORDER.index(max_difficulty) + 1]
        where.append("difficulty = ANY(%s)")
        params.append(allowed)
    params.append(limit)

    sql = f"""
        SELECT id, name, difficulty, surface, tracktype, requires_4wd,
               suitable_for, vehicle_max_width_m, vehicle_max_weight_t,
               vehicle_max_height_m, length_m, confidence, warning,
               ST_AsGeoJSON(geom) AS geometry
        FROM offroad_segments
        WHERE {' AND '.join(where)}
        LIMIT %s
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return JSONResponse(
        media_type="application/geo+json",
        content={"type": "FeatureCollection", "features": [_feature(r) for r in rows]},
    )


@app.get("/v1/segment/{seg_id:path}", dependencies=[Depends(auth)])
def segment(seg_id: str, format: str = Query("json", pattern="^(json|gpx)$")):
    sql = """
        SELECT id, name, difficulty, surface, tracktype, smoothness, requires_4wd,
               suitable_for, vehicle_max_width_m, vehicle_max_weight_t,
               vehicle_max_height_m, length_m, confidence, warning,
               ST_AsGeoJSON(geom) AS geometry
        FROM offroad_segments WHERE id = %s
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, [seg_id])
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Tratto non trovato")
    if format == "gpx":
        return Response(_to_gpx(row), media_type="application/gpx+xml")
    return _feature(row)


class RouteRequest(BaseModel):
    start: list[float] = Field(..., description="[lon, lat] partenza")
    end: list[float] = Field(..., description="[lon, lat] arrivo")
    waypoints: list[list[float]] = Field(default_factory=list, description="[[lon,lat],...] intermedi")
    vehicle: str = Field("van", description="van | camper_4x4")
    format: str = Field("gpx", pattern="^(gpx|json)$")


@app.post("/v1/route", dependencies=[Depends(auth)])
def route(req: RouteRequest):
    """Percorso A -> waypoint -> B che unisce piu tratti, passando da asfalto.

    Profilo di costo per veicolo: 'van'/'camper' evita pendenze forti e solo-4x4;
    'camper_4x4' cerca lo sterrato tecnico. Output GPX o GeoJSON + riepilogo.
    Pilota: attivo solo dove e caricato il grafo (area Sassello); altrove 501.
    """
    try:
        g = routing.get_graph()
    except FileNotFoundError:
        raise HTTPException(501, "Routing non disponibile: grafo non caricato (fase pilota)")
    for p in [req.start, req.end, *req.waypoints]:
        if not (isinstance(p, list) and len(p) == 2):
            raise HTTPException(400, "Punti non validi: usa [lon, lat]")
    profile = routing.vehicle_to_profile(req.vehicle)
    points = [req.start, *req.waypoints, req.end]
    res = g.route(points, profile)
    if res is None:
        raise HTTPException(422, "Nessun percorso trovato tra i punti indicati")
    if req.format == "gpx":
        return Response(routing.to_gpx(res["coords"], f"Campera {req.vehicle}"),
                        media_type="application/gpx+xml")
    return {
        "summary": res["summary"],
        "profile": profile,
        "geometry": {"type": "LineString", "coordinates": res["coords"]},
    }


@app.post("/v1/admin/load-graph", dependencies=[Depends(auth)])
async def load_graph(request: Request, gzipped: int = Query(0)):
    """Carica una volta l'artefatto del grafo sul volume (es. /data).

    Body = file del grafo (JSON, eventualmente gzip con ?gzipped=1). Dopo questa
    chiamata `/v1/route` diventa attivo. Il grafo NON e in git: si carica qui.
    """
    raw = await request.body()
    if not raw:
        raise HTTPException(400, "Body vuoto: invia il file del grafo")
    try:
        g = routing.save_graph(raw, gzipped=bool(gzipped))
    except Exception as e:
        raise HTTPException(400, f"Grafo non valido: {e}")
    return {"loaded": True, "path": routing.graph_path(), "meta": g.meta}


@app.get("/v1/route/status", dependencies=[Depends(auth)])
def route_status():
    """Dice se il routing e attivo (grafo caricato) e su quale area."""
    import os as _os
    p = routing.graph_path()
    if not _os.path.exists(p):
        return {"active": False, "graph_path": p}
    try:
        g = routing.get_graph()
        return {"active": True, "graph_path": p, "meta": g.meta}
    except Exception as e:
        return {"active": False, "graph_path": p, "error": str(e)}


@app.get("/v1/admin/clean-boundaries", dependencies=[Depends(auth)])
def clean_boundaries(dry_run: int = Query(1), buffer_km: float = Query(20)):
    """Rimuove i tratti oltre `buffer_km` dai confini di Piemonte/Liguria.

    Mantiene la fascia transfrontaliera (es. 20 km, lato Francia) cosi i percorsi
    di confine non vengono persi. dry_run=1 = solo anteprima.
    """
    import json as _json
    import urllib.request as _url
    src = os.environ.get(
        "REGIONS_GEOJSON_URL",
        "https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/limits_IT_regions.geojson",
    )
    keep = {"piemonte", "liguria"}
    req = _url.Request(src, headers={"User-Agent": "CamperaOffroad/0.1"})
    fc = _json.loads(_url.urlopen(req, timeout=60).read())
    geoms = [
        _json.dumps(f["geometry"])
        for f in fc["features"]
        if (f.get("properties", {}).get("reg_name", "") or "").strip().lower() in keep
    ]
    if not geoms:
        raise HTTPException(500, "Confini regionali non trovati")
    with db() as conn, conn.cursor() as cur:
        cur.execute("CREATE TEMP TABLE keep_region (geom geometry);")
        for g in geoms:
            cur.execute(
                "INSERT INTO keep_region(geom) VALUES (ST_SetSRID(ST_GeomFromGeoJSON(%s),4326));",
                (g,),
            )
        # Regione + fascia buffer (in metri) come unica geometria, indicizzata.
        cur.execute(
            "CREATE TEMP TABLE keep_buf AS "
            "SELECT ST_Buffer(ST_Union(geom)::geography, %s)::geometry AS geom FROM keep_region;",
            (buffer_km * 1000.0,),
        )
        cur.execute("CREATE INDEX ON keep_buf USING GIST (geom);")
        cur.execute("SELECT count(*) AS c FROM offroad_segments;")
        before = cur.fetchone()["c"]
        cur.execute(
            "SELECT count(*) AS c FROM offroad_segments s "
            "WHERE NOT EXISTS (SELECT 1 FROM keep_buf k WHERE ST_Intersects(s.geom, k.geom));"
        )
        out = cur.fetchone()["c"]
        deleted = 0
        if not dry_run:
            cur.execute(
                "DELETE FROM offroad_segments s "
                "WHERE NOT EXISTS (SELECT 1 FROM keep_buf k WHERE ST_Intersects(s.geom, k.geom));"
            )
            deleted = cur.rowcount
            conn.commit()
    return {
        "total": before, "out_of_buffer": out, "deleted": deleted,
        "buffer_km": buffer_km, "dry_run": bool(dry_run),
    }


def _to_gpx(row: dict) -> str:
    import json
    coords = json.loads(row["geometry"])["coordinates"]
    pts = "".join(f'<trkpt lat="{lat}" lon="{lon}"></trkpt>' for lon, lat in coords)
    name = (row.get("name") or row["id"])
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="Campera Offroad Service">'
        f"<trk><name>{name}</name><trkseg>{pts}</trkseg></trk></gpx>"
    )
