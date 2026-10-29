#!/bin/sh
set -eu

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=migrator_password="$TASTEDUEL_MIGRATOR_PASSWORD" \
  --set=runtime_password="$TASTEDUEL_RUNTIME_PASSWORD" <<'SQL'
CREATE ROLE tasteduel_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD :'migrator_password';
CREATE ROLE tasteduel_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD :'runtime_password';
REVOKE ALL ON DATABASE tasteduel_local FROM PUBLIC;
GRANT CONNECT ON DATABASE tasteduel_local TO tasteduel_migrator, tasteduel_runtime;
CREATE SCHEMA tasteduel AUTHORIZATION tasteduel_migrator;
GRANT USAGE ON SCHEMA tasteduel TO tasteduel_runtime;
ALTER ROLE tasteduel_migrator SET search_path = tasteduel, pg_catalog;
ALTER ROLE tasteduel_runtime SET search_path = tasteduel, pg_catalog;
SQL
