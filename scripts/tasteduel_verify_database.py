"""Authorized foundation SQL bootstrap/verification using ADC and pinned secrets.

Run with cloud-sql-python-connector[psycopg]==1.23.0. No credential payload
files, DSN output, old-row retrieval, application migrations or network changes.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tasteduel_database_foundation import FoundationBoundaryError, bootstrap_staged, verify_migrator, verify_runtime

PROJECT = 'project-bb13ecd8-9d67-408d-9a7'
INSTANCE = PROJECT + ':asia-south1:accesslife-db'
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bootstrap', action='store_true')
    args = parser.parse_args()
    result = {'status': 'STARTED', 'application_migrations_run': False, 'secret_payloads_printed': False}
    try:
        from google.cloud import secretmanager
        from google.cloud.sql.connector import Connector, IPTypes
        client = secretmanager.SecretManagerServiceClient()

        def secret(name):
            return client.access_secret_version(request={'name': f'projects/{PROJECT}/secrets/{name}/versions/1'}).payload.data.decode()

        with Connector(refresh_strategy='LAZY') as connector:
            def connect(user, password, database='tasteduel'):
                return connector.connect(INSTANCE, 'psycopg', user=user, password=password, db=database, ip_type=IPTypes.PUBLIC, timeout=15)

            if args.bootstrap:
                migration = urlsplit(secret('tasteduel-migrate-database-url'))
                if migration.username != 'tasteduel_migrator' or migration.path != '/tasteduel' or migration.hostname is not None:
                    raise ValueError('Unexpected migration reference')
                with connect('accesslife', secret('accesslife-db-password')) as admin:
                    with connect('tasteduel_migrator', unquote(migration.password or '')) as migrator:
                        result['bootstrap'] = bootstrap_staged(admin, migrator)
                del migration
            for actor, user, verify in [('runtime', 'tasteduel_runtime', verify_runtime), ('migrate', 'tasteduel_migrator', verify_migrator)]:
                url = urlsplit(secret(f'tasteduel-{actor}-database-url'))
                if url.username != user or url.path != '/tasteduel' or url.hostname is not None:
                    raise ValueError('Unexpected connection reference')
                password = unquote(url.password or '')
                with connect(user, password) as connection:
                    result[actor] = verify(connection)
                    if actor == 'runtime':
                        probes = [
                            'CREATE SCHEMA tasteduel_forbidden_foundation_probe',
                            'CREATE TABLE tasteduel.forbidden_foundation_probe (id integer)',
                            'CREATE TEMP TABLE forbidden_foundation_probe (id integer)',
                            'SET ROLE tasteduel_migrator',
                            'SET ROLE accesslife',
                        ]
                        denied = 0
                        for statement in probes:
                            try:
                                with connection.transaction(force_rollback=True):
                                    connection.execute(statement)
                            except Exception as exc:
                                if getattr(exc, 'sqlstate', None) != '42501':
                                    raise
                                denied += 1
                            else:
                                raise ValueError('Unexpected runtime capability')
                        result['runtime_actual_denial_probes'] = denied
                if actor == 'runtime':
                    with connect(user, password, 'accesslife') as legacy:
                        # Permission check only: LIMIT 0 never retrieves old rows.
                        try:
                            legacy.execute('SELECT 1 FROM public.sessions LIMIT 0')
                        except Exception as exc:
                            if getattr(exc, 'sqlstate', None) != '42501':
                                raise
                            legacy.rollback()
                            result['old_sessions_read_denied'] = True
                        else:
                            legacy.rollback()
                            raise ValueError('Old private table access was unexpectedly permitted')
                        row = legacy.execute("""SELECT count(*) FROM pg_class c
                            JOIN pg_namespace n ON n.oid=c.relnamespace
                            WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema'
                            AND c.relkind IN ('r','p','v','m','f')
                            AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_class'::regclass
                                AND d.objid=c.oid AND d.deptype='e')
                            AND has_table_privilege(current_user,c.oid,
                                'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')""").fetchone()
                        result['old_application_tables_privileges_denied'] = row[0] == 0
                        if row[0]:
                            raise ValueError('Unexpected legacy table privileges')
                        functions = legacy.execute("""SELECT count(*) FROM pg_proc p
                            JOIN pg_namespace n ON n.oid=p.pronamespace
                            WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema'
                            AND p.prosecdef
                            AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_proc'::regclass
                                AND d.objid=p.oid AND d.deptype='e')
                            AND has_function_privilege(current_user,p.oid,'EXECUTE')""").fetchone()
                        result['old_application_definer_functions_denied'] = functions[0] == 0
                        if functions[0]:
                            raise ValueError('Unexpected legacy privileged function access')
                        legacy.rollback()
                del password, url
        result['status'] = 'PASS'
    except Exception as exc:
        # Never print a database server exception, URL, SQL values or traceback.
        result.update(status='BLOCKED', failure_type=type(exc).__name__, sqlstate=getattr(exc, 'sqlstate', None))
        if isinstance(exc, FoundationBoundaryError):
            result['boundary_reason'] = str(exc)
            result['sqlstate'] = getattr(exc.__context__, 'sqlstate', None)
            for field in ('preparation_committed', 'temporary_create_cleanup_completed'):
                if hasattr(exc, field):
                    result[field] = bool(getattr(exc, field))
    destination = ROOT / '.data/tasteduel-cloud-review/database-foundation-verification.json'
    destination.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
