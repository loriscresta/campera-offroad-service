-- Schema PostGIS del Campera Offroad Service
CREATE EXTENSION IF NOT EXISTS postgis;

-- Tabella finale servita dall'API
CREATE TABLE IF NOT EXISTS offroad_segments (
    id                   TEXT PRIMARY KEY,              -- es. 'way/123456789'
    name                 TEXT,
    difficulty           TEXT NOT NULL,                 -- facile|medio|impegnativo|solo_4x4
    surface              TEXT,
    tracktype            TEXT,
    smoothness           TEXT,
    requires_4wd         BOOLEAN NOT NULL DEFAULT FALSE,
    suitable_for         TEXT[] NOT NULL DEFAULT '{}',  -- {van, camper_4x4}
    vehicle_max_width_m  NUMERIC,
    vehicle_max_weight_t NUMERIC,
    vehicle_max_height_m NUMERIC,
    length_m             NUMERIC,
    confidence           TEXT NOT NULL DEFAULT 'media', -- alta|media|bassa
    warning              TEXT,
    geom                 GEOMETRY(LineString, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_offroad_segments_geom ON offroad_segments USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_offroad_segments_diff ON offroad_segments (difficulty);
