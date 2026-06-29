#!/usr/bin/env python3
"""Step 2 - Grafo unificato offroad + strade asfaltate (area Sassello).
Aggiunge la rete stradale OSM (presa al volo, NON salvata), noda tutto insieme,
rimisura connettivita e instrada A->B cucendo sterrati via asfalto.
Peso provvisorio 'preferisci offroad' (anteprima del cost model dello Step 3).
"""
import json, math, time, urllib.request, urllib.parse
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely import STRtree
import networkx as nx

CENTER=(44.483,8.490); HL=0.135; HO=0.190
S,W,N,E = CENTER[0]-HL, CENTER[1]-HO, CENTER[0]+HL, CENTER[1]+HO
OVERPASS="https://overpass-api.de/api/interpreter"
UA="CamperaOffroad-POC/0.1 (loris.cresta@gmail.com)"
ASPHALT_PENALTY=3.0   # provvisorio: prefer sterrato, asfalto solo per collegare

def ask(q):
    data=urllib.parse.urlencode({"data":q}).encode()
    req=urllib.request.Request(OVERPASS,data=data,headers={"User-Agent":UA})
    return json.loads(urllib.request.urlopen(req,timeout=240).read())

Q_OFF=f"""[out:json][timeout:120];
(way["highway"="track"]({S},{W},{N},{E});
 way["highway"~"^(unclassified|service|path|bridleway)$"]["surface"~"^(unpaved|gravel|fine_gravel|compacted|dirt|ground|earth)$"]({S},{W},{N},{E});
 way["tracktype"]({S},{W},{N},{E});
 way["4wd_only"="yes"]({S},{W},{N},{E}););
out geom tags;"""

Q_ROAD=f"""[out:json][timeout:180];
(way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]({S},{W},{N},{E}););
out geom tags;"""

def ways_of(js):
    return [el for el in js.get("elements",[]) if el.get("type")=="way" and el.get("geometry") and len(el["geometry"])>=2]

def hav(a,b):
    R=6371000.0; la1,lo1,la2,lo2=map(math.radians,[a[1],a[0],b[1],b[0]])
    h=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))
def llen(cs): return sum(hav(cs[i],cs[i+1]) for i in range(len(cs)-1))

t0=time.time()
off=ways_of(ask(Q_OFF)); print(f"offroad: {len(off)} way")
road=ways_of(ask(Q_ROAD)); print(f"strade:  {len(road)} way  ({time.time()-t0:.0f}s)")

off_lines=[LineString([(p["lon"],p["lat"]) for p in el["geometry"]]) for el in off]
road_lines=[LineString([(p["lon"],p["lat"]) for p in el["geometry"]]) for el in road]

def key(pt): return (round(pt[0],6),round(pt[1],6))
def build_graph(lines):
    merged=unary_union(lines)
    segs=list(merged.geoms) if merged.geom_type=="MultiLineString" else [merged]
    G=nx.Graph()
    for s in segs:
        cs=list(s.coords)
        if len(cs)<2: continue
        a,b=key(cs[0]),key(cs[-1])
        if a==b: continue
        L=llen(cs)
        if G.has_edge(a,b) and G[a][b]["length_m"]<=L: continue
        G.add_edge(a,b,length_m=L,coords=cs)
    return G,segs

# --- baseline offroad-only per scegliere A e B in due isole diverse ---
Goff,_=build_graph(off_lines)
comps_off=sorted(nx.connected_components(Goff),key=lambda c:sum(Goff.subgraph(c).edges[e]['length_m'] for e in Goff.subgraph(c).edges),reverse=True)
def rep(c):  # nodo centrale-ish: il piu lontano dal centroide opposto, semplice: primo
    return next(iter(c))
A=rep(comps_off[0]); B=rep(comps_off[1])
print(f"A in isola#1, B in isola#2 (in offroad-only erano SCOLLEGATE)")

# --- grafo unificato ---
all_lines=off_lines+road_lines
tree=STRtree(off_lines)
merged=unary_union(all_lines)
segs=list(merged.geoms) if merged.geom_type=="MultiLineString" else [merged]
G=nx.Graph()
for s in segs:
    cs=list(s.coords)
    if len(cs)<2: continue
    a,b=key(cs[0]),key(cs[-1])
    if a==b: continue
    mid=Point(cs[len(cs)//2])
    idx=tree.query_nearest(mid)
    d=off_lines[int(idx[0] if hasattr(idx,'__len__') else idx)].distance(mid)
    kind="offroad" if d<1e-7 else "road"
    L=llen(cs)
    if G.has_edge(a,b):
        if G[a][b]["length_m"]<=L: continue
    G.add_edge(a,b,length_m=L,coords=cs,kind=kind)
print(f"Grafo unificato: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi")

comps=sorted(nx.connected_components(G),key=len,reverse=True)
def clen(c):
    sg=G.subgraph(c); return sum(d["length_m"] for _,_,d in sg.edges(data=True))
tot_km=sum(d["length_m"] for _,_,d in G.edges(data=True))/1000
big_km=clen(comps[0])/1000
off_km=sum(d["length_m"] for _,_,d in G.edges(data=True) if d["kind"]=="offroad")/1000
road_km=tot_km-off_km
print(f"\n== CONNETTIVITA (unificato) ==")
print(f"Componenti: {len(comps)} | piu grande: {len(comps[0])} nodi, {big_km:.0f} km ({100*big_km/tot_km:.1f}%)")
print(f"Composizione rete: offroad {off_km:.0f} km, asfalto {road_km:.0f} km")

# snap A,B a nodi del grafo unificato
nodes=list(G.nodes())
def nearest(pt):
    return min(nodes,key=lambda n:hav(n,pt))
A2=nearest(A); B2=nearest(B)
same=any(A2 in c and B2 in c for c in comps)
print(f"A e B nella stessa componente ora? {'SI' if same else 'NO'}")

# route con peso 'preferisci offroad'
def w(u,v,d): return d["length_m"]*(1.0 if d["kind"]=="offroad" else ASPHALT_PENALTY)
path=nx.shortest_path(G,A2,B2,weight=w)
# metriche reali
rc=[]; km_off=0.0; km_road=0.0
for u,v in zip(path,path[1:]):
    d=G[u][v]; cs=d["coords"]
    if key(cs[0])!=u: cs=cs[::-1]
    if rc and rc[-1]==cs[0]: rc.extend(cs[1:])
    else: rc.extend(cs)
    if d["kind"]=="offroad": km_off+=d["length_m"]/1000
    else: km_road+=d["length_m"]/1000
tot=km_off+km_road
print(f"\n== PERCORSO A->B (preferisci offroad, asfalto x{ASPHALT_PENALTY}) ==")
print(f"Totale {tot:.1f} km | offroad {km_off:.1f} km ({100*km_off/tot:.0f}%) | asfalto {km_road:.1f} km ({100*km_road/tot:.0f}%)")

# GPX
pts="".join(f'<trkpt lat="{la}" lon="{lo}"></trkpt>' for lo,la in rc)
open("/sessions/compassionate-gifted-goldberg/mnt/outputs/sassello_route_step2.gpx","w").write(
 '<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="Campera Routing POC">'
 f'<trk><name>Sassello A-B offroad+asfalto</name><trkseg>{pts}</trkseg></trk></gpx>')

# mappa
off_f=[{"type":"Feature","properties":{"k":"offroad"},"geometry":{"type":"LineString","coordinates":d["coords"]}} for _,_,d in G.edges(data=True) if d["kind"]=="offroad"]
road_f=[{"type":"Feature","properties":{"k":"road"},"geometry":{"type":"LineString","coordinates":d["coords"]}} for _,_,d in G.edges(data=True) if d["kind"]=="road"]
route_f=[{"type":"Feature","properties":{"route":1},"geometry":{"type":"LineString","coordinates":rc}}]
ab=[{"type":"Feature","properties":{"pt":"A"},"geometry":{"type":"Point","coordinates":[A2[0],A2[1]]}},
    {"type":"Feature","properties":{"pt":"B"},"geometry":{"type":"Point","coordinates":[B2[0],B2[1]]}}]
import os
html=open("/sessions/compassionate-gifted-goldberg/mnt/outputs/sassello_map.html").read().split("var data=")[0]  # reuse head/style
html='''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Sassello unificato (Step 2)</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#map{height:100%;margin:0}.legend{background:#fff;padding:8px 10px;font:13px sans-serif;line-height:1.6;box-shadow:0 1px 4px rgba(0,0,0,.3);border-radius:6px}.sw{display:inline-block;width:14px;height:4px;vertical-align:middle;margin-right:6px}</style>
</head><body><div id="map"></div><script>
var data=__DATA__;var map=L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'OSM'}).addTo(map);
L.geoJSON({type:'FeatureCollection',features:data.road},{style:{color:'#3B8BD4',weight:1.3,opacity:.5}}).addTo(map);
L.geoJSON({type:'FeatureCollection',features:data.off},{style:{color:'#854F0B',weight:1.6,opacity:.7}}).addTo(map);
var r=L.geoJSON({type:'FeatureCollection',features:data.route},{style:{color:'#C0392B',weight:5,opacity:.95}}).addTo(map);
data.ab.forEach(function(f){L.marker([f.geometry.coordinates[1],f.geometry.coordinates[0]]).addTo(map).bindTooltip(f.properties.pt,{permanent:true});});
map.fitBounds(r.getBounds().pad(0.4));
var lg=L.control({position:'topright'});lg.onAdd=function(){var d=L.DomUtil.create('div','legend');d.innerHTML='<b>Sassello - grafo unificato</b><br><span class="sw" style="background:#854F0B"></span>sterrato (offroad)<br><span class="sw" style="background:#3B8BD4"></span>strade asfaltate<br><span class="sw" style="background:#C0392B"></span>percorso A-B (cuce le 2 isole)';return d;};lg.addTo(map);
</script></body></html>'''
payload=json.dumps({"off":off_f,"road":road_f,"route":route_f,"ab":ab})
open("/sessions/compassionate-gifted-goldberg/mnt/outputs/sassello_map_step2.html","w").write(html.replace("__DATA__",payload))

summary=dict(offroad_ways=len(off),road_ways=len(road),nodes=G.number_of_nodes(),edges=G.number_of_edges(),
  components=len(comps),big_pct=round(100*big_km/tot_km,1),net_off_km=round(off_km),net_road_km=round(road_km),
  AB_connected=same,route_tot_km=round(tot,1),route_off_pct=round(100*km_off/tot),route_road_pct=round(100*km_road/tot))
open("/sessions/compassionate-gifted-goldberg/mnt/outputs/sassello_step2_summary.json","w").write(json.dumps(summary,indent=2))
print("\nFile: sassello_route_step2.gpx, sassello_map_step2.html, sassello_step2_summary.json")
