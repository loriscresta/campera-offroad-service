-- Popola offroad_segments dalla tabella importata da osm2pgsql (planet_osm_line).
-- Richiede import con --hstore (i tag non mappati a colonna finiscono in `tags`).
-- Le regole qui devono restare allineate a scripts/seed_overpass.py.

TRUNCATE offroad_segments;

INSERT INTO offroad_segments (
    id, name, surface, tracktype, smoothness, requires_4wd,
    difficulty, suitable_for,
    vehicle_max_width_m, vehicle_max_weight_t, vehicle_max_height_m,
    length_m, confidence, geom
)
SELECT
    'way/' || osm_id,
    name,
    surface,
    tracktype,
    COALESCE(tags->'smoothness', NULL)                       AS smoothness,
    (tags->'4wd_only' = 'yes')                               AS requires_4wd,

    -- Difficolta
    CASE
        WHEN tags->'4wd_only' = 'yes'
          OR tracktype IN ('grade4','grade5')
          OR tags->'smoothness' IN ('very_bad','horrible','very_horrible','impassable')
            THEN 'solo_4x4'
        WHEN tracktype = 'grade3'
          OR surface IN ('dirt','ground','earth')
            THEN 'impegnativo'
        WHEN tracktype = 'grade2'
          OR surface IN ('gravel','fine_gravel')
            THEN 'medio'
        ELSE 'facile'
    END                                                      AS difficulty,

    -- Mezzi idonei
    CASE
        WHEN tags->'4wd_only' = 'yes' OR tracktype IN ('grade4','grade5')
            THEN ARRAY['camper_4x4']
        ELSE ARRAY['van','camper_4x4']
    END                                                      AS suitable_for,

    -- Limiti dimensionali (se presenti)
    NULLIF(regexp_replace(COALESCE(tags->'maxwidth', width), '[^0-9.]', '', 'g'), '')::numeric,
    NULLIF(regexp_replace(tags->'maxweight', '[^0-9.]', '', 'g'), '')::numeric,
    NULLIF(regexp_replace(tags->'maxheight', '[^0-9.]', '', 'g'), '')::numeric,

    ST_Length(way::geography)                               AS length_m,

    -- Confidenza in base ai tag presenti
    CASE
        WHEN tracktype IS NOT NULL AND surface IS NOT NULL THEN 'alta'
        WHEN tracktype IS NOT NULL OR  surface IS NOT NULL THEN 'media'
        ELSE 'bassa'
    END                                                     AS confidence,

    ST_Transform(way, 4326)                                 AS geom
FROM planet_osm_line
WHERE
    highway = 'track'
    OR tracktype IS NOT NULL
    OR tags->'4wd_only' = 'yes'
    OR (highway IN ('unclassified','service','path','bridleway')
        AND surface IN ('unpaved','gravel','fine_gravel','compacted','dirt','ground','earth'))
ON CONFLICT (id) DO NOTHING;

UPDATE offroad_segments
SET warning = 'Dati parziali: verifica le condizioni locali'
WHERE confidence = 'bassa';
