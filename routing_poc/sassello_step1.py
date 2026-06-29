#!/usr/bin/env python3
"""Step 1 - Topologia rete offroad area pilota Sassello (SV).
Pull Overpass (stessa query dell'importer Campera) -> noding geometrico (shapely)
-> grafo (networkx) -> analisi connettivita -> test Dijkstra A-B -> GPX + mappa.
Nessun accesso al DB live: dato preso da Overpass, identico a quanto importato.
"""
import json, math, time, urllib.request, urllib.parse
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
import networkx as nx

# Sassello (SV) ~44.483, 8.490 -> box ~30 km
CENTER = (44.483, 8.490)
HALF_LAT = 0.135       # ~15 km
HALF_LON = 0.190       # ~15 km a 44.5N
S, W = CENTER[0]-HALF_LAT, CENTER[1]-HALF_LON
N, E = CENTER[0]+HALF_LAT, CENTER[1]+HALF_LON
OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "CamperaOffroad-POC/0.1 (loris.cresta@gmail.com)"

def overpass(s,w,n,e):
    q = f"""[out:json][timeout:120];
(
  way["highway"="track"]({s},{w},{n},{e});
  way["highway"~"^(unclassified|service|path|bridleway)$"]["surface"~"^(unpaved|gravel|fine_gravel|compacted|dirt|ground|earth)$"]({s},{w},{n},{e});
  way["tracktype"]({s},{w},{n},{e});
  way["4wd_only"="yes"]({s},{w},{n},{e});
);
out geom tags;"""
    data = urllib.parse.urlencode({"data": q}).encode()
    req = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=180).read())

def haversine(a, b):
    R=6371000.0
    la1,lo1,la2,lo2 = map(math.radians,[a[1],a[0],b[1],b[0]])
    h=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))

def line_len(coords):
    return sum(haversine(coords[i],coords[i+1]) for i in range(len(coords)-1))

def classify(t):
    tr,sf,sm = t.get("tracktype"),t.get("surface"),t.get("smoothness")
    fourwd = t.get("4wd_only")=="yes"
    if fourwd or tr in ("grade4","grade5") or sm in ("very_bad","horrible","very_horrible","impassable"): return "solo_4x4"
    if tr=="grade3" or sf in ("dirt","ground","earth"): return "impegnativo"
    if tr=="grade2" or sf in ("gravel","fine_gravel"): return "medio"
    return "facile"

print(f"BBox Sassello: S={S:.3f} W={W:.3f} N={N:.3f} E={E:.3f}  (~{haversine((W,S),(E,S))/1000:.0f}x{haversine((W,S),(W,N))/1000:.0f} km)")
t0=time.time()
js = overpass(S,W,N,E)
ways = [el for el in js.get("elements",[]) if el.get("type")=="way" and el.get("geometry") and len(el["geometry"])>=2]
print(f"Overpass: {len(ways)} way offroad in {time.time()-t0:.0f}s")

lines=[]; diff_count={}
for el in ways:
    coords=[(p["lon"],p["lat"]) for p in el["geometry"]]
    lines.append(LineString(coords))
    d=classify(el.get("tags",{})); diff_count[d]=diff_count.get(d,0)+1
print("Per difficolta:", diff_count)
tot_raw_km = sum(line_len(list(l.coords)) for l in lines)/1000
print(f"Lunghezza grezza totale: {tot_raw_km:.1f} km")

# --- NODING geometrico: split a ogni intersezione ---
print("Noding (unary_union)...")
merged = unary_union(lines)
segs = list(merged.geoms) if merged.geom_type=="MultiLineString" else [merged]
print(f"Segmenti dopo noding: {len(segs)}")

def key(pt): return (round(pt[0],6), round(pt[1],6))
G = nx.Graph()
for s in segs:
    cs=list(s.coords)
    if len(cs)<2: continue
    a,b = key(cs[0]), key(cs[-1])
    if a==b: continue
    L=line_len(cs)
    if G.has_edge(a,b) and G[a][b]["length_m"]<=L: continue
    G.add_edge(a,b, length_m=L, coords=cs)

print(f"Grafo: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi")

# --- Connettivita ---
comps = sorted(nx.connected_components(G), key=len, reverse=True)
def comp_len(c):
    sg=G.subgraph(c); return sum(d["length_m"] for _,_,d in sg.edges(data=True))
tot_km = sum(d["length_m"] for _,_,d in G.edges(data=True))/1000
big = comps[0]
big_km = comp_len(big)/1000
print(f"\n== CONNETTIVITA ==")
print(f"Componenti connesse: {len(comps)}")
print(f"Componente piu grande: {len(big)} nodi, {big_km:.1f} km ({100*big_km/tot_km:.1f}% della rete)")
print(f"Top 5 componenti per lunghezza (km): " + ", ".join(f"{comp_len(c)/1000:.1f}" for c in comps[:5]))
isolated = sum(1 for c in comps if len(c)<=2)
print(f"Frammenti isolati (<=2 nodi): {isolated}")

# --- Test Dijkstra A->B nella componente piu grande (nodi piu lontani) ---
bg = G.subgraph(big)
nodes=list(bg.nodes())
import itertools
# stima estremi: nodo piu a SW e piu a NE
sw=min(nodes,key=lambda n:n[0]+n[1]); ne=max(nodes,key=lambda n:n[0]+n[1])
path=nx.shortest_path(bg, sw, ne, weight="length_m")
plen=nx.shortest_path_length(bg, sw, ne, weight="length_m")/1000
# ricostruisci geometria completa
route_coords=[]
for u,v in zip(path,path[1:]):
    cs=bg[u][v]["coords"]
    if key(cs[0])!=u: cs=cs[::-1]
    if route_coords and route_coords[-1]==cs[0]: route_coords.extend(cs[1:])
    else: route_coords.extend(cs)
print(f"\n== TEST DIJKSTRA (offroad puro) ==")
print(f"A={sw}  B={ne}")
print(f"Percorso: {len(path)} nodi, {plen:.1f} km")

# --- GPX ---
gpx_pts="".join(f'<trkpt lat="{lat}" lon="{lon}"></trkpt>' for lon,lat in route_coords)
gpx=('<?xml version="1.0" encoding="UTF-8"?>'
     '<gpx version="1.1" creator="Campera Routing POC">'
     f'<trk><name>Sassello offroad test A-B</name><trkseg>{gpx_pts}</trkseg></trk></gpx>')
open("/sessions/compassionate-gifted-goldberg/mnt/outputs/sassello_test_route.gpx","w").write(gpx)

# --- export GeoJSON componenti per mappa ---
def seg_feat(coords, comp_id, big):
    return {"type":"Feature","properties":{"comp":comp_id,"big":big},
            "geometry":{"type":"LineString","coordinates":coords}}
comp_of={}
for i,c in enumerate(comps):
    for n in c: comp_of[n]=i
feats=[]
for u,v,d in G.edges(data=True):
    ci=comp_of[u]
    feats.append(seg_feat(d["coords"], ci, ci==0))
route_feat={"type":"Feature","properties":{"route":True},
            "geometry":{"type":"LineString","coordinates":route_coords}}
ab_feats=[{"type":"Feature","properties":{"pt":lbl},"geometry":{"type":"Point","coordinates":[p[0],p[1]]}}
          for lbl,p in (("A",sw),("B",ne))]
gj={"type":"FeatureCollection","features":feats+[route_feat]+ab_feats}
open("/sessions/compassionate-gifted-goldberg/mnt/outputs/sassello_network.geojson","w").write(json.dumps(gj))

# summary json
summary=dict(bbox=[W,S,E,N], ways=len(ways), diff=diff_count, raw_km=round(tot_raw_km,1),
             segments=len(segs), nodes=G.number_of_nodes(), edges=G.number_of_edges(),
             components=len(comps), big_nodes=len(big), big_km=round(big_km,1),
             big_pct=round(100*big_km/tot_km,1), isolated=isolated,
             route_km=round(plen,1), route_nodes=len(path))
open("/sessions/compassionate-gifted-goldberg/mnt/outputs/sassello_summary.json","w").write(json.dumps(summary,indent=2))
print("\nFile scritti: sassello_test_route.gpx, sassello_network.geojson, sassello_summary.json")
