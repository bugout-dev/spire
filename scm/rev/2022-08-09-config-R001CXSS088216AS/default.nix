stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXSS088216AS";
    name = "2022-08-09-config";
    basefiles = ./basefiles;
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        
    ];
}
