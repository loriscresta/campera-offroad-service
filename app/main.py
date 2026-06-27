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
from fastapi import FastAPI, Depends, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse

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


def auth(x_api_key: str = Header(default="")) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key mancante o non valida")


def db():
    return psycopg.connect(DSN, row_factory=dict_row)


def _feature(row: dict) -> dict:
    geom = row.pop("geometry")
    import json
    return {
        "type": "Feature",
        "geometry": json.loads(geom) if geom else None,
        "properties": row,
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


@app.post("/v1/route", dependencies=[Depends(auth)])
def route():
    # Fase 2: integrazione GraphHopper con profili van / camper_4x4.
    raise HTTPException(501, "Routing non ancora disponibile (fase 2)")


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
