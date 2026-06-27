#!/usr/bin/env python3
"""Estrazione rapida dei tratti offroad via Overpass (validazione / seed).

Non richiede database: produce un GeoJSON reale della zona pilota e stampa la
distribuzione di difficolta. Le regole di classificazione sono allineate a
db/02_classify.sql.

Uso:
    python3 scripts/seed_overpass.py
Variabili opzionali:
    BBOX_SEED="min_lon,min_lat,max_lon,max_lat"   (default: core Appennino ligure)
"""
import os, json, math, collections, urllib.request, urllib.parse

# Default: core Appennino ligure-piemontese (Valle Scrivia, Val Borbera, Ovadese)
_default = "8.80,44.55,9.15,44.72"
min_lon, min_lat, max_lon, max_lat = (
    float(x) for x in os.environ.get("BBOX_SEED", _default).split(",")
)
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "pilot_appennino_ligure.geojson")
UA = "CamperaOffroad/0.1 (loris.cresta@gmail.com)"

QUERY = f"""[out:json][timeout:60];
(
  way["highway"="track"]({min_lat},{min_lon},{max_lat},{max_lon});
  way["highway"~"^(unclassified|service|path|bridleway)$"]["surface"~"^(unpaved|gravel|fine_gravel|compacted|dirt|ground|earth)$"]({min_lat},{min_lon},{max_lat},{max_lon});
  way["tracktype"]({min_lat},{min_lon},{max_lat},{max_lon});
  way["4wd_only"="yes"]({min_lat},{min_lon},{max_lat},{max_lon});
);
out geom tags;"""


def haversine_len(geom):
    R = 6371000.0
    tot = 0.0
    for a, b in zip(geom, geom[1:]):
        la1, lo1, la2, lo2 = map(math.radians, [a["lat"], a["lon"], b["lat"], b["lon"]])
        h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        tot += 2 * R * math.asin(math.sqrt(h))
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
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=data,
                                 headers={"User-Agent": UA})
    js = json.loads(urllib.request.urlopen(req, timeout=90).read())
    els = [e for e in js.get("elements", []) if e.get("type") == "way" and e.get("geometry")]

    feats, diff_c, conf_c, km = [], collections.Counter(), collections.Counter(), collections.Counter()
    for e in els:
        t = e.get("tags", {})
        coords = [[p["lon"], p["lat"]] for p in e["geometry"]]
        if len(coords) < 2:
            continue
        diff, suitable, conf, fourwd = classify(t)
        length = round(haversine_len(e["geometry"]), 1)
        diff_c[diff] += 1; conf_c[conf] += 1; km[diff] += length
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "id": f"way/{e['id']}", "name": t.get("name"),
                "difficulty": diff, "surface": t.get("surface"), "tracktype": t.get("tracktype"),
                "smoothness": t.get("smoothness"), "requires_4wd": fourwd, "suitable_for": suitable,
                "length_m": length, "confidence": conf,
                "warning": "Dati parziali: verifica le condizioni locali" if conf == "bassa" else None,
            },
        })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": feats}, open(OUT, "w"), ensure_ascii=False)
    print("tratti classificati:", len(feats))
    print("per difficolta:", dict(diff_c))
    print("km per difficolta:", {k: round(v / 1000, 1) for k, v in km.items()})
    print("per confidence:", dict(conf_c))
    print("salvato:", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
