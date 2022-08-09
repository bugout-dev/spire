stdargs @ { scm, ... }:

scm.revision {
    guid = "R001COSILGN1FVM0";
    name = "2022-08-04-journals";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        
    ];
}
