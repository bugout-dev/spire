stdargs @ { scm, ... }:

scm.revision {
    guid = "R001COS1T0OKAPY7";
    name = "2022-08-04-github_bugout_users";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-04-github_oauth_events-R001COS1ACCETILG>
    ];
}
