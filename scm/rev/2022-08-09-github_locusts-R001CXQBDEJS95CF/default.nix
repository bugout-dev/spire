stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXQBDEJS95CF";
    name = "2022-08-09-github_locusts";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-github_issues_prs-R001CXQ8X5ATFOUE>
    ];
}
