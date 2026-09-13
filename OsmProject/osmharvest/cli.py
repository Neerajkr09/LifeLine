"""Command line interface.

    submit   register a search and print its 8-digit request id
    run      work the queue (add --follow to keep running on a VPS)
    status   live progress for one job, or a list of all jobs
    export   rewrite the output files for a job from the database
    retry    return permanently-failed tasks to the queue
    doctor   check connectivity and endpoint health before a long run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

from . import config
from .exporters import export_job
from .overpass import OverpassClient
from .store import Store
from .worker import Worker, plan_job
from .store import JOB_COMPLETED, JOB_COMPLETED_WITH_ERRORS, Store
LOGGER = logging.getLogger("osmharvest")


def _configure_logging(verbose: bool, log_file: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_submit(args: argparse.Namespace) -> int:
    if not -90.0 <= args.lat <= 90.0:
        raise SystemExit(f"Latitude {args.lat} out of range")
    if not -180.0 <= args.lng <= 180.0:
        raise SystemExit(f"Longitude {args.lng} out of range")
    if not 0 < args.radius <= config.MAX_RADIUS_METRES:
        raise SystemExit(f"Radius must be 1..{config.MAX_RADIUS_METRES:.0f} metres")

    with Store(args.db) as db:
        request_id = args.request_id or db.generate_request_id()
        if db.get_job(request_id) is not None:
            raise SystemExit(f"Request id {request_id} already exists")
        db.create_job(
            request_id=request_id,
            latitude=args.lat,
            longitude=args.lng,
            radius_metres=args.radius,
            categories=args.categories,
        )
        created = plan_job(db, request_id)

    print(f"\nRequest ID: {request_id}")
    print(f"  {args.lat}, {args.lng} within {args.radius:.0f}m")
    print(f"  {created} categorie(s): {', '.join(args.categories)}")
    print(f"\nNext:  python -m osmharvest run --request-id {request_id}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    with Store(args.db) as db, OverpassClient(
        endpoints=args.endpoints,
        query_timeout=args.query_timeout,
        min_interval=args.min_interval,
    ) as client:
        if args.request_id and db.get_job(args.request_id) is None:
            raise SystemExit(f"No such request id: {args.request_id}")

        worker = Worker(
            db,
            client,
            batch_size=args.batch_size,
            export_dir=Path(args.export_dir),
            export_after_each_batch=not args.export_at_end,
        )
        stats = worker.run(
            request_id=args.request_id,
            follow=args.follow,
            poll_seconds=args.poll,
            max_tasks=args.max_tasks,
        )

    print(
        f"\nTasks done {stats.tasks_done} | deferred {stats.tasks_deferred} | "
        f"dead {stats.tasks_dead}\n"
        f"Places linked {stats.places_linked} | outside radius {stats.places_discarded}\n"
        f"Overpass requests {stats.requests}"
    )
    return 1 if stats.tasks_dead else 0


def cmd_status(args: argparse.Namespace) -> int:
    with Store(args.db) as db:
        if not args.request_id:
            jobs = db.list_jobs()
            if not jobs:
                print("No jobs yet.")
                return 0
            print(f"{'REQUEST':<10} {'STATUS':<24} {'PLACES':>7}  QUERY")
            for job in jobs:
                stats = db.job_stats(job["request_id"])
                print(
                    f"{job['request_id']:<10} {job['status']:<24} "
                    f"{stats['places']:>7}  "
                    f"{job['latitude']:.4f},{job['longitude']:.4f} "
                    f"r={job['radius_metres']:.0f}m"
                )
            return 0

        job = db.get_job(args.request_id)
        if job is None:
            raise SystemExit(f"No such request id: {args.request_id}")

        stats = db.job_stats(args.request_id)
        print(f"\nRequest {job['request_id']} - {job['status']}")
        print(
            f"  {job['latitude']}, {job['longitude']} within "
            f"{job['radius_metres']:.0f}m | {', '.join(json.loads(job['categories']))}"
        )
        print(f"  created {job['created_at']}  started {job['started_at'] or '-'}")

        print("\n  Progress by category")
        for row in db.category_progress(args.request_id):
            done, total = row["done"] or 0, row["total"]
            pct = (done / total * 100) if total else 0.0
            bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
            flags = []
            if row["running"]:
                flags.append(f"{row['running']} running")
            if row["retrying"]:
                flags.append(f"{row['retrying']} retrying")
            if row["dead"]:
                flags.append(f"{row['dead']} FAILED")
            suffix = f"  ({', '.join(flags)})" if flags else ""
            print(f"    {row['category']:<12} [{bar}] {pct:5.1f}%  {done}/{total}{suffix}")

        print(
            f"\n  Places {stats['places']} | with email {stats['with_email']} | "
            f"with website {stats['with_website']} | with phone {stats['with_phone']}"
        )

        dead = db.dead_tasks(args.request_id)
        if dead:
            print(f"\n  {len(dead)} failed task(s). Most recent errors:")
            for row in dead[:5]:
                print(f"    {row['category']}/{row['kind']}#{row['batch_number']}: "
                      f"{(row['last_error'] or '')[:90]}")
            print(f"  Retry with: python -m osmharvest retry "
                  f"--request-id {args.request_id}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    with Store(args.db) as db:
        paths = export_job(db, args.request_id, Path(args.export_dir))
        stats = db.job_stats(args.request_id)
    print(f"\nExported request {args.request_id} ({stats['places']} places):")
    for path in paths.values():
        print(f"  {path}")
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    with Store(args.db) as db:
        revived = db.revive_dead_tasks(args.request_id)
        if args.request_id:
            db.refresh_job_status(args.request_id)
    print(f"Requeued {revived} failed task(s).")
    return 0

# def cmd_cancel(args: argparse.Namespace) -> int:
#     """Remove a job entirely: its queued/in-progress tasks, and its links
#     into the shared place table. Use this for a stuck or no-longer-wanted
#     job -- e.g. one that's been retrying against a dead endpoint for hours,
#     or whose corresponding blood request was already marked failed
#     elsewhere. Without this, claim_next_task's oldest-first ordering means a
#     single old, permanently-stuck job can sit at the front of the queue
#     forever, ahead of every real, newer request.
#     """
#     with Store(args.db) as db:
#         existed = db.delete_job(args.request_id)
#     if existed:
#         print(f"Removed request {args.request_id} and its tasks from the queue.")
#         return 0
#     print(f"No such request: {args.request_id}")
#     return 1
def cmd_cancel(args: argparse.Namespace) -> int:
    """Remove a job entirely: its queued/in-progress tasks, and its links
    into the shared place table. Use this for a stuck or no-longer-wanted
    job -- e.g. one that's been retrying against a dead endpoint for hours,
    or whose corresponding blood request was already marked failed
    elsewhere. Without this, claim_next_task's oldest-first ordering means a
    single old, permanently-stuck job can sit at the front of the queue
    forever, ahead of every real, newer request.

    --all removes every job that isn't already COMPLETED /
    COMPLETED_WITH_ERRORS in one pass -- a full "stop everything currently
    queued or in progress" reset, for when several stale jobs have piled up
    rather than just one.
    """
    with Store(args.db) as db:
        if args.all:
            targets = [
                job["request_id"] for job in db.list_jobs()
                if job["status"] not in (JOB_COMPLETED, JOB_COMPLETED_WITH_ERRORS)
            ]
            if not targets:
                print("Nothing to cancel -- every job is already COMPLETED or COMPLETED_WITH_ERRORS.")
                return 0
            for request_id in targets:
                db.delete_job(request_id)
                print(f"Removed request {request_id}")
            print(f"\n{len(targets)} job(s) removed. The queue is now empty of anything unfinished.")
            return 0

        if not args.request_id:
            print("Give --request-id <id>, or --all to remove every unfinished job.")
            return 2

        existed = db.delete_job(args.request_id)
    if existed:
        print(f"Removed request {args.request_id} and its tasks from the queue.")
        return 0
    print(f"No such request: {args.request_id}")
    return 1
def cmd_doctor(args: argparse.Namespace) -> int:
    """Check every endpoint before committing to a long run."""
    print(f"User-Agent: {config.USER_AGENT}")
    if "example.ac.uk" in config.USER_AGENT:
        print("  WARNING: set OSMHARVEST_USER_AGENT to a real contact address.\n")

    healthy = 0
    with OverpassClient(endpoints=args.endpoints) as client:
        for endpoint in client.endpoints:
            host = endpoint.split("//")[-1].split("/")[0]
            try:
                text = client.status(endpoint)
                slots = [
                    line for line in text.splitlines()
                    if "slot" in line.lower() or "Rate limit" in line
                ]
                print(f"  OK   {host}")
                for line in slots[:3]:
                    print(f"         {line.strip()}")
                healthy += 1
            except Exception as exc:  # noqa: BLE001 - diagnostics must not raise
                print(f"  FAIL {host}: {type(exc).__name__}: {str(exc)[:80]}")

        if healthy:
            print("\n  Sending a tiny live query...")
            try:
                payload = client.run(
                    "[out:json][timeout:25];node[amenity=pub](51.5074,-0.1288,51.5084,-0.1268);out ids;"
                )
                print(f"  OK   query returned {len(payload.get('elements', []))} element(s), "
                      f"data as of {client.data_timestamp}")
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL {type(exc).__name__}: {str(exc)[:160]}")
                return 1
    return 0 if healthy else 1


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    # Shared flags live on a parent parser so they are accepted both before and
    # after the subcommand. Position-sensitive flags are a needless deployment
    # trap on a machine you are administering over SSH at midnight.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default="osmharvest.db", help="SQLite database path")
    common.add_argument("--export-dir", default="exports", help="Output directory")
    common.add_argument("--log-file", type=Path, default=None, help="Also log to a file")
    common.add_argument("-v", "--verbose", action="store_true")

    parser = argparse.ArgumentParser(
        prog="python -m osmharvest",
        parents=[common],
        description="Resumable OpenStreetMap POI harvester with per-request email export.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        return subparsers.add_parser(name, help=help_text, parents=[common])

    submit = add("submit", "Register a new search")
    submit.add_argument("--lat", type=float, required=True)
    submit.add_argument("--lng", type=float, required=True)
    submit.add_argument("--radius", type=float, default=5000.0, help="Metres")
    submit.add_argument(
        "--categories",
        nargs="+",
        choices=sorted(config.CATEGORIES),
        default=list(config.DEFAULT_CATEGORIES),
    )
    submit.add_argument("--request-id", help="Supply your own 8-digit id")
    submit.set_defaults(func=cmd_submit)

    run = add("run", "Work the task queue")
    run.add_argument("--request-id", help="Limit to one job")
    run.add_argument("--follow", action="store_true", help="Stay alive and poll")
    run.add_argument("--poll", type=float, default=30.0, help="Poll interval, seconds")
    run.add_argument("--max-tasks", type=int, default=None, help="Stop after N tasks")
    run.add_argument("--batch-size", type=int, default=config.DEFAULT_BATCH_SIZE)
    run.add_argument("--query-timeout", type=int, default=config.QUERY_TIMEOUT)
    run.add_argument(
        "--min-interval",
        type=float,
        default=config.MIN_REQUEST_INTERVAL,
        help="Minimum seconds between Overpass requests",
    )
    run.add_argument("--endpoints", nargs="+", default=list(config.DEFAULT_ENDPOINTS))
    run.add_argument(
        "--export-at-end",
        action="store_true",
        help="Export once at the end instead of after every batch",
    )
    run.set_defaults(func=cmd_run)

    status = add("status", "Show progress")
    status.add_argument("--request-id", nargs="?", default=None)
    status.set_defaults(func=cmd_status)

    export = add("export", "Rewrite output files")
    export.add_argument("--request-id", required=True)
    export.set_defaults(func=cmd_export)

    retry = add("retry", "Requeue failed tasks")
    # cancel = add("cancel", "Remove a job and its tasks from the queue")
    # cancel.add_argument("--request-id", required=True)
    # cancel.set_defaults(func=cmd_cancel)
    cancel = add("cancel", "Remove a job and its tasks from the queue")
    cancel.add_argument("--request-id", default=None, help="Required unless --all is given")
    cancel.add_argument("--all", action="store_true", help="Remove every unfinished job, not just one")
    cancel.set_defaults(func=cmd_cancel)
    retry.add_argument("--request-id", default=None)
    retry.set_defaults(func=cmd_retry)

    doctor = add("doctor", "Check endpoint health")
    doctor.add_argument("--endpoints", nargs="+", default=list(config.DEFAULT_ENDPOINTS))
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_logging(args.verbose, args.log_file)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted. Progress is saved; rerun 'run' to resume.")
        return 130
    except KeyError as exc:
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
