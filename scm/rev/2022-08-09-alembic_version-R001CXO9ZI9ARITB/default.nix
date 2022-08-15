stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXO9ZI9ARITB";
    name = "2022-08-09-alembic_version";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        
    ];
}
