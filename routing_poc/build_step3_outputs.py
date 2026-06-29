import json,math,pickle
import networkx as nx
G=pickle.load(open("graph3.pkl","rb")); elev=json.load(open("elevOT.json"))
def k(n): return f"{n[0]:.6f},{n[1]:.6f}"
for u,v,d in G.edges(data=True):
    eu=elev.get(k(u)); ev=elev.get(k(v)); d["z_u"]=eu; d["z_v"]=ev
    d["grade"]=abs(ev-eu)/max(d["length_m"],1)*100 if (eu is not None and ev is not None) else 0.0
big=max(nx.connected_components(G),key=len); Gb=G.subgraph(big).copy()
BIG=1e7
def camper_w(u,v,d):
    if d["diff"]=="solo_4x4": return d["length_m"]*BIG
    g=d["grade"]; gp=1.0 if g<8 else 2.0 if g<12 else 5.0 if g<18 else 20.0
    dp={"impegnativo":2.0,"medio":1.3,"facile":1.0,"road":1.0}[d["diff"]]
    return d["length_m"]*gp*dp
def jeep_w(u,v,d):
    g=d["grade"]; gp=0.7 if g>15 else 0.85 if g>8 else 1.0
    dp={"solo_4x4":0.6,"impegnativo":0.7,"medio":0.9,"facile":1.0,"road":4.0}[d["diff"]]
    return d["length_m"]*gp*dp
nodes=list(Gb.nodes())
A=min(nodes,key=lambda n:n[0]+n[1]); B=max(nodes,key=lambda n:n[0]+n[1])
def run(w):
    p=nx.shortest_path(Gb,A,B,weight=w)
    coords=[]; prof=[]; cum=0; km=0; off=0; s4=0; asc=0; mg=0; comp={"facile":0,"medio":0,"impegnativo":0,"solo_4x4":0,"road":0}
    for idx,(u,v) in enumerate(zip(p,p[1:])):
        d=Gb[u][v]; cs=d["coords"]
        if (round(cs[0][0],6),round(cs[0][1],6))!=u: cs=cs[::-1]
        if coords and coords[-1]==cs[0]: coords.extend(cs[1:])
        else: coords.extend(cs)
        L=d["length_m"]; km+=L/1000; comp[d["diff"]]+=L/1000
        if d["kind"]=="offroad": off+=L/1000
        if d["diff"]=="solo_4x4": s4+=L/1000
        zu,zv=d["z_u"],d["z_v"]
        if zu is not None and zv is not None: asc+=max(0,zv-zu)
        mg=max(mg,d["grade"])
        if idx==0 and zu is not None: prof.append([0,zu])
        cum+=L/1000
        if zv is not None: prof.append([round(cum,2),zv])
    return dict(coords=coords,prof=prof,km=km,off=off,s4=s4,asc=asc,mg=mg,comp=comp)
C=run(camper_w); J=run(jeep_w)

def gpx(coords,name):
    pts="".join(f'<trkpt lat="{la}" lon="{lo}"></trkpt>' for lo,la in coords)
    return ('<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="Campera Routing POC">'
            f'<trk><name>{name}</name><trkseg>{pts}</trkseg></trk></gpx>')
open("sassello_camper.gpx","w").write(gpx(C["coords"],"Sassello A-B profilo CAMPER"))
open("sassello_jeep.gpx","w").write(gpx(J["coords"],"Sassello A-B profilo JEEP 4x4"))

def stat(r): return dict(km=round(r["km"],1),offpct=round(100*r["off"]/r["km"]),asc=round(r["asc"]),maxg=round(r["mg"]),s4=round(r["s4"],1))
summary=dict(A=list(A),B=list(B),camper=stat(C),jeep=stat(J))
json.dump(summary,open("sassello_step3_summary.json","w"),indent=2)

data=dict(camper=C["coords"],jeep=J["coords"],A=list(A),B=list(B),
          cp=C["prof"],jp=J["prof"],cs=stat(C),js=stat(J))
html='''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Sassello - camper vs jeep (Step 3)</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>html,body{margin:0;font-family:sans-serif}#map{height:62vh}#panel{padding:10px 14px}
table{border-collapse:collapse;font-size:14px;margin:6px 0}td,th{border:1px solid #ddd;padding:4px 10px;text-align:right}th{background:#f3f3f1}
.legend{background:#fff;padding:8px 10px;font-size:13px;line-height:1.6;box-shadow:0 1px 4px rgba(0,0,0,.3);border-radius:6px}
.sw{display:inline-block;width:14px;height:4px;vertical-align:middle;margin-right:6px}.cap{display:flex;gap:24px;flex-wrap:wrap}#chart{max-width:640px}</style>
</head><body><div id="map"></div><div id="panel">
<h3 style="margin:.2em 0">Stesso A&rarr;B, due profili veicolo</h3>
<div class="cap"><table id="tab"></table><div style="flex:1;min-width:320px"><canvas id="chart" height="150"></canvas></div></div>
<p style="font-size:13px;color:#555">Quota eudem25m (25 m). Pendenza da quota nodi; in produzione Tinitaly 10 m + campionamento per-vertice.</p>
</div><script>
var data=__DATA__;var map=L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'OSM'}).addTo(map);
var camper=L.geoJSON({type:'Feature',geometry:{type:'LineString',coordinates:data.camper}},{style:{color:'#185FA5',weight:5,opacity:.9}}).addTo(map);
var jeep=L.geoJSON({type:'Feature',geometry:{type:'LineString',coordinates:data.jeep}},{style:{color:'#C0392B',weight:5,opacity:.9}}).addTo(map);
[["A",data.A],["B",data.B]].forEach(function(x){L.marker([x[1][1],x[1][0]]).addTo(map).bindTooltip(x[0],{permanent:true});});
map.fitBounds(jeep.getBounds().extend(camper.getBounds()).pad(0.15));
var lg=L.control({position:'topright'});lg.onAdd=function(){var d=L.DomUtil.create('div','legend');d.innerHTML='<b>Sassello &mdash; profili veicolo</b><br><span class="sw" style="background:#185FA5"></span>camper (evita ripido)<br><span class="sw" style="background:#C0392B"></span>jeep 4x4 (cerca tecnico)';return d;};lg.addTo(map);
var c=data.cs,j=data.js;
document.getElementById('tab').innerHTML=
 '<tr><th></th><th style="color:#185FA5">camper</th><th style="color:#C0392B">jeep 4x4</th></tr>'+
 '<tr><td>distanza</td><td>'+c.km+' km</td><td>'+j.km+' km</td></tr>'+
 '<tr><td>% su sterrato</td><td>'+c.offpct+'%</td><td>'+j.offpct+'%</td></tr>'+
 '<tr><td>dislivello +</td><td>'+c.asc+' m</td><td>'+j.asc+' m</td></tr>'+
 '<tr><td>pendenza max</td><td>'+c.maxg+'%</td><td>'+j.maxg+'%</td></tr>'+
 '<tr><td>km solo 4x4</td><td>'+c.s4+'</td><td>'+j.s4+'</td></tr>';
new Chart(document.getElementById('chart'),{type:'line',data:{datasets:[
 {label:'camper',data:data.cp.map(p=>({x:p[0],y:p[1]})),borderColor:'#185FA5',pointRadius:0,borderWidth:2},
 {label:'jeep 4x4',data:data.jp.map(p=>({x:p[0],y:p[1]})),borderColor:'#C0392B',pointRadius:0,borderWidth:2}]},
 options:{scales:{x:{type:'linear',title:{display:true,text:'km'}},y:{title:{display:true,text:'quota m'}}},plugins:{title:{display:true,text:'Profilo altimetrico'}}}});
</script></body></html>'''
open("sassello_map_step3.html","w").write(html.replace("__DATA__",json.dumps(data)))
print("camper",stat(C)); print("jeep",stat(J)); print("comp camper",{x:round(y,1) for x,y in C['comp'].items()}); print("comp jeep",{x:round(y,1) for x,y in J['comp'].items()})
print("file ok")
