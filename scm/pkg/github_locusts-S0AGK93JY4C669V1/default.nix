stdargs @ { scm, ... }:

scm.schema {
    guid = "S0AGK93JY4C669V1";
    name = "github_locusts";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <github_issues_prs-S0JD4L40K2RY4QYJ>
        <2022-08-09-github_locusts-R001CXQBDEJS95CF>
    ];
}
