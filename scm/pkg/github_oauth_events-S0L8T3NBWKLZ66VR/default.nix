stdargs @ { scm, ... }:

scm.schema {
    guid = "S0L8T3NBWKLZ66VR";
    name = "github_oauth_events";
    upgrade_sql = ./upgrade.sql;
    dependencies = [

    ];
}
