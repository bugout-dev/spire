stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXQDMIDE091L";
    name = "2022-08-09-github_checks";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-04-github_oauth_events-R001COS1ACCETILG>
        <2022-08-09-github_repos-R001CXQ80THAGLN3>
        <2022-08-09-github_issues_prs-R001CXQ8X5ATFOUE>
    ];
}
