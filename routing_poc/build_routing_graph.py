import json,pickle
import networkx as nx
G=pickle.load(open("graph3.pkl","rb")); elev=json.load(open("elevOT.json"))
def k(n): return f"{n[0]:.6f},{n[1]:.6f}"
# usa solo la componente piu grande (rete navigabile)
big=max(nx.connected_components(G),key=len)
Gb=G.subgraph(big).copy()
nodes=list(Gb.nodes())
idx={n:i for i,n in enumerate(nodes)}
node_arr=[[round(n[0],6),round(n[1],6), (round(elev[k(n)],1) if elev.get(k(n)) is not None else None)] for n in nodes]
edges=[]
for u,v,d in Gb.edges(data=True):
    zu=elev.get(k(u)); zv=elev.get(k(v))
    grade=abs(zv-zu)/max(d["length_m"],1)*100 if (zu is not None and zv is not None) else 0.0
    # coords compatte arrotondate
    cs=[[round(x,6),round(y,6)] for x,y in d["coords"]]
    edges.append([idx[u],idx[v],round(d["length_m"],1),round(grade,1),
                  0 if d["kind"]=="offroad" else 1, d["diff"], cs])
out=dict(meta=dict(area="Sassello (SV)", crs="EPSG:4326", elev="eudem25m-25m",
                   nodes=len(node_arr), edges=len(edges)),
         nodes=node_arr, edges=edges)
json.dump(out, open("sassello_graph.json","w"))
import os
print("nodi",len(node_arr),"archi",len(edges),"dim MB", round(os.path.getsize("sassello_graph.json")/1e6,2))
