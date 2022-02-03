# encoding: utf-8

from datetime import datetime
import ldap3
import logging
import psycopg2
import re
import sys
from os import environ
# from urllib.error import URLError
# from pprint import pprint

from fileenv import fileenv

loglevel = environ.get('VERBOSITY', logging.INFO)
log = logging.getLogger(__name__)
log.setLevel(loglevel)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(fmt='[%(asctime)s: %(levelname)s] %(message)s'))
log.addHandler(handler)

# Load some config from ENV vars
ldap_uri = environ.get('LDAPURI', 'ldap://192.168.1.70:3389')
baseDN=environ.get('LDAPBASEDN','dc=georchestra,dc=org')
ldap_role_regex = environ.get('LDAP_ROLE_REGEX','^PGSQL_SCHEMA_([A-Z][A-Z0-9-_]+)_(READER|WRITER|PUBLISHER)$')
search_base = 'ou=users,{}'.format(baseDN)
ldapadmin_passwd = fileenv('LDAPPASSWORD', fallback='ldapadmin_pwd')
pg_dsn = environ.get('PGDSN', 'postgres://georchestra@192.168.1.70:5434/georchestra')
pg_password = fileenv('PGPASSWORD', fallback='geor')
dry_mode = environ.get('DRY', '')


def extract_schema_from_ldap_role(ldap_role: str) -> str:
    tokens = re.search(ldap_role_regex, ldap_role)
    if not tokens:
        return None
    schema_name = tokens.group(1).lower()
    return schema_name


def get_schemas_list_from_ldap(ldapconnection: ldap3.Connection):
    """
    Scan the LDAP directory for employeeNumber values. Look for the max value, and returns the following one (maxValue+1)
    :param ldapconnection: an ldap3 LDAP connection
    :return: employeeNumber value to use for next user
    """
    entry_generator = ldapconnection.extend.standard.paged_search(
        search_base='ou=roles,{}'.format(baseDN),
        search_filter='(cn=PGSQL_*)',
        search_scope=ldap3.SUBTREE,
        attributes=['cn'],
        paged_size=1000, generator=True)

    # Then get your results:
    schemas_list = []
    pages = 0
    for entry in entry_generator:
        pages += 1
        schema = extract_schema_from_ldap_role(entry['attributes']['cn'][0])
        if schema:
            schemas_list.append(schema)
    return set(schemas_list)


def main():
    # lst = ["MAPSTORE", "PGSQL_SCHEMA_KSK_READER", "PGSQL_SCHEMA_KSK-GIS_WRITER", "PGSQL_SCHEMA_UPJS_STUDENTS_PUBLISHER", "PGSQL_SCHEMA_UPJS_STUDENTS_USER"]
    # for l in lst:
    #     extract_schema_from_ldap_role(l)
    if dry_mode:
        log.info("[Schemas synchronization] Running in dry mode. No changes will be applied")

    log.debug("Connecting to LDAP server {}".format(ldap_uri))
    server = ldap3.Server(ldap_uri)
    with ldap3.Connection(server, user='cn=admin,{}'.format(baseDN), password=ldapadmin_passwd, auto_bind=True) as conn:

        # Get schemas list from LDAP
        ldap_schemas = get_schemas_list_from_ldap(conn)
        log.debug("Schemas list (from LDAP): {}".format(', '.join(ldap_schemas)))

        # close the connection
        conn.unbind()

    pg_schemas = list()
    pg_conn = psycopg2.connect(pg_dsn, password=pg_password)
    with pg_conn:
        with pg_conn.cursor() as cur:
            # Get the list of existing non-system schemas
            q = """SELECT DISTINCT nspname
                    FROM pg_catalog.pg_namespace
                    WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'
                    AND nspname NOT LIKE 'tiger%' AND nspname <> 'topology' AND nspname <> 'public';"""
            cur.execute(q)
            pg_schemas = [r[0] for r in cur.fetchall()]
            log.debug("Schemas list (from PG): {}".format(', '.join(pg_schemas)))

            # Add missing schemas
            missing_schemas = set(ldap_schemas) - set(pg_schemas)

            if missing_schemas:
                log.info("Create schemas: {}".format(', '.join(missing_schemas)))
                if not dry_mode:
                    for sch in missing_schemas:
                        try:
                            q = 'CREATE SCHEMA IF NOT EXISTS "{}";'.format(sch)
                            cur.execute(q)
                        except psycopg2.Error as e:
                            log.error("Unexpected error: {}".format(e))
                            #cur.execute("ROLLBACK")

    # Remove deprecated schemas (if empty)
    deprecated_schemas = set(pg_schemas) - set(ldap_schemas)
    if deprecated_schemas:
        log.info("Delete schemas (if empty): {}".format(', '.join(deprecated_schemas)))
        if not dry_mode:
            for sch in deprecated_schemas:
                with pg_conn:
                    with pg_conn.cursor() as cur:
                        try:
                            q = 'DROP SCHEMA IF EXISTS "{}" RESTRICT;'.format(sch)
                            cur.execute(q)
                        except psycopg2.Error as e:
                            if "cannot drop schema" in str(e):
                                log.warning("Could not drop the schema {} (probably not empty)".format(sch));
                            else:
                                log.error("Unexpected error: {}".format(e));
                            #cur.execute("ROLLBACK")


    log.info("schemas up-to-date")
    pg_conn.close()

if __name__ == '__main__':
    main()
