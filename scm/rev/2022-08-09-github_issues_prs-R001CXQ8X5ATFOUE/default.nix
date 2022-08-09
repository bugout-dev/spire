stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXQ8X5ATFOUE";
    name = "2022-08-09-github_issues_prs";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-04-github_oauth_events-R001COS1ACCETILG>
        <2022-08-09-github_repos-R001CXQ80THAGLN3>
    ];
}
