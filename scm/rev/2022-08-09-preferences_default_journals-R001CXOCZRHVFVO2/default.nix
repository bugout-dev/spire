stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXOCZRHVFVO2";
    name = "2022-08-09-preferences_default_journals";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        
    ];
}
