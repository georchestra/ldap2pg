ldap2pg doesn't manage the existence or deletion of the schemas.
To get a better automation, it is a good thing to create the schema when its pattern appears in the LDAP roles syntax. And to delete them, when they don't appear anymore if, and only if, they are empty (prevent data loss).
This is what this script does.
