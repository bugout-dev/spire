stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXODPVGLEDUS";
    name = "2022-08-09-permalink_journals";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        
    ];
}
