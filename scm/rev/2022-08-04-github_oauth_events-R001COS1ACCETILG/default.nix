stdargs @ { scm, ... }:

scm.revision {
    guid = "R001COS1ACCETILG";
    name = "2022-08-04-github_oauth_events";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        
    ];
}
