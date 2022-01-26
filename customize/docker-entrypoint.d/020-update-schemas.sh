#!/bin/bash
set -e

# Run the script that will synchronize the schemas in the DB, from the LDAP records
python3 /georchestra-ldap2pg/scripts/manage_schemas.py
