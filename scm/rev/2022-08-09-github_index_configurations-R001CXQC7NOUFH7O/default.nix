stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXQC7NOUFH7O";
    name = "2022-08-09-github_index_configurations";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-04-github_oauth_events-R001COS1ACCETILG>
    ];
}
