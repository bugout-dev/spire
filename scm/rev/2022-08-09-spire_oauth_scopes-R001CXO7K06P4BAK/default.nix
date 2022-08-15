stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXO7K06P4BAK";
    name = "2022-08-09-spire_oauth_scopes";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        
    ];
}
