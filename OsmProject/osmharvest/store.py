"""Persistence: SQLite schema and repository.

SQLite rather than Postgres, deliberately. This workload is a single worker
appending a few thousand rows over hours; SQLite in WAL mode handles it with
zero setup, the database is one file to back up or copy off the VPS, and every
query in this module is portable to Postgres if the project ever outgrows it.

The database is also the cache. A task marked DONE is never re-run, and places
are upserted by (osm_type, osm_id), so restarting a job costs nothing and
overlapping tiles cannot create duplicates. A separate response cache would add
a second source of truth for no benefit.
"""

from __future__ import annotations

import json
import random
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

# -- task state machine ------------------------------------------------------ #
PENDING = "PENDING"
RUNNING = "RUNNING"
DONE = "DONE"
RETRY = "RETRY"
DEAD = "DEAD"

# -- job state --------------------------------------------------------------- #
JOB_PENDING = "PENDING"
JOB_RUNNING = "RUNNING"
JOB_COMPLETED = "COMPLETED"
JOB_COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"

DISCOVERY = "DISCOVERY"
DETAIL = "DETAIL"

SCHEMA: str = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS search_job (
    request_id     TEXT PRIMARY KEY,
    latitude       REAL NOT NULL,
    longitude      REAL NOT NULL,
    radius_metres  REAL NOT NULL,
    categories     TEXT NOT NULL,
    status         TEXT NOT NULL,
    note           TEXT,
    created_at     TEXT NOT NULL,
    started_at     TEXT,
    completed_at   TEXT
);

CREATE TABLE IF NOT EXISTS fetch_task (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id     TEXT NOT NULL REFERENCES search_job(request_id) ON DELETE CASCADE,
    category       TEXT NOT NULL,
    kind           TEXT NOT NULL,
    batch_number   INTEGER NOT NULL DEFAULT 0,
    payload        TEXT NOT NULL,
    status         TEXT NOT NULL,
    attempts       INTEGER NOT NULL DEFAULT 0,
    last_error     TEXT,
    next_retry_at  TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    UNIQUE (request_id, category, kind, batch_number)
);

CREATE INDEX IF NOT EXISTS idx_task_claim
    ON fetch_task (status, next_retry_at);
CREATE INDEX IF NOT EXISTS idx_task_job
    ON fetch_task (request_id, status);

-- A place is global: the same pub found by two different searches is stored
-- once. Membership of a search lives in job_place.
CREATE TABLE IF NOT EXISTS place (
    osm_type       TEXT NOT NULL,
    osm_id         INTEGER NOT NULL,
    name           TEXT,
    amenity        TEXT,
    latitude       REAL,
    longitude      REAL,
    email          TEXT,
    website        TEXT,
    phone          TEXT,
    address        TEXT,
    postcode       TEXT,
    opening_hours  TEXT,
    cuisine        TEXT,
    operator       TEXT,
    brand          TEXT,
    raw_tags       TEXT,
    first_seen_at  TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    PRIMARY KEY (osm_type, osm_id)
);

CREATE INDEX IF NOT EXISTS idx_place_email
    ON place (email) WHERE email IS NOT NULL;

CREATE TABLE IF NOT EXISTS job_place (
    request_id       TEXT NOT NULL REFERENCES search_job(request_id) ON DELETE CASCADE,
    osm_type         TEXT NOT NULL,
    osm_id           INTEGER NOT NULL,
    category         TEXT NOT NULL,
    distance_metres  REAL,
    created_at       TEXT NOT NULL,
    PRIMARY KEY (request_id, osm_type, osm_id),
    FOREIGN KEY (osm_type, osm_id) REFERENCES place(osm_type, osm_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_job_place_request ON job_place (request_id);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp)
    except ValueError:
        return None


class Store:
    """Thin repository over SQLite. One instance per process."""

    def __init__(self, path: Path | str = "osmharvest.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            self.path, timeout=30.0, isolation_level=None  # explicit transactions
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """BEGIN IMMEDIATE so concurrent workers cannot claim the same task."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

    # -- jobs --------------------------------------------------------------- #

    def generate_request_id(self) -> str:
        """An unused 8-digit request id.

        Random rather than sequential so ids are not guessable and two
        independently launched workers cannot collide on the next value.
        """
        for _ in range(200):
            candidate = f"{random.randint(10_000_000, 99_999_999)}"
            row = self._conn.execute(
                "SELECT 1 FROM search_job WHERE request_id = ?", (candidate,)
            ).fetchone()
            if row is None:
                return candidate
        raise RuntimeError("Could not allocate a free 8-digit request id")

    def create_job(
        self,
        *,
        request_id: str,
        latitude: float,
        longitude: float,
        radius_metres: float,
        categories: Sequence[str],
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO search_job (request_id, latitude, longitude, "
                "radius_metres, categories, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    request_id,
                    latitude,
                    longitude,
                    radius_metres,
                    json.dumps(list(categories)),
                    JOB_PENDING,
                    utcnow(),
                ),
            )

    def get_job(self, request_id: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM search_job WHERE request_id = ?", (request_id,)
        ).fetchone()

    def list_jobs(self) -> list[sqlite3.Row]:
        return list(
            self._conn.execute("SELECT * FROM search_job ORDER BY created_at DESC")
        )

    def mark_job_running(self, request_id: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE search_job SET status = ?, "
                "started_at = COALESCE(started_at, ?) WHERE request_id = ?",
                (JOB_RUNNING, utcnow(), request_id),
            )

    def refresh_job_status(self, request_id: str) -> str:
        """Recompute a job's status from its tasks. Returns the new status."""
        counts = self.task_counts(request_id)
        outstanding = counts.get(PENDING, 0) + counts.get(RETRY, 0) + counts.get(RUNNING, 0)
        if outstanding:
            status = JOB_RUNNING
        elif counts.get(DEAD, 0):
            status = JOB_COMPLETED_WITH_ERRORS
        else:
            status = JOB_COMPLETED
        completed = None if outstanding else utcnow()
        with self.transaction() as conn:
            conn.execute(
                "UPDATE search_job SET status = ?, completed_at = ? WHERE request_id = ?",
                (status, completed, request_id),
            )
        return status
    
    def delete_job(self, request_id: str) -> bool:
        """
        Remove a job and everything scoped to it: its fetch_task rows (queued
        or in-progress work) and job_place rows (its links into the shared
        place table). Returns True if a job with this id existed.

        The shared `place` table is deliberately left untouched -- a place
        row can be linked to several jobs (that's the whole point of
        deduplicating by osm_type/osm_id), so deleting a job must never
        delete data another job still depends on. Cascading is handled by
        the `ON DELETE CASCADE` foreign keys in the schema (requires
        `PRAGMA foreign_keys = ON`, which __init__ sets on every connection),
        so removing the one `search_job` row is enough -- its `fetch_task`
        and `job_place` rows go with it automatically.

        Use this to clear out a stuck or no-longer-wanted job (e.g. one
        whose Mongo-side blood request was already marked failed elsewhere,
        or a one-off manual test) so claim_next_task's oldest-first ordering
        stops handing its tasks out ahead of every newer job's.
        """
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM search_job WHERE request_id = ?", (request_id,))
        return cursor.rowcount > 0
    # -- tasks -------------------------------------------------------------- #

    def add_task(
        self,
        conn: sqlite3.Connection,
        *,
        request_id: str,
        category: str,
        kind: str,
        batch_number: int,
        payload: dict[str, Any],
    ) -> None:
        """Insert a task, ignoring duplicates so re-planning is idempotent."""
        now = utcnow()
        conn.execute(
            "INSERT OR IGNORE INTO fetch_task (request_id, category, kind, "
            "batch_number, payload, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                request_id,
                category,
                kind,
                batch_number,
                json.dumps(payload),
                PENDING,
                now,
                now,
            ),
        )

    def claim_next_task(self, request_id: str | None = None) -> sqlite3.Row | None:
        """Atomically take the next runnable task and mark it RUNNING.

        DISCOVERY sorts before DETAIL so a category's shape is known early and
        the progress display is meaningful from the first minute.
        """
        now = utcnow()
        clause = "AND request_id = ?" if request_id else ""
        params: list[Any] = [now]
        if request_id:
            params.append(request_id)

        with self.transaction() as conn:
            row = conn.execute(
                f"""
                SELECT * FROM fetch_task
                 WHERE (status = 'PENDING'
                        OR (status = 'RETRY' AND (next_retry_at IS NULL
                                                  OR next_retry_at <= ?)))
                   {clause}
              ORDER BY CASE kind WHEN 'DISCOVERY' THEN 0 ELSE 1 END,
                       id
                 LIMIT 1
                """,
                params,
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE fetch_task SET status = ?, attempts = attempts + 1, "
                "updated_at = ? WHERE id = ?",
                (RUNNING, utcnow(), row["id"]),
            )
        return self._conn.execute(
            "SELECT * FROM fetch_task WHERE id = ?", (row["id"],)
        ).fetchone()

    def next_retry_due(self, request_id: str | None = None) -> datetime | None:
        """When the earliest backing-off task becomes runnable."""
        clause = "AND request_id = ?" if request_id else ""
        params = [request_id] if request_id else []
        row = self._conn.execute(
            f"SELECT MIN(next_retry_at) AS due FROM fetch_task "
            f"WHERE status = 'RETRY' {clause}",
            params,
        ).fetchone()
        return _parse(row["due"]) if row else None

    def complete_task(self, task_id: int) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE fetch_task SET status = ?, last_error = NULL, "
                "next_retry_at = NULL, updated_at = ? WHERE id = ?",
                (DONE, utcnow(), task_id),
            )

    def defer_task(self, task_id: int, *, error: str, delay_seconds: float) -> None:
        due = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        with self.transaction() as conn:
            conn.execute(
                "UPDATE fetch_task SET status = ?, last_error = ?, "
                "next_retry_at = ?, updated_at = ? WHERE id = ?",
                (RETRY, error[:500], due.isoformat(timespec="seconds"), utcnow(), task_id),
            )

    def kill_task(self, task_id: int, *, error: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE fetch_task SET status = ?, last_error = ?, "
                "next_retry_at = NULL, updated_at = ? WHERE id = ?",
                (DEAD, error[:500], utcnow(), task_id),
            )

    def reset_stale_running(self, request_id: str | None = None) -> int:
        """Return tasks left RUNNING by a crash to the queue.

        Called at worker start-up. Without this, a hard kill during a request
        would strand those tasks forever.
        """
        clause = "AND request_id = ?" if request_id else ""
        params = [request_id] if request_id else []
        with self.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE fetch_task SET status = 'RETRY', next_retry_at = NULL, "
                f"last_error = 'Reset after unclean shutdown', updated_at = '{utcnow()}' "
                f"WHERE status = 'RUNNING' {clause}",
                params,
            )
            return cursor.rowcount

    def revive_dead_tasks(self, request_id: str | None = None) -> int:
        """Return DEAD tasks to the queue with their attempt count cleared."""
        clause = "AND request_id = ?" if request_id else ""
        params = [request_id] if request_id else []
        with self.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE fetch_task SET status = 'PENDING', attempts = 0, "
                f"next_retry_at = NULL, updated_at = '{utcnow()}' "
                f"WHERE status = 'DEAD' {clause}",
                params,
            )
            return cursor.rowcount

    def task_counts(self, request_id: str) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM fetch_task "
            "WHERE request_id = ? GROUP BY status",
            (request_id,),
        )
        return {row["status"]: row["n"] for row in rows}

    def category_progress(self, request_id: str) -> list[sqlite3.Row]:
        return list(
            self._conn.execute(
                """
                SELECT category,
                       COUNT(*) AS total,
                       SUM(status = 'DONE')    AS done,
                       SUM(status = 'DEAD')    AS dead,
                       SUM(status = 'RETRY')   AS retrying,
                       SUM(status = 'RUNNING') AS running
                  FROM fetch_task
                 WHERE request_id = ?
              GROUP BY category
              ORDER BY category
                """,
                (request_id,),
            )
        )

    def dead_tasks(self, request_id: str) -> list[sqlite3.Row]:
        return list(
            self._conn.execute(
                "SELECT * FROM fetch_task WHERE request_id = ? AND status = 'DEAD' "
                "ORDER BY category, batch_number",
                (request_id,),
            )
        )

    # -- places ------------------------------------------------------------- #

    def upsert_places(
        self,
        *,
        request_id: str,
        category: str,
        places: Sequence[dict[str, Any]],
    ) -> int:
        """Insert or update places and link them to the job. Returns rows linked.

        Upsert semantics mean overlapping tiles, retried batches and repeated
        jobs converge instead of duplicating. The unique key is
        (osm_type, osm_id) — never the name.
        """
        if not places:
            return 0
        now = utcnow()
        linked = 0
        with self.transaction() as conn:
            for place in places:
                conn.execute(
                    """
                    INSERT INTO place (osm_type, osm_id, name, amenity, latitude,
                        longitude, email, website, phone, address, postcode,
                        opening_hours, cuisine, operator, brand, raw_tags,
                        first_seen_at, updated_at)
                    VALUES (:osm_type, :osm_id, :name, :amenity, :latitude,
                        :longitude, :email, :website, :phone, :address, :postcode,
                        :opening_hours, :cuisine, :operator, :brand, :raw_tags,
                        :now, :now)
                    ON CONFLICT (osm_type, osm_id) DO UPDATE SET
                        name          = excluded.name,
                        amenity       = excluded.amenity,
                        latitude      = excluded.latitude,
                        longitude     = excluded.longitude,
                        email         = excluded.email,
                        website       = excluded.website,
                        phone         = excluded.phone,
                        address       = excluded.address,
                        postcode      = excluded.postcode,
                        opening_hours = excluded.opening_hours,
                        cuisine       = excluded.cuisine,
                        operator      = excluded.operator,
                        brand         = excluded.brand,
                        raw_tags      = excluded.raw_tags,
                        updated_at    = excluded.updated_at
                    """,
                    {**place, "now": now},
                )
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO job_place (request_id, osm_type, osm_id, "
                    "category, distance_metres, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        request_id,
                        place["osm_type"],
                        place["osm_id"],
                        category,
                        place.get("distance_metres"),
                        now,
                    ),
                )
                linked += cursor.rowcount
        return linked

    def job_places(
        self, request_id: str, *, with_email_only: bool = False
    ) -> list[sqlite3.Row]:
        email_clause = "AND p.email IS NOT NULL AND TRIM(p.email) <> ''"
        return list(
            self._conn.execute(
                f"""
                SELECT jp.category, jp.distance_metres, p.*
                  FROM job_place jp
                  JOIN place p USING (osm_type, osm_id)
                 WHERE jp.request_id = ?
                   {email_clause if with_email_only else ""}
              ORDER BY jp.distance_metres
                """,
                (request_id,),
            )
        )

    def job_stats(self, request_id: str) -> dict[str, int]:
        row = self._conn.execute(
            """
            SELECT COUNT(*) AS places,
                   SUM(p.email   IS NOT NULL AND TRIM(p.email)   <> '') AS with_email,
                   SUM(p.website IS NOT NULL AND TRIM(p.website) <> '') AS with_website,
                   SUM(p.phone   IS NOT NULL AND TRIM(p.phone)   <> '') AS with_phone
              FROM job_place jp
              JOIN place p USING (osm_type, osm_id)
             WHERE jp.request_id = ?
            """,
            (request_id,),
        ).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}
