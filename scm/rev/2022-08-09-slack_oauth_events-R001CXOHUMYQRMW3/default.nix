stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXOHUMYQRMW3";
    name = "2022-08-09-slack_oauth_events";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        
    ];
}
