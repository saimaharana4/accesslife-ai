"""Restore an actual snapshot into a disposable local database, without exporting user data."""

import subprocess
from uuid import uuid4
from sqlalchemy import text
from accesslife.persistence.db import engine

TABLES = [
    "sessions",
    "plans",
    "runs",
    "plan_versions",
    "run_events",
    "trips",
    "knowledge_chunks",
    "place_locations",
    "provider_permits",
    "request_quotas",
    "provider_cache",
]


def docker(*args):
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "db", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def main():
    database = "accesslife_restore_check_" + uuid4().hex[:8]
    dump = "/tmp/" + database + ".dump"
    created = False
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                snapshot = connection.scalar(text("SELECT pg_export_snapshot()"))
                expected = {
                    table: connection.scalar(text(f'SELECT count(*) FROM "{table}"')) for table in TABLES
                }
                docker(
                    "pg_dump",
                    "-U",
                    "accesslife",
                    "-d",
                    "accesslife",
                    "--snapshot",
                    snapshot,
                    "-Fc",
                    "-f",
                    dump,
                )
        docker("createdb", "-U", "accesslife", database)
        created = True
        docker("pg_restore", "-U", "accesslife", "-d", database, "--no-owner", "--exit-on-error", dump)
        restored = {
            table: int(
                docker("psql", "-U", "accesslife", "-d", database, "-Atc", f'SELECT count(*) FROM "{table}"')
            )
            for table in TABLES
        }
        assert expected == restored, "Restored table counts differ from the exported snapshot"
        extensions = docker(
            "psql",
            "-U",
            "accesslife",
            "-d",
            database,
            "-Atc",
            "SELECT extname FROM pg_extension WHERE extname IN ('postgis','vector') ORDER BY extname",
        )
        assert extensions.splitlines() == ["postgis", "vector"]
        print(
            {
                "restore": "passed",
                "tables_checked": len(TABLES),
                "required_extensions": "passed",
                "private_payloads_exported": False,
            }
        )
    finally:
        if created:
            docker("dropdb", "-U", "accesslife", database)
        docker("rm", "-f", dump)


if __name__ == "__main__":
    main()
