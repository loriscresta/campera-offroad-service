"""Campera routing (fase 2 - pilota) — Dijkstra su grafo pre-costruito.

Tutto il lavoro pesante (Overpass, noding, quota, pendenza) e fatto OFFLINE in
`routing_poc/build_routing_graph.py`, che esporta un grafo JSON. Qui carichiamo
quel grafo e instradiamo in PURO Python (nessuna dipendenza esterna): il
microservizio resta leggero.

Profili veicolo (cost model):
  - "camper": evita pendenze forti e tratti solo-4x4, ok asfalto per collegare.
  - "jeep":   cerca sterrato/tecnico, usa asfalto solo al minimo.

Il grafo (`sassello_graph.json`) NON e nel deploy: finche non e presente,
l'endpoint risponde 501 e il servizio live resta invariato.
"""
import os, json, math, heapq

_GRAPH = None
_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "routing_poc", "sassello_graph.json")

# diff string -> codice (gli archi 'road' hanno kind=1)
def _camper_factor(grade, diff):
    if diff == "solo_4x4":
        return 1e7
    if grade < 8: gp = 1.0
    elif grade < 12: gp = 2.0
    elif grade < 18: gp = 5.0
    else: gp = 20.0
    dp = {"impegnativo": 2.0, "medio": 1.3, "facile": 1.0, "road": 1.0}.get(diff, 1.5)
    return gp * dp

def _jeep_factor(grade, diff):
    gp = 0.7 if grade > 15 else (0.85 if grade > 8 else 1.0)
    dp = {"solo_4x4": 0.6, "impegnativo": 0.7, "medio": 0.9, "facile": 1.0, "road": 4.0}.get(diff, 1.0)
    return gp * dp

PROFILES = {"camper": _camper_factor, "jeep": _jeep_factor}

def vehicle_to_profile(vehicle: str) -> str:
    v = (vehicle or "").lower()
    if v in ("camper_4x4", "jeep", "4x4", "offroad"):
        return "jeep"
    return "camper"  # van, camper, default

def _haversine(a, b):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, [a[1], a[0], b[1], b[0]])
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))


class RoutingGraph:
    def __init__(self, data):
        self.nodes = data["nodes"]          # [[lon,lat,z], ...]
        self.edges = data["edges"]          # [[a,b,len,grade,kind,diff,coords], ...]
        self.meta = data.get("meta", {})
        self.adj = {}
        for ei, e in enumerate(self.edges):
            a, b = e[0], e[1]
            self.adj.setdefault(a, []).append((b, ei))
            self.adj.setdefault(b, []).append((a, ei))

    def nearest(self, lon, lat):
        best, bd = None, None
        p = (lon, lat)
        for i, n in enumerate(self.nodes):
            d = (n[0]-lon)**2 + (n[1]-lat)**2
            if bd is None or d < bd:
                bd, best = d, i
        return best

    def _dijkstra(self, src, dst, factor):
        dist = {src: 0.0}
        prev = {}
        pq = [(0.0, src)]
        while pq:
            du, u = heapq.heappop(pq)
            if u == dst:
                break
            if du > dist.get(u, float("inf")):
                continue
            for v, ei in self.adj.get(u, ()):
                e = self.edges[ei]
                w = e[2] * factor(e[3], e[5])
                nd = du + w
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    prev[v] = (u, ei)
                    heapq.heappush(pq, (nd, v))
        if dst not in prev and dst != src:
            return None
        # ricostruzione nodi+archi
        path_nodes = [dst]; path_edges = []
        cur = dst
        while cur != src:
            u, ei = prev[cur]
            path_edges.append(ei); path_nodes.append(u); cur = u
        path_nodes.reverse(); path_edges.reverse()
        return path_nodes, path_edges

    def route(self, points, profile="camper"):
        """points: lista di [lon,lat] (>=2). Concatena i tratti A->w..->B."""
        factor = PROFILES.get(profile, _camper_factor)
        snapped = [self.nearest(p[0], p[1]) for p in points]
        all_nodes, all_edges = [], []
        for a, b in zip(snapped, snapped[1:]):
            if a == b:
                continue
            r = self._dijkstra(a, b, factor)
            if r is None:
                return None
            pn, pe = r
            if all_nodes and all_nodes[-1] == pn[0]:
                all_nodes.extend(pn[1:])
            else:
                all_nodes.extend(pn)
            all_edges.extend(pe)
        return self._assemble(all_nodes, all_edges)

    def _assemble(self, path_nodes, path_edges):
        coords = []
        km = off = asc = mg = 0.0
        comp = {}
        for k, ei in enumerate(path_edges):
            e = self.edges[ei]
            a = path_nodes[k]
            cs = e[6]
            # orienta la geometria per prossimita al nodo di partenza: robusto
            # all'ordine dei nodi di networkx (non orientato), che puo' essere
            # invertito rispetto alla geometria e creare salti rettilinei.
            na = self.nodes[a]
            d0 = (cs[0][0]-na[0])**2 + (cs[0][1]-na[1])**2
            d1 = (cs[-1][0]-na[0])**2 + (cs[-1][1]-na[1])**2
            if d1 < d0:
                cs = cs[::-1]
            if coords and coords[-1] == cs[0]:
                coords.extend(cs[1:])
            else:
                coords.extend(cs)
            L = e[2]; km += L/1000.0
            if e[4] == 0: off += L/1000.0
            comp[e[5]] = comp.get(e[5], 0.0) + L/1000.0
            mg = max(mg, e[3])
        # dislivello positivo lungo i nodi
        for a, b in zip(path_nodes, path_nodes[1:]):
            za, zb = self.nodes[a][2], self.nodes[b][2]
            if za is not None and zb is not None and zb > za:
                asc += zb - za
        summary = {
            "distance_km": round(km, 1),
            "offroad_pct": round(100*off/km) if km else 0,
            "ascent_m": round(asc),
            "max_grade_pct": round(mg),
            "by_difficulty_km": {k: round(v, 1) for k, v in comp.items()},
        }
        return {"coords": coords, "summary": summary}


def graph_path():
    """Percorso del grafo: ROUTING_GRAPH (es. /data/sassello_graph.json sul
    volume Railway) oppure il default locale del pilota."""
    return os.environ.get("ROUTING_GRAPH", _DEFAULT)


def reset_graph():
    global _GRAPH
    _GRAPH = None


def get_graph(path=None):
    """Carica (una volta) il grafo. Solleva FileNotFoundError se assente."""
    global _GRAPH
    if _GRAPH is None:
        p = path or graph_path()
        with open(p, encoding="utf-8") as f:
            _GRAPH = RoutingGraph(json.load(f))
    return _GRAPH


def save_graph(raw: bytes, gzipped: bool = False):
    """Scrive il grafo nel percorso configurato (volume) e lo ricarica.

    Permette di caricare l'artefatto una volta sola via endpoint admin, senza
    metterlo in git. `gzipped`=True se il body e compresso gzip (trasferimento
    piu leggero)."""
    import gzip as _gz
    p = graph_path()
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    data = _gz.decompress(raw) if gzipped else raw
    json.loads(data)  # valida che sia JSON prima di scrivere
    with open(p, "wb") as f:
        f.write(data)
    reset_graph()
    return get_graph()


def to_gpx(coords, name="Campera route"):
    pts = "".join(f'<trkpt lat="{lat}" lon="{lon}"></trkpt>' for lon, lat in coords)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<gpx version="1.1" creator="Campera Routing">'
            f"<trk><name>{name}</name><trkseg>{pts}</trkseg></trk></gpx>")
