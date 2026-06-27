#!/usr/bin/env bash
# Importa la rete offroad della zona pilota in PostGIS.
# Prerequisiti: docker compose (per il db), osmium-tool e osm2pgsql installati,
# oppure usa il container helper (vedi note in fondo).
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

: "${BBOX:?Imposta BBOX in .env}"
: "${GEOFABRIK_URL:?Imposta GEOFABRIK_URL in .env}"
: "${POSTGRES_USER:?}"; : "${POSTGRES_DB:?}"; : "${POSTGRES_PASSWORD:?}"

WORK=import/work
mkdir -p "$WORK"
PBF="$WORK/region.osm.pbf"
CLIP="$WORK/pilot.osm.pbf"

echo "==> 1/4 Download estratto Geofabrik"
[ -f "$PBF" ] || curl -L --fail -o "$PBF" "$GEOFABRIK_URL"

echo "==> 2/4 Clip sulla zona pilota ($BBOX)"
# osmium vuole left,bottom,right,top = min_lon,min_lat,max_lon,max_lat (= BBOX)
osmium extract -b "$BBOX" "$PBF" -o "$CLIP" --overwrite

echo "==> 3/4 Import in PostGIS con osm2pgsql (--hstore)"
PGPASSWORD="$POSTGRES_PASSWORD" osm2pgsql \
  --create --slim --hstore --latlong \
  --host "${POSTGRES_HOST:-localhost}" --port "${POSTGRES_PORT:-5432}" \
  --username "$POSTGRES_USER" --database "$POSTGRES_DB" \
  "$CLIP"

echo "==> 4/4 Classificazione difficolta"
PGPASSWORD="$POSTGRES_PASSWORD" psql \
  --host "${POSTGRES_HOST:-localhost}" --port "${POSTGRES_PORT:-5432}" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -f db/02_classify.sql

echo "==> Fatto. Conteggio tratti:"
PGPASSWORD="$POSTGRES_PASSWORD" psql \
  --host "${POSTGRES_HOST:-localhost}" --port "${POSTGRES_PORT:-5432}" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "SELECT difficulty, count(*) FROM offroad_segments GROUP BY difficulty ORDER BY 1;"

# NOTE: se non vuoi installare osmium/osm2pgsql sulla macchina, puoi usarli da
# container, es.:
#   docker run --rm -v "$PWD/import/work":/data ghcr.io/osmcode/osmium-tool \
#     osmium extract -b "$BBOX" /data/region.osm.pbf -o /data/pilot.osm.pbf --overwrite
#   docker run --rm --network host -v "$PWD/import/work":/data iboates/osm2pgsql \
#     osm2pgsql --create --slim --hstore --latlong -H localhost -U "$POSTGRES_USER" \
#     -d "$POSTGRES_DB" /data/pilot.osm.pbf
