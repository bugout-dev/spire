stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXQ80THAGLN3";
    name = "2022-08-09-github_repos";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-04-github_oauth_events-R001COS1ACCETILG>
    ];
}
