import json,math,os,pickle,glob
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
from shapely import STRtree
import networkx as nx
def ways(js): return [e for e in js.get("elements",[]) if e.get("type")=="way" and e.get("geometry") and len(e["geometry"])>=2]
off=ways(json.load(open("raw_off.json")))
roads={}
for fn in glob.glob("rt_*.json"):
    for e in ways(json.load(open(fn))): roads[e["id"]]=e
road=list(roads.values())
print("offroad",len(off),"road(unici)",len(road))
def classify(t):
    tr,sf,sm=t.get("tracktype"),t.get("surface"),t.get("smoothness"); f=t.get("4wd_only")=="yes"
    if f or tr in("grade4","grade5") or sm in("very_bad","horrible","very_horrible","impassable"): return "solo_4x4"
    if tr=="grade3" or sf in("dirt","ground","earth"): return "impegnativo"
    if tr=="grade2" or sf in("gravel","fine_gravel"): return "medio"
    return "facile"
off_lines=[LineString([(p["lon"],p["lat"]) for p in e["geometry"]]) for e in off]
off_diff=[classify(e.get("tags",{})) for e in off]
road_lines=[LineString([(p["lon"],p["lat"]) for p in e["geometry"]]) for e in road]
def hav(a,b):
    R=6371000.0; la1,lo1,la2,lo2=map(math.radians,[a[1],a[0],b[1],b[0]])
    h=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))
def llen(cs): return sum(hav(cs[i],cs[i+1]) for i in range(len(cs)-1))
def key(p): return (round(p[0],6),round(p[1],6))
tree=STRtree(off_lines)
merged=unary_union(off_lines+road_lines)
segs=list(merged.geoms) if merged.geom_type=="MultiLineString" else [merged]
G=nx.Graph()
for s in segs:
    cs=list(s.coords)
    if len(cs)<2: continue
    a,b=key(cs[0]),key(cs[-1])
    if a==b: continue
    mid=Point(cs[len(cs)//2]); i=int(tree.query_nearest(mid)[0]); d=off_lines[i].distance(mid)
    if d<1e-7: kind,diff="offroad",off_diff[i]
    else: kind,diff="road","road"
    L=llen(cs)
    if G.has_edge(a,b) and G[a][b]["length_m"]<=L: continue
    G.add_edge(a,b,length_m=L,coords=cs,kind=kind,diff=diff)
pickle.dump(G,open("graph3.pkl","wb"))
json.dump(list(G.nodes()),open("nodes3.json","w"))
import networkx as nx2
comps=sorted(nx.connected_components(G),key=len,reverse=True)
print("grafo",G.number_of_nodes(),"nodi",G.number_of_edges(),"archi |componenti",len(comps),"|big",len(comps[0]))
