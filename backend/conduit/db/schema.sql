-- SPDX-License-Identifier: MIT
CREATE TABLE IF NOT EXISTS events (
    id                  TEXT PRIMARY KEY,
    timestamp           TEXT NOT NULL,
    destination         TEXT NOT NULL,
    user_pseudo_id      TEXT NOT NULL,
    page_title          TEXT,
    trigger             TEXT NOT NULL DEFAULT 'paste',
    char_count          INTEGER NOT NULL DEFAULT 0,

    decision            TEXT NOT NULL CHECK (decision IN ('allow','redact','block')),
    lt_rule             TEXT,
    lt_action           TEXT,

    severity            TEXT NOT NULL DEFAULT 'low',
    categories_json     TEXT NOT NULL DEFAULT '[]',
    classification_json TEXT NOT NULL DEFAULT '{}',
    regulatory_json     TEXT NOT NULL DEFAULT '[]',

    prompt_excerpt      TEXT NOT NULL,
    sanitized_excerpt   TEXT,
    audit_message       TEXT,

    override_applied    INTEGER NOT NULL DEFAULT 0,

    -- Multimodal: when the source paste was an image, these fields are populated.
    is_image            INTEGER NOT NULL DEFAULT 0,
    image_mime          TEXT,
    image_ui_type       TEXT,
    image_analysis_json TEXT,

    -- Thinking-mode reasoning trace (Gemini 2.5 Pro thinking output).
    reasoning_json      TEXT,

    -- Embedding vector (base64-encoded float32 array) for similarity search.
    embedding_blob      TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp   ON events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_decision    ON events (decision);
CREATE INDEX IF NOT EXISTS idx_events_severity    ON events (severity);
CREATE INDEX IF NOT EXISTS idx_events_destination ON events (destination);
