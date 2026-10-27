"""Isolated local PostgreSQL foundation. Never reads legacy/cloud configuration.

Generated local-only passwords stay in dedicated container configuration and
process memory, never repository files or command arguments. Docker stores its
own container metadata locally. Real provider credentials are never read here.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from urllib.parse import quote

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = "tasteduel-prompt5-db"
SCOPE = "tasteduel-local-foundation"
DATABASE = "tasteduel_prompt5"
PORT = 55435
IMAGE = "postgres:16-bookworm@sha256:d81f7b51697014367236d07ec58b54153fc28f828b72bf247fe5c7487520bcb0"


def docker(*args: str, required: bool = True, env=None) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, env=env)
    if required and result.returncode:
        raise RuntimeError("Local Docker command failed; check Docker Desktop and the dedicated port.")
    return result.stdout.strip() if result.returncode == 0 else ""


def verify_scope() -> bool:
    label = docker(
        "inspect", "--format", '{{ index .Config.Labels "tasteduel.scope" }}', CONTAINER, required=False
    )
    if label and label != SCOPE:
        raise RuntimeError("Container name belongs to a different scope; refusing to change it.")
    return label == SCOPE


def start() -> None:
    if not docker("info", "--format", "{{.ServerVersion}}", required=False):
        raise RuntimeError("Docker Desktop must be running. No database was changed.")
    if not verify_scope():
        # An existing unlabeled container must never be adopted or replaced.
        if docker("ps", "-a", "--filter", f"name=^/{CONTAINER}$", "--format", "{{.Names}}"):
            raise RuntimeError("An unrecognized container uses the dedicated name.")
        child_env = {**os.environ, "POSTGRES_PASSWORD": secrets.token_urlsafe(40)}
        docker(
            "run",
            "--detach",
            "--name",
            CONTAINER,
            "--label",
            f"tasteduel.scope={SCOPE}",
            "--publish",
            f"127.0.0.1:{PORT}:5432",
            "--env",
            "POSTGRES_USER=tasteduel_admin",
            "--env",
            f"POSTGRES_DB={DATABASE}",
            "--env",
            "POSTGRES_PASSWORD",
            IMAGE,
            env=child_env,
        )
        print("Created dedicated loopback-only Taste Duel PostgreSQL container.")
    else:
        docker("start", CONTAINER)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if docker(
            "exec",
            CONTAINER,
            "pg_isready",
            "-h",
            "127.0.0.1",
            "-U",
            "tasteduel_admin",
            "-d",
            DATABASE,
            required=False,
        ):
            return
        time.sleep(0.5)
    raise RuntimeError("Dedicated PostgreSQL did not become ready within 45 seconds.")


def credentials() -> tuple[str, str, str]:
    if not verify_scope():
        raise RuntimeError("Start the dedicated local container first.")
    admin = docker("exec", CONTAINER, "printenv", "POSTGRES_PASSWORD")
    if len(admin) < 32:
        raise RuntimeError("Dedicated container credentials are unavailable.")

    def derive(role):
        return hmac.new(admin.encode(), role.encode(), hashlib.sha256).hexdigest()

    return admin, derive("tasteduel_migrator"), derive("tasteduel_runtime")


def bootstrap() -> tuple[str, str]:
    admin, owner, runtime = credentials()
    with psycopg.connect(
        host="127.0.0.1", port=PORT, dbname=DATABASE, user="tasteduel_admin", password=admin, autocommit=True
    ) as db:
        if db.execute("SELECT current_database()").fetchone()[0] != DATABASE:
            raise RuntimeError("Unexpected local database; refusing bootstrap.")
        for name, password in [("tasteduel_migrator", owner), ("tasteduel_runtime", runtime)]:
            exists = db.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,)).fetchone()
            verb = sql.SQL("ALTER ROLE") if exists else sql.SQL("CREATE ROLE")
            db.execute(
                sql.SQL(
                    "{} {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD {}"
                ).format(verb, sql.Identifier(name), sql.Literal(password))
            )
        db.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        db.execute("CREATE SCHEMA IF NOT EXISTS tasteduel AUTHORIZATION tasteduel_migrator")
        db.execute("REVOKE ALL ON DATABASE tasteduel_prompt5 FROM PUBLIC")
        db.execute("GRANT CONNECT ON DATABASE tasteduel_prompt5 TO tasteduel_migrator, tasteduel_runtime")
        db.execute("GRANT USAGE ON SCHEMA tasteduel TO tasteduel_runtime")
        db.execute("ALTER ROLE tasteduel_migrator SET search_path = tasteduel, pg_catalog")
        db.execute("ALTER ROLE tasteduel_runtime SET search_path = tasteduel, pg_catalog")
    prefix = "postgresql+psycopg://"
    suffix = f"@127.0.0.1:{PORT}/{DATABASE}"
    return prefix + "tasteduel_migrator:" + quote(
        owner, safe=""
    ) + suffix, prefix + "tasteduel_runtime:" + quote(runtime, safe="") + suffix


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "migrate", "test", "api", "status", "stop", "events-report", "events-purge"])
    parser.add_argument("--api-port", type=int, choices=[8002, 8004, 8005], default=8002)
    args, extra = parser.parse_known_args()
    os.chdir(ROOT)
    if args.command == "stop":
        if verify_scope():
            docker("stop", CONTAINER)
        print("Dedicated local container stopped; its data was retained.")
        return 0
    start()
    owner, runtime = bootstrap()
    if args.command in {"events-report", "events-purge"}:
        # Restricted to the verified dedicated local container. Never discovers
        # a cloud URL, writes credentials, or prints private event subjects.
        admin, _, _ = credentials()
        with psycopg.connect(
            host="127.0.0.1", port=PORT, dbname=DATABASE,
            user="tasteduel_admin", password=admin, autocommit=True,
        ) as db:
            if args.command == "events-purge":
                removed = db.execute("DELETE FROM tasteduel.product_events WHERE expires_at<=clock_timestamp()")
                print(json.dumps({"expired_events_removed": removed.rowcount}))
            else:
                values = db.execute("""
                    SELECT event,source_mode,cohort,count(*) FROM tasteduel.product_events e
                    JOIN tasteduel.sessions s ON s.id=e.session_id
                    JOIN tasteduel.games g ON g.id=e.game_id AND g.session_id=e.session_id
                    WHERE e.expires_at>clock_timestamp() AND s.revoked_at IS NULL
                      AND s.expires_at>clock_timestamp() AND g.expires_at>clock_timestamp()
                    GROUP BY event,source_mode,cohort ORDER BY event,source_mode,cohort
                """).fetchall()
                print(json.dumps({"retained_event_counts": [
                    {"event": event, "source_mode": mode, "cohort": cohort, "count": count}
                    for event, mode, cohort, count in values
                ], "human_participants_inferred": False}))
        return 0
    env = {
        **os.environ,
        "TASTEDUEL_MIGRATION_DATABASE_URL": owner,
        "TASTEDUEL_DATABASE_URL": runtime,
        "TASTEDUEL_TEST_MIGRATION_DATABASE_URL": owner,
        "TASTEDUEL_TEST_DATABASE_URL": runtime,
        "PYTHONPATH": str(ROOT / "apps/api/src"),
    }
    if args.command in {"start", "status"}:
        print(
            json.dumps(
                {
                    "scope": SCOPE,
                    "host": "127.0.0.1",
                    "port": PORT,
                    "database": DATABASE,
                    "schema": "tasteduel",
                    "provider_calls": 0,
                    "credential_files_written": False,
                }
            )
        )
        return 0
    if args.command == "migrate":
        command = [sys.executable, "-m", "alembic", "-c", "apps/api/tasteduel-alembic.ini", "upgrade", "head"]
    elif args.command == "test":
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "pytest.tasteduel.ini",
            "--confcutdir=tests/tasteduel",
            *extra,
        ]
    else:
        env["TASTEDUEL_COOKIE_SECURE"] = "false"  # Explicit local HTTP only; production default is secure.
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "tasteduel.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.api_port),
            "--no-access-log",
        ]
    return subprocess.run(command, env=env).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, psycopg.Error):
        # Never print SQL/connection values or underlying exception arguments.
        print(
            "Taste Duel local setup failed. Check Docker, port 55435 and the dedicated container; no cloud/legacy database is targeted.",
            file=sys.stderr,
        )
        raise SystemExit(1)
