#!/usr/bin/env python3
"""Carica il grafo pre-costruito sul microservizio (una volta sola).

Comprime `sassello_graph.json` in gzip e lo invia a POST /v1/admin/load-graph,
che lo scrive sul volume Railway. Dopo, /v1/route e attivo.

Uso:
  python3 upload_graph.py <BASE_URL> <API_KEY> [percorso_grafo]
Esempio:
  python3 upload_graph.py https://campera-offroad.up.railway.app LA_TUA_KEY
"""
import sys, os, gzip, urllib.request

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    base = sys.argv[1].rstrip("/")
    key = sys.argv[2]
    path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(__file__), "sassello_graph.json")
    raw = open(path, "rb").read()
    body = gzip.compress(raw)
    print(f"Grafo {len(raw)/1e6:.1f} MB -> gzip {len(body)/1e6:.1f} MB. Invio a {base} ...")
    req = urllib.request.Request(
        f"{base}/v1/admin/load-graph?gzipped=1",
        data=body, method="POST",
        headers={"X-API-Key": key, "Content-Type": "application/octet-stream"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        print("Risposta:", r.status, r.read().decode())

if __name__ == "__main__":
    main()
