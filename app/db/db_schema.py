"""
db_schema.py
============
SQLite database schema and connection manager for the meeting extraction pipeline.

Design
------
One database file. One meetings table as the root entity.
Every child table (attendees, action_items, decisions, blockers, ambiguous)
references meetings.id via a foreign key with ON DELETE CASCADE.

This means:
- All meetings share the same tables — no data duplication, no file sprawl
- Each row in every child table is stamped with meeting_id
- All reads are filtered by meeting_id — data from different meetings never mixes
- Deleting a meeting row cascades and removes ALL its child rows automatically

New functions vs original
--------------------------
+ list_meeting_dbs()       : Returns metadata for every stored meeting (for UI dropdown)
+ delete_meeting_db()      : Deletes a meeting and all its data via CASCADE
+ Added meeting_id indexes on every child table for fast per-meeting queries

Usage
-----
    from app.db.db_schema import initialise_db, get_connection, list_meeting_dbs

    initialise_db()
    conn = get_connection()
    meetings = list_meeting_dbs()
"""
import logging
import sqlite3
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "database" / "meetings.db"

logger = logging.getLogger(__name__)


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    """
    Return a new SQLite connection with row factory and foreign key support enabled.

    IMPORTANT: foreign_keys = ON must be set on every connection — SQLite does not
    persist this setting. Without it, ON DELETE CASCADE will silently not fire.

    Args:
        db_path: Path to the SQLite database file. Defaults to meetings.db.

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout = 30)
    conn.row_factory = sqlite3.Row           # Access columns by name: row["title"]
    conn.execute("PRAGMA foreign_keys = ON") # Required for CASCADE to work
    conn.execute("PRAGMA journal_mode = WAL") # Better concurrent read performance
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
    -- Root entity: one row per meeting
    -- Every child table references this id as a foreign key
    CREATE TABLE IF NOT EXISTS meetings (
        id          TEXT PRIMARY KEY,               -- uuid-based: "meet_2026_05_29_a3f7c1"
        date        TEXT NOT NULL,                  -- ISO 8601: "2026-05-29"
        title       TEXT,                           -- Inferred short title
        created_at  TEXT DEFAULT (datetime('now'))  -- Insertion timestamp
    );

    -- Participants: one row per person per meeting
    CREATE TABLE IF NOT EXISTS attendees (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id  TEXT NOT NULL,
        name        TEXT NOT NULL,
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
    );

    -- Tasks and commitments: id is scoped to meeting (task_001 per meeting, not globally)
    CREATE TABLE IF NOT EXISTS action_items (
        id              TEXT NOT NULL,
        meeting_id      TEXT NOT NULL,
        title           TEXT NOT NULL,
        owner           TEXT,
        due_date        TEXT,
        priority        TEXT CHECK(priority IN ('high', 'medium', 'low')),
        status          TEXT CHECK(status IN ('open', 'on_hold', 'blocked')),
        missing_fields  TEXT,
        note            TEXT,
        PRIMARY KEY (id, meeting_id),               -- Composite PK: id is unique per meeting
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
    );

    -- Decisions: composite PK scopes id to meeting
    CREATE TABLE IF NOT EXISTS decisions (
        id              TEXT NOT NULL,
        meeting_id      TEXT NOT NULL,
        decision        TEXT NOT NULL,
        rationale       TEXT,
        status          TEXT CHECK(status IN ('confirmed', 'deferred', 'pending')),
        missing_fields  TEXT,
        note            TEXT,
        PRIMARY KEY (id, meeting_id),
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
    );

    -- Blockers: composite PK scopes id to meeting
    CREATE TABLE IF NOT EXISTS blockers (
        id              TEXT NOT NULL,
        meeting_id      TEXT NOT NULL,
        task            TEXT NOT NULL,
        blocked_by      TEXT NOT NULL,
        owner           TEXT,
        ticket          TEXT,
        missing_fields  TEXT,
        PRIMARY KEY (id, meeting_id),
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
    );

    -- Ambiguous items: composite PK scopes id to meeting
    CREATE TABLE IF NOT EXISTS ambiguous (
        id          TEXT NOT NULL,
        meeting_id  TEXT NOT NULL,
        description TEXT NOT NULL,
        owner       TEXT,
        note        TEXT,
        PRIMARY KEY (id, meeting_id),
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
    );

    -- Indexes on meeting_id for every child table (fast per-meeting reads)
    CREATE INDEX IF NOT EXISTS idx_attendees_meeting     ON attendees(meeting_id);
    CREATE INDEX IF NOT EXISTS idx_action_items_meeting  ON action_items(meeting_id);
    CREATE INDEX IF NOT EXISTS idx_decisions_meeting     ON decisions(meeting_id);
    CREATE INDEX IF NOT EXISTS idx_blockers_meeting      ON blockers(meeting_id);
    CREATE INDEX IF NOT EXISTS idx_ambiguous_meeting     ON ambiguous(meeting_id);

    -- Indexes for common filter queries
    CREATE INDEX IF NOT EXISTS idx_action_items_owner    ON action_items(owner);
    CREATE INDEX IF NOT EXISTS idx_action_items_status   ON action_items(status);
    CREATE INDEX IF NOT EXISTS idx_action_items_due_date ON action_items(due_date);
    CREATE INDEX IF NOT EXISTS idx_blockers_owner        ON blockers(owner);
    CREATE INDEX IF NOT EXISTS idx_decisions_status      ON decisions(status);
"""


# ── Initialisation ────────────────────────────────────────────────────────────

def initialise_db(db_path: str | Path = DB_PATH) -> None:
    """
    Create all tables and indexes if they do not already exist.
    Safe to call on every application startup.

    Args:
        db_path: Path to the SQLite database file. Defaults to meetings.db.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        logger.info("Database initialised at %s", db_path)
    except sqlite3.Error as e:
        logger.error("Failed to initialise database: %s", e)
        raise
    finally:
        conn.close()


# ── List all meetings ─────────────────────────────────────────────────────────

def list_meeting_dbs(db_path: str | Path = DB_PATH) -> list[dict]:
    """
    Return metadata for every meeting stored in the database, newest first.

    Used by:
    - The UI dropdown to populate the meetings list
    - The notification engine to iterate over all meetings

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of dicts: [{id, date, title}], sorted by date DESC then created_at DESC.
        Returns empty list if the database does not exist yet.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    try:
        conn = get_connection(db_path)
        rows = conn.execute(
            "SELECT id, date, title FROM meetings ORDER BY date DESC, created_at DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error("Failed to list meetings: %s", e)
        return []


# ── Delete one meeting ────────────────────────────────────────────────────────

def delete_meeting_db(meeting_id: str, db_path: str | Path = DB_PATH) -> None:
    """
    Delete a meeting and ALL its associated data from the database.

    How it works:
    - Deletes the row from meetings WHERE id = meeting_id
    - SQLite's ON DELETE CASCADE automatically deletes all matching rows
      from attendees, action_items, decisions, blockers, and ambiguous
    - No manual cleanup needed in child tables

    Prerequisite: foreign_keys = ON must be set on the connection (it is,
    in get_connection). Without it CASCADE does not fire.

    Args:
        meeting_id: The meeting identifier to delete.
        db_path:    Path to the SQLite database file.

    Raises:
        sqlite3.Error: If the delete fails.
    """
    conn = get_connection(db_path)
    try:
        conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        conn.commit()
        logger.info("Deleted meeting %s and all cascaded child rows.", meeting_id)
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("Failed to delete meeting %s: %s", meeting_id, e)
        raise
    finally:
        conn.close()


# ── Health check ──────────────────────────────────────────────────────────────

def check_db_health(db_path: str | Path = DB_PATH) -> dict:
    """
    Return row counts for all tables.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Dict mapping table name to row count.
    """
    tables = ["meetings", "attendees", "action_items", "decisions", "blockers", "ambiguous"]
    conn = get_connection(db_path)
    counts = {}
    try:
        for table in tables:
            row = conn.execute(f"SELECT COUNT(*) as count FROM {table}").fetchone()
            counts[table] = row["count"]
    finally:
        conn.close()
    return counts


# ── Drop all (testing only) ───────────────────────────────────────────────────

def drop_all_tables(db_path: str | Path = DB_PATH) -> None:
    """
    Drop all tables. FOR TESTING AND DEVELOPMENT ONLY. Never call in production.

    Args:
        db_path: Path to the SQLite database file.
    """
    tables = ["ambiguous", "blockers", "decisions", "action_items", "attendees", "meetings"]
    conn = get_connection(db_path)
    try:
        for table in tables:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        logger.warning("All tables dropped from %s", db_path)
    finally:
        conn.close()
