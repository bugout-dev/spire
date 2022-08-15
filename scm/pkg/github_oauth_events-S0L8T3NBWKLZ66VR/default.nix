stdargs @ { scm, ... }:

scm.schema {
    guid = "S0L8T3NBWKLZ66VR";
    name = "github_oauth_events";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-04-github_oauth_events-R001COS1ACCETILG>
    ];
}
