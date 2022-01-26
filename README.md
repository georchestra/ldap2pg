# LDAP2PG -- customized for geOrchestra

_Use excellent code from [ldap2pg](https://github.com/dalibo/ldap2pg/) to configure, from the console, the schemas and roles in your database._

_**Please be careful when using it: run some tests before running it in production. Review the config. Don't use it blindly, we will not be held responsible of what can happen**_

---

Most geOrchestra instances use a PostGIS DB to store geospatial (and also non-geospatial) data, for publication in GeoServer mostly.

This DB needs to be accessible by some editors of your geOrchestra instance.
Instead of configuring postgresql accounts, schemas and privileges manually,
you can

1. Configure your DB to lookup for users [using LDAP](https://www.postgresql.org/docs/9.3/auth-methods.html#AUTH-LDAP)
2. Configure the accounts, schemas and privileges using the console

This tool addresses the point 2:
- a small script (georchestra-custom/src/main.py) synchronizes the schemas
- then ldap2pg synchronizes the users accounts & privileges

All this based on roles, defined in the console.


## Known limitations

For now, it is tested and working on a separate postgresql cluster (don't use the main geOrchestra DB), with a single database, which name is provided in the config (environment variables).

While ldap2pg is capable of working with several databases, the schema synchronization script is not configured for this. And the default ldap2pg.yml config would probably need some revisiting, too.

Any contributions are welcome !


## Using it

### Configure the roles in the console

The expected syntax is `PGSQL_SCHEMA_[SCHEMANAME]_[PRIVILEGE]`.

For instance, `PGSQL_SCHEMA_KSK_WRITER` will give the user the writer role in the schema ksk. If it does not exist, the ksk schema will be created. If, at some point, no role remains that target the ksk schema, it will be removed _if empty_ (`DROP SCHEMA ... RESTRICT;`)

Allowed chunks:
- `PGSQL_SCHEMA_` is a fixed chunk, that allows to filter the relevant roles
- `[SCHEMANAME]` can take any reasonable value (uppercase non-accetnuated letters, and also _ and -)
- `[PRIVILEGE]` can be
  - READER: the user has read access (SELECT mostly) in the schema
  - PUBLISHER: the user has insert and update access in the schema, but cannot create any table
  - WRITER: the user is actually an owner of the schema (as defined by default in ldap2pg), meaning he can create tables and other objects and insert/update data.


Four additional database-wide roles are supported in the default ldap2pg config:
- PGSQL_READ_ALL: grants read access to all tables in all schemas
- PGSQL_PUBLISH_ALL: grants insert/update  for all tables in all schemas
- PGSQL_WRITE_ALL: grants ddl on all tables in all schemas. Actually some kind of superuser
- PGSQL_SUPERUSER: grants superuser profile (should not be needed, most likely PGSQL_WRITE_ALL is enough)


### Run the sync
#### Using docker
This was first designed to work with Docker. But since ldap2pg doesn't care about docker or not, and this is just some configurations + a little hack over ldap2pg, it should be easy to use it without docker. See below about it.

- Build the container (this is all expected to be run in a container, but you probably can figure out something without: just run the georchestra-custom/src/main.py for schema sync, then this modified ldap2pg)

  From *the root of this repo*, run

        docker build -t georchestra/ldap2pg:5.7 -f docker/Dockerfile .

- Run it (one shot)
      docker run --rm --tty \
        -e PGDSN=postgres://georchestra@192.168.1.70:5434/georchestra \
        -e PGPASSWORD_FILE=/workspace/pgpasswd \
        -e LDAPURI=ldap://192.168.1.70:3389 \
        -e LDAPBASEDN=dc=georchestra,dc=org \
        -e LDAPBINDDN=cn=admin,dc=georchestra,dc=org \
        -e LDAPPASSWORD_FILE=/workspace/ldappasswd \
        -e DRY="" \
        -e COLOR=1 \
        georchestra/ldap2pg:5.7

    In production, you will want to program it as a cron task or similar.

#### Without docker

You can install ldap2pg. Look at the [official documentation](https://ldap2pg.readthedocs.io/en/latest/install/). Then you will have to apply the following hack, and you will be able to use the configuration provided in this repo.

##### Hack
There is a small hack to apply on the ldap2pg upstream code: for geOrchestra usage, we need some regex parsing on the LDAP roles. This requires to hack ldap2pg's original format.py (this is too specific to be accepted in the upstream project). So, replace the original ldap2pg's format.py file by the one from customize/hacks/format.py (the only changes are at lines 324-337).
For instance, if you have installed ldap2pg using pip, you will have to replace the format.py file at /usr/local/lib/python3.9/dist-packages/ldap2pg/format.py (Debian 11 example, you might have to adjust according to your environment).

##### Config
You can use the config file from customize/config/ldap2pg.yml
See ldap2pg's main doc to see how to [use custom config file](https://ldap2pg.readthedocs.io/en/latest/cli/).

##### Manage schemas
We added a small script that handles schemas' creation & deletion when needed. You will find it in customize/scripts/manage_schemas.py. You're supposed to run it *before* running ldap2pg .

#### Environment variables
Configuration is mostly done using environment variables:

**Compulsory**:
- PGDSN: the connection string to the postgresql DB. Look at the example above for a valid syntax
- PGPASSWORD: password for the user documented in the DSN string. You can use PGPASSWORD_FILE to provide it through a docker secret
- LDAPURI: the connection string to the LDAP DB. Look at the example above for a valid syntax
- LDAPBASEDN: the LDAP base DN. Look at the example above for a valid syntax
- LDAPBINDDN: the LDAP admin user. Look at the example above for a valid syntax
- LDAPPASSWORD_FILE: the LDAP admin user's password. You can use LDAPPASSWORD_FILE to provide it through a docker secret

**Optional**:
- LDAP_ROLE_REGEX: the regular expression used to extract the roles from the LDAP DB. See below for the default value
- and quite a few env vars supported by [ldap2pg] (https://ldap2pg.readthedocs.io/en/latest/cli/#environment-variables). To name a few:
  - DRY: if set to `1`, it will run in dry mode (not change anything). If set to `''`, changes are applied (what we want in production)
  - VERBOSITY: set it to `DEBUG` to get a more verbose output
  - COLOR: set it to `1` to get a colored output (docker need the `--tty` option, too)


### Changing the default config

This is all very configurable if you feel like a rebel. There are mostly 2 places to look at:

#### LDAP_ROLE_REGEX environment variable

You can change the default regular expression applied on the console roles. The default value is
`LDAP_ROLE_REGEX="^PGSQL_SCHEMA_([A-Z][A-Z0-9-_]+)_(READER|WRITER|PUBLISHER)$"`
If you change it, you will probably need to adjust the ldap2pg.yml config file too

#### ldap2pg.yml

The default config is the customize/config/ldap2pg.yml file. In the docker image, it is copied as /etc/ldap2pg.yml.
To override it, the easiest way is to mount a /workspace volume, in which will be your ldap2pg.yml alternative file. See https://ldap2pg.readthedocs.io/en/latest/config/#file-location

If you feel like playing with configuration, let's have a look at https://ldap2pg.readthedocs.io/en/latest/config/.


## Aknowledgements
We thank [Dalibo](https://github.com/dalibo) for this nice piece of software that is ldap2pg. Thank you, [bersace](https://github.com/bersace) for helping me out at figuring how the ldap2pg config works.
