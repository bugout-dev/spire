stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXOB6OVUS12Q";
    name = "2022-08-09-public_users";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        
    ];
}
