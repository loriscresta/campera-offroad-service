import json,math,pickle,itertools
import networkx as nx
G=pickle.load(open("graph3.pkl","rb"))
elev=json.load(open("elevOT.json"))
def k(n): return f"{n[0]:.6f},{n[1]:.6f}"
def hav(a,b):
    R=6371000.0; la1,lo1,la2,lo2=map(math.radians,[a[1],a[0],b[1],b[0]])
    h=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))
# grade per edge
for u,v,d in G.edges(data=True):
    eu=elev.get(k(u)); ev=elev.get(k(v))
    d["z_u"]=eu; d["z_v"]=ev
    d["grade"]=abs((ev-eu))/max(d["length_m"],1)*100 if (eu is not None and ev is not None) else 0.0

big=max(nx.connected_components(G),key=len)
Gb=G.subgraph(big).copy()
BIG=1e7
def camper_w(u,v,d):
    if d["diff"]=="solo_4x4": return d["length_m"]*BIG
    g=d["grade"]
    if g<8: gp=1.0
    elif g<12: gp=2.0
    elif g<18: gp=5.0
    else: gp=20.0
    dp={"impegnativo":2.0,"medio":1.3,"facile":1.0,"road":1.0}[d["diff"]]
    return d["length_m"]*gp*dp
def jeep_w(u,v,d):
    g=d["grade"]
    gp=0.7 if g>15 else (0.85 if g>8 else 1.0)
    dp={"solo_4x4":0.6,"impegnativo":0.7,"medio":0.9,"facile":1.0,"road":4.0}[d["diff"]]
    return d["length_m"]*gp*dp

def route(A,B,w):
    path=nx.shortest_path(Gb,A,B,weight=w)
    edges=[]; coords=[]; km=0; off=0; s4=0; asc=0; mg=0
    for u,v in zip(path,path[1:]):
        d=Gb[u][v]; edges.append((u,v))
        cs=d["coords"]; 
        if (round(cs[0][0],6),round(cs[0][1],6))!=u: cs=cs[::-1]
        if coords and coords[-1]==cs[0]: coords.extend(cs[1:])
        else: coords.extend(cs)
        km+=d["length_m"]/1000
        if d["kind"]=="offroad": off+=d["length_m"]/1000
        if d["diff"]=="solo_4x4": s4+=d["length_m"]/1000
        if d["z_u"] is not None and d["z_v"] is not None:
            asc+=max(0,d["z_v"]-d["z_u"]) if path.index(v)>path.index(u) else max(0,d["z_u"]-d["z_v"])
        mg=max(mg,d["grade"])
    return dict(path=path,edges=set(map(frozenset,edges)),coords=coords,km=km,off=off,s4=s4,asc=asc,mg=mg)

# candidate A/B: estremi del big component
nodes=list(Gb.nodes())
corners={
 "SW":min(nodes,key=lambda n:n[0]+n[1]), "NE":max(nodes,key=lambda n:n[0]+n[1]),
 "NW":min(nodes,key=lambda n:n[0]-n[1]), "SE":max(nodes,key=lambda n:n[0]-n[1]),
}
pairs=[("SW","NE"),("NW","SE"),("SW","SE"),("NW","NE")]
best=None
for an,bn in pairs:
    A,B=corners[an],corners[bn]
    try:
        rc=route(A,B,camper_w); rj=route(A,B,jeep_w)
    except nx.NetworkXNoPath: continue
    inter=len(rc["edges"]&rj["edges"]); uni=len(rc["edges"]|rj["edges"])
    jac=1-inter/uni if uni else 0
    score=jac
    print(f"{an}->{bn}: divergenza {jac*100:.0f}% | camper {rc['km']:.1f}km off{100*rc['off']/rc['km']:.0f}% asc{rc['asc']:.0f}m maxg{rc['mg']:.0f}% | jeep {rj['km']:.1f}km off{100*rj['off']/rj['km']:.0f}% s4x4 {rj['s4']:.1f}km asc{rj['asc']:.0f}m maxg{rj['mg']:.0f}%")
    if best is None or score>best[0]: best=(score,an,bn,A,B,rc,rj)

score,an,bn,A,B,rc,rj=best
print(f"\nSCELTA: {an}->{bn} (divergenza {score*100:.0f}%)")
json.dump(dict(an=an,bn=bn,A=list(A),B=list(B),
  camper=dict(km=rc["km"],offpct=100*rc["off"]/rc["km"],asc=rc["asc"],maxg=rc["mg"],s4=rc["s4"]),
  jeep=dict(km=rj["km"],offpct=100*rj["off"]/rj["km"],asc=rj["asc"],maxg=rj["mg"],s4=rj["s4"]),
  divergence=score), open("profiles_result.json","w"),indent=2)
# salva coords per mappa/gpx
json.dump(dict(camper=rc["coords"],jeep=rj["coords"],A=list(A),B=list(B)),open("profiles_routes.json","w"))
print("ok")
