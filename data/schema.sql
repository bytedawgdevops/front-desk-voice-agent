-- Kestrel Community Recreation — database schema
-- SQLite 3.  Populate with:  python -m data.seed
-- Applications must run:     PRAGMA foreign_keys = ON

-- -------------------------------------------------------------------------
-- Core
-- -------------------------------------------------------------------------

CREATE TABLE centres (
    id      INTEGER PRIMARY KEY,
    name    TEXT    NOT NULL,
    type    TEXT    NOT NULL
                CHECK (type IN ('recreation_aquatic','oshc','gymnastics','head_office')),
    suburb  TEXT    NOT NULL,
    address TEXT    NOT NULL,
    phone   TEXT    NOT NULL
);

-- One row per physical facility at a centre.
-- closure_month_start / closure_month_end (1–12, inclusive): months during
-- which the facility does not operate.  NULL on both = open all year.
-- The two outdoor pools carry closure_month_start=5, closure_month_end=9.
CREATE TABLE facilities (
    id                  INTEGER PRIMARY KEY,
    centre_id           INTEGER NOT NULL REFERENCES centres(id),
    name                TEXT    NOT NULL,
    closure_month_start INTEGER,
    closure_month_end   INTEGER
);

-- Opening hours per facility per day.  An absent row means closed that day.
CREATE TABLE facility_hours (
    id          INTEGER PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES facilities(id),
    day_of_week TEXT    NOT NULL
                    CHECK (day_of_week IN
                       ('Monday','Tuesday','Wednesday','Thursday',
                        'Friday','Saturday','Sunday')),
    open_time   TEXT    NOT NULL,   -- HH:MM
    close_time  TEXT    NOT NULL    -- HH:MM
);

-- -------------------------------------------------------------------------
-- Programs
-- -------------------------------------------------------------------------

CREATE TABLE programs (
    id                  INTEGER PRIMARY KEY,
    centre_id           INTEGER NOT NULL REFERENCES centres(id),
    name                TEXT    NOT NULL,
    program_type        TEXT    NOT NULL
                            CHECK (program_type IN ('swim_lessons','oshc','gymnastics')),
    age_min             INTEGER,            -- NULL = no lower bound
    age_max             INTEGER,            -- NULL = no upper bound
    price_per_session   REAL    NOT NULL,
    description         TEXT    NOT NULL,
    next_intake         TEXT,               -- ISO 8601 date; NULL = enquire
    day_of_week         TEXT,               -- e.g. 'Saturday' or 'Monday, Wednesday'
    start_time          TEXT,               -- HH:MM
    duration_minutes    INTEGER
);

-- -------------------------------------------------------------------------
-- Logging
-- -------------------------------------------------------------------------

-- Every turn of every conversation.
CREATE TABLE call_log (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT    NOT NULL,
    turn        INTEGER NOT NULL,
    role        TEXT    NOT NULL CHECK (role IN ('user','assistant','tool')),
    content     TEXT    NOT NULL,
    tool_name   TEXT,               -- set when role = 'tool'
    tool_input  TEXT,               -- JSON
    created_at  TEXT    NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- Messages taken by the receptionist via take_message().
CREATE TABLE messages (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    phone       TEXT    NOT NULL,
    centre_id   INTEGER REFERENCES centres(id),
    topic       TEXT    NOT NULL,
    message     TEXT    NOT NULL,
    delivered   INTEGER NOT NULL DEFAULT 0,     -- reserved for message delivery; nothing currently sets it
    created_at  TEXT    NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- -------------------------------------------------------------------------
-- Indexes
-- -------------------------------------------------------------------------

CREATE INDEX idx_facilities_centre       ON facilities     (centre_id);
CREATE INDEX idx_facility_hours_facility ON facility_hours (facility_id);
CREATE INDEX idx_programs_centre         ON programs       (centre_id);
CREATE INDEX idx_programs_type           ON programs       (program_type);
CREATE INDEX idx_call_log_session        ON call_log       (session_id);
CREATE INDEX idx_messages_centre         ON messages       (centre_id);
CREATE INDEX idx_messages_delivered      ON messages       (delivered);
