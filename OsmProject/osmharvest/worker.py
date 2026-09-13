"""The worker: claims tasks, calls Overpass, persists results, retries failures.

Design notes
------------
*Every* unit of work is a row in ``fetch_task``. The worker holds no state of
its own, so it can be killed at any moment and restarted without losing
progress or repeating completed work.

Retries are owned here rather than in the HTTP layer, because the attempt count
has to survive a process restart. A task that fails at 02:00 and is retried at
02:30 by a worker started at 02:29 must still be on attempt 3, not attempt 1.

Adaptive tiling is the escalation path. A discovery query that fails twice is
not retried a third time at the same size; it is replaced by four quarter-sized
child tasks. Repeating an identical failing request is how clients get blocked.
"""

from __future__ import annotations

import json
import logging
import random
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import config, store
from .exporters import export_job
from .geo import Circle, bounding_box, split_into_quadrants
from .overpass import (
    OverpassClient,
    OverpassPermanent,
    OverpassTransient,
    build_detail_query,
    build_discovery_query,
)
from .parsing import parse_elements
from .store import DETAIL, DISCOVERY, Store

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class WorkerStats:
    tasks_done: int = 0
    tasks_deferred: int = 0
    tasks_dead: int = 0
    places_linked: int = 0
    places_discarded: int = 0
    requests: int = 0


class GracefulShutdown:
    """Finish the current task on SIGINT/SIGTERM, then stop.

    Killing a worker mid-request is survivable — the task is reset on the next
    start — but finishing cleanly avoids a wasted Overpass call, which matters
    when the server is the scarce resource.
    """

    def __init__(self) -> None:
        self.requested = False
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._handle)
            except (ValueError, OSError, AttributeError):
                pass  # not the main thread, or the platform lacks the signal

    def _handle(self, *_args: object) -> None:
        if self.requested:
            LOGGER.warning("Second interrupt - exiting immediately")
            raise KeyboardInterrupt
        self.requested = True
        LOGGER.warning("Shutdown requested - finishing current task first")


def backoff_seconds(attempts: int) -> float | None:
    """Delay before attempt ``attempts + 1``, or None once retries run out."""
    if attempts < 1:
        attempts = 1
    if attempts > len(config.RETRY_BACKOFF_SECONDS):
        return None
    base = config.RETRY_BACKOFF_SECONDS[attempts - 1]
    return base * (1.0 + random.uniform(-config.RETRY_JITTER, config.RETRY_JITTER))


def plan_job(db: Store, request_id: str) -> int:
    """Create the initial DISCOVERY task for each category. Idempotent."""
    job = db.get_job(request_id)
    if job is None:
        raise KeyError(f"No such request id: {request_id}")

    circle = Circle(job["latitude"], job["longitude"], job["radius_metres"])
    categories = json.loads(job["categories"])

    with db.transaction() as conn:
        for category in categories:
            db.add_task(
                conn,
                request_id=request_id,
                category=category,
                kind=DISCOVERY,
                batch_number=0,
                payload={"circle": circle.as_dict(), "depth": 0},
            )
    db.mark_job_running(request_id)
    return len(categories)


class Worker:
    """Executes tasks until the queue is empty or shutdown is requested."""

    def __init__(
        self,
        db: Store,
        client: OverpassClient,
        *,
        batch_size: int = config.DEFAULT_BATCH_SIZE,
        export_dir: Path = Path("exports"),
        export_after_each_batch: bool = True,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        self._db = db
        self._client = client
        self._batch_size = batch_size
        self._export_dir = export_dir
        self._export_after_each_batch = export_after_each_batch
        self._on_progress = on_progress or (lambda message: None)
        self.stats = WorkerStats()

    # -- main loop ---------------------------------------------------------- #

    def run(
        self,
        *,
        request_id: str | None = None,
        follow: bool = False,
        poll_seconds: float = 30.0,
        max_tasks: int | None = None,
    ) -> WorkerStats:
        """Drain the queue.

        With ``follow=False`` the worker stops once nothing is immediately
        runnable, sleeping only for backoff windows. With ``follow=True`` it
        stays alive and polls, which is the mode for a long-lived VPS process.
        """
        shutdown = GracefulShutdown()
        reset = self._db.reset_stale_running(request_id)
        if reset:
            LOGGER.info("Requeued %d task(s) left running by a previous process", reset)

        processed = 0
        while not shutdown.requested:
            if max_tasks is not None and processed >= max_tasks:
                LOGGER.info("Reached --max-tasks limit of %d", max_tasks)
                break

            task = self._db.claim_next_task(request_id)
            if task is not None:
                self._process(task)
                processed += 1
                # if request_id:
                    # self._db.refresh_job_status(request_id)
                self._db.refresh_job_status(task["request_id"])
                continue

            # Nothing runnable now. Is anything backing off?
            due = self._db.next_retry_due(request_id)
            if due is None:
                if not follow:
                    break
                LOGGER.info("Queue empty; polling again in %.0fs", poll_seconds)
                if self._sleep(poll_seconds, shutdown):
                    break
                continue

            wait = (due - datetime.now(timezone.utc)).total_seconds()
            if wait > 0:
                LOGGER.info(
                    "All remaining tasks are backing off; next due in %s",
                    _human_duration(wait),
                )
                if self._sleep(min(wait, poll_seconds), shutdown):
                    break

        if request_id:
            final = self._db.refresh_job_status(request_id)
            LOGGER.info("Job %s is now %s", request_id, final)
            self._export(request_id)

        self.stats.requests = self._client.request_count
        return self.stats

    @staticmethod
    def _sleep(seconds: float, shutdown: GracefulShutdown) -> bool:
        """Sleep in short slices so a signal is noticed promptly."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if shutdown.requested:
                return True
            time.sleep(min(1.0, deadline - time.monotonic()))
        return shutdown.requested

    # -- task dispatch ------------------------------------------------------ #

    def _process(self, task: Any) -> None:
        kind = task["kind"]
        suffix = "" if kind == DISCOVERY else f"#{task['batch_number']}"
        label = f"{task['request_id']}/{task['category']}/{kind}{suffix}"
        LOGGER.info("-> %s (attempt %d)", label, task["attempts"])
        try:
            if kind == DISCOVERY:
                self._run_discovery(task)
            else:
                self._run_detail(task)
        except OverpassPermanent as exc:
            LOGGER.error("%s failed permanently: %s", label, exc)
            self._db.kill_task(task["id"], error=str(exc))
            self.stats.tasks_dead += 1
        except OverpassTransient as exc:
            self._handle_transient(task, exc, label)
        except Exception as exc:  # noqa: BLE001 - a bug must not kill the worker
            LOGGER.exception("%s raised an unexpected error", label)
            self._db.kill_task(task["id"], error=f"{type(exc).__name__}: {exc}")
            self.stats.tasks_dead += 1

    def _handle_transient(self, task: Any, exc: Exception, label: str) -> None:
        """Retry, escalate to tiling, or give up."""
        attempts = task["attempts"]

        if (
            task["kind"] == DISCOVERY
            and attempts >= config.DISCOVERY_ATTEMPTS_BEFORE_TILING
            and self._try_tiling(task)
        ):
            return

        delay = backoff_seconds(attempts)
        if delay is None:
            LOGGER.error("%s exhausted all retries: %s", label, exc)
            self._db.kill_task(task["id"], error=str(exc))
            self.stats.tasks_dead += 1
            return

        LOGGER.warning("%s failed (%s); retrying in %s", label, exc, _human_duration(delay))
        self._db.defer_task(task["id"], error=str(exc), delay_seconds=delay)
        self.stats.tasks_deferred += 1

    # -- phase 1: discovery ------------------------------------------------- #

    def _run_discovery(self, task: Any) -> None:
        payload = json.loads(task["payload"])
        circle = Circle.from_dict(payload["circle"])
        category = config.CATEGORIES[task["category"]]

        query = build_discovery_query(
            filter_expression=category.filter_expression,
            box=bounding_box(circle),
            query_timeout=self._client.query_timeout,
        )
        response = self._client.run(query)

        refs = [
            [element["type"], int(element["id"])]
            for element in response.get("elements", [])
            if element.get("type") in ("node", "way", "relation")
            and element.get("id") is not None
        ]

        batches = [
            refs[i : i + self._batch_size]
            for i in range(0, len(refs), self._batch_size)
        ]
        LOGGER.info(
            "   found %d element(s) -> %d detail batch(es)", len(refs), len(batches)
        )
        self._on_progress(
            f"{task['category']}: discovered {len(refs)} candidate(s)"
        )

        # The detail tasks and the completion of discovery are written in one
        # transaction. A crash between them would otherwise lose the batches.
        base = _batch_base(task["batch_number"], payload.get("depth", 0))
        with self._db.transaction() as conn:
            for offset, batch in enumerate(batches):
                self._db.add_task(
                    conn,
                    request_id=task["request_id"],
                    category=task["category"],
                    kind=DETAIL,
                    batch_number=base + offset,
                    payload={"refs": batch, "circle": payload["circle"]},
                )
            conn.execute(
                "UPDATE fetch_task SET status = ?, last_error = NULL, "
                "next_retry_at = NULL, updated_at = ? WHERE id = ?",
                (store.DONE, store.utcnow(), task["id"]),
            )
        self.stats.tasks_done += 1

    def _try_tiling(self, task: Any) -> bool:
        """Replace a failing discovery task with four smaller children.

        Returns False when the circle is already small enough that splitting
        will not help, in which case normal retry/backoff continues.
        """
        payload = json.loads(task["payload"])
        circle = Circle.from_dict(payload["circle"])
        depth = int(payload.get("depth", 0))

        if circle.radius_metres <= config.MIN_TILE_RADIUS_METRES:
            LOGGER.warning(
                "   tile already at %.0fm; not splitting further",
                circle.radius_metres,
            )
            return False

        children = split_into_quadrants(circle)
        LOGGER.warning(
            "   discovery failed twice; splitting %.0fm circle into 4 x %.0fm tiles",
            circle.radius_metres,
            children[0].radius_metres,
        )
        self._on_progress(
            f"{task['category']}: subdividing search area (depth {depth + 1})"
        )

        # Child batch numbers are namespaced by depth so tiles at different
        # levels can never collide on the (request, category, kind, batch)
        # uniqueness constraint.
        base = _tile_base(depth + 1) + task["batch_number"] * 4
        with self._db.transaction() as conn:
            for index, child in enumerate(children):
                self._db.add_task(
                    conn,
                    request_id=task["request_id"],
                    category=task["category"],
                    kind=DISCOVERY,
                    batch_number=base + index,
                    payload={"circle": child.as_dict(), "depth": depth + 1},
                )
            conn.execute(
                "UPDATE fetch_task SET status = ?, "
                "last_error = 'Subdivided into 4 tiles', updated_at = ? WHERE id = ?",
                (store.DONE, store.utcnow(), task["id"]),
            )
        self.stats.tasks_done += 1
        return True

    # -- phase 2: detail ---------------------------------------------------- #

    def _run_detail(self, task: Any) -> None:
        payload = json.loads(task["payload"])
        refs = [(str(t), int(i)) for t, i in payload["refs"]]
        job = self._db.get_job(task["request_id"])

        query = build_detail_query(refs=refs, query_timeout=self._client.query_timeout)
        response = self._client.run(query)

        rows, discarded = parse_elements(
            response.get("elements", []),
            origin_lat=job["latitude"],
            origin_lon=job["longitude"],
            radius_metres=job["radius_metres"],
        )
        linked = self._db.upsert_places(
            request_id=task["request_id"],
            category=task["category"],
            places=rows,
        )
        self._db.complete_task(task["id"])

        self.stats.tasks_done += 1
        self.stats.places_linked += linked
        self.stats.places_discarded += discarded
        LOGGER.info(
            "   stored %d place(s), %d new to this request, %d outside radius",
            len(rows),
            linked,
            discarded,
        )

        # Results are exported after every batch, so a job that has been
        # running for two days is readable now, not in another day.
        if self._export_after_each_batch and linked:
            self._export(task["request_id"])

    def _export(self, request_id: str) -> None:
        try:
            export_job(self._db, request_id, self._export_dir)
        except OSError as exc:
            LOGGER.warning("Export failed (results are safe in the database): %s", exc)


def _batch_base(discovery_batch_number: int, depth: int) -> int:
    """Namespace detail batch numbers by their parent discovery task."""
    return (depth * 1_000_000) + (discovery_batch_number * 1_000)


def _tile_base(depth: int) -> int:
    return depth * 100_000


def _human_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"
